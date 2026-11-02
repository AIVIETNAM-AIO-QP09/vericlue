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
    var accountSaved = false
        private set

    fun begin(requested: Purpose): AccountEntry {
        accountSaved = false
        val saved = store.load()
        if (requested != Purpose.Onboarding && saved != null && !saved.hasKnownEvaluationBinding) {
            return AccountEntry(requested, saved.receipt, saved.keyAlias, null, Routes.ErrorService,
                "Tài khoản cũ chưa có thông tin chế độ. Về màn hình chính và chọn Đăng ký để bắt đầu phiên mới; tài khoản cũ được giữ lại.", saved)
        }
        if (requested == Purpose.Reauth && signingEnabled && saved != null) {
            if (!keys.exists(saved.keyAlias)) {
                return AccountEntry(requested, saved.receipt, saved.keyAlias, null, Routes.RecoveryRequired)
            }
            return AccountEntry(requested, saved.receipt, saved.keyAlias,
                keys.open(saved.keyAlias, create = false), Routes.Terms, previous = saved)
        }
        val fallback = requested != Purpose.Onboarding && (!signingEnabled || saved == null)
        val purpose = if (fallback) Purpose.Onboarding else requested
        val alias = if (signingEnabled) newAlias() else null
        require(alias == null || KeyAliases.valid(alias))
        require(purpose != Purpose.Recovery || alias != saved?.keyAlias)
        return AccountEntry(purpose,
            saved?.receipt?.takeIf { purpose == Purpose.Recovery }, alias,
            alias?.let { keys.open(it, create = true) },
            Routes.Terms,
            if (fallback) "Vui lòng đăng ký để tiếp tục." else null,
            saved?.takeIf { purpose == Purpose.Recovery })
    }

    /** Persistence finishes before Success's automatic navigation starts. Failure never changes pass. */
    suspend fun finish(entry: AccountEntry, live: LiveFlow, next: Next): Next {
        if (next != Next.To(Routes.Success)) return next
        val session = live.session ?: return Next.Fail(vn.vericlue.app.data.api.ApiError.BadResponse)
        val previous = entry.previous
        if (session.purpose != FlowRules.purposeCode(entry.purpose) ||
            entry.account != live.boundAccount ||
            entry.purpose != Purpose.Onboarding && (previous == null || !previous.hasKnownEvaluationBinding ||
                previous.evaluationMode != session.evaluationMode || previous.demoPolicyId != session.demoPolicyId)) {
            warn("account_evaluation_context_mismatch")
            return Next.Fail(vn.vericlue.app.data.api.ApiError.BadResponse)
        }
        if (entry.purpose == Purpose.Reauth) return next
        val alias = entry.keyAlias ?: return next
        val receipt = live.receiptAfterPass()
        if (receipt == null) {
            warn("account_receipt_unavailable")
            return next
        }
        if (entry.purpose == Purpose.Recovery && (previous == null ||
                receipt.accountId != previous.receipt.accountId || receipt.deviceId == previous.receipt.deviceId)) {
            warn("account_receipt_context_mismatch")
            return Next.Fail(vn.vericlue.app.data.api.ApiError.BadResponse)
        }
        withContext(Dispatchers.IO) {
            try {
                store.save(receipt, alias, session.evaluationMode, session.demoPolicyId,
                    preserveExisting = entry.purpose == Purpose.Onboarding)
                accountSaved = true
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
