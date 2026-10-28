package vn.vericlue.app.flow

import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import vn.vericlue.app.data.AccountStore
import vn.vericlue.app.data.StoredAccount
import vn.vericlue.app.data.api.AccountReceipt
import vn.vericlue.app.security.AccountKeys
import vn.vericlue.app.security.KeyAliases
import vn.vericlue.app.security.MediaSigner

data class AccountEntry(
    val purpose: Purpose,
    val account: AccountReceipt?,
    val keyAlias: String?,
    val signer: MediaSigner?,
    val route: String,
    val hint: String? = null,
    val previous: StoredAccount? = null,
)

/** One auth choice owns one key/session context. Call begin on IO (Keystore/prefs). */
class AccountFlow(
    private val store: AccountStore,
    private val keys: AccountKeys,
    private val signingEnabled: Boolean,
    private val newAlias: () -> String = KeyAliases::fresh,
    private val warn: (String) -> Unit = {},
) {
    fun begin(requested: Purpose): AccountEntry {
        val saved = store.load()
        if (requested == Purpose.Reauth && signingEnabled && saved != null) {
            if (!keys.exists(saved.keyAlias)) {
                return AccountEntry(requested, saved.receipt, saved.keyAlias, null, Routes.RecoveryRequired)
            }
            return AccountEntry(requested, saved.receipt, saved.keyAlias,
                keys.open(saved.keyAlias, create = false), Routes.Phone)
        }
        val fallback = requested != Purpose.Onboarding && (!signingEnabled || saved == null)
        val purpose = if (fallback) Purpose.Onboarding else requested
        val alias = if (signingEnabled) newAlias() else null
        require(alias == null || KeyAliases.valid(alias))
        require(purpose != Purpose.Recovery || alias != saved?.keyAlias)
        return AccountEntry(purpose,
            saved?.receipt?.takeIf { purpose == Purpose.Recovery }, alias,
            alias?.let { keys.open(it, create = true) },
            if (purpose == Purpose.Onboarding) Routes.Terms else Routes.Phone,
            if (fallback) "Vui lòng đăng ký để tiếp tục." else null,
            saved?.takeIf { purpose == Purpose.Recovery })
    }

    /** Persistence finishes before Success's automatic navigation starts. Failure never changes pass. */
    suspend fun finish(entry: AccountEntry, live: LiveFlow, next: Next): Next {
        if (next != Next.To(Routes.Success) || entry.purpose == Purpose.Reauth) return next
        val alias = entry.keyAlias ?: return next
        val receipt = live.receiptAfterPass()
        if (receipt == null) {
            warn("account_receipt_unavailable")
            return next
        }
        val previous = entry.previous
        if (entry.purpose == Purpose.Recovery && (previous == null ||
                receipt.accountId != previous.receipt.accountId || receipt.deviceId == previous.receipt.deviceId)) {
            warn("account_receipt_context_mismatch")
            return next
        }
        withContext(Dispatchers.IO) {
            try {
                store.save(receipt, alias)
            } catch (e: CancellationException) {
                throw e
            } catch (_: Exception) {
                warn("account_receipt_write_failed")
                return@withContext
            }
            if (previous != null && previous.keyAlias != alias) {
                try {
                    keys.delete(previous.keyAlias)
                } catch (_: Exception) {
                    // The new binding is durable. A cleanup failure must not roll it back.
                    warn("account_old_key_cleanup_failed")
                }
            }
        }
        return next
    }
}
