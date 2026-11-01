package vn.vericlue.app.data

import android.content.SharedPreferences
import java.time.Instant
import java.time.OffsetDateTime
import kotlinx.serialization.Serializable
import kotlinx.serialization.json.Json
import vn.vericlue.app.data.api.AccountReceipt
import vn.vericlue.app.security.KeyAliases

/** Small key-value storage: app-private SharedPreferences on the phone, a map in tests. */
interface KeyValueStore {
    fun get(key: String): String?
    /** Returns only after a durable write; failure must throw. */
    fun put(key: String, value: String)
    fun remove(key: String)
}

class PrefsStore(private val prefs: SharedPreferences) : KeyValueStore {
    override fun get(key: String) = prefs.getString(key, null)
    override fun put(key: String, value: String) {
        val previous = prefs.getString(key, null)
        if (!prefs.edit().putString(key, value).commit()) {
            // commit() may have changed the in-memory value even if the disk write failed.
            val rollback = prefs.edit()
            if (previous == null) rollback.remove(key) else rollback.putString(key, previous)
            rollback.commit()
            error("Account receipt write failed")
        }
    }
    override fun remove(key: String) { prefs.edit().remove(key).apply() }
}

/**
 * SEC-02 receipt of the account enrolled on this phone. Not a secret: the private key stays in the
 * Keystore. Expired/unreadable records are unavailable, but remain intact for inspection.
 */
@Serializable
data class StoredAccount(
    val receipt: AccountReceipt,
    val keyAlias: String,
    val evaluationMode: String? = null,
    val demoPolicyId: String? = null,
    val previousBindings: List<StoredAccount> = emptyList(),
    val unreadableBindingBackup: String? = null,
) {
    /** Missing metadata is legacy/unknown, never an implicit standard or demo binding. */
    val hasKnownEvaluationBinding: Boolean get() = when (evaluationMode) {
        "standard" -> demoPolicyId == null
        "manual_full_demo" -> demoPolicyId?.matches(Regex("[0-9a-f]{64}")) == true
        else -> false
    }
    val manualFullDemo: Boolean get() = hasKnownEvaluationBinding && evaluationMode == "manual_full_demo"
}

class AccountStore(private val store: KeyValueStore, private val now: () -> Instant = Instant::now) {
    fun load(): StoredAccount? {
        // Receipt-only v1 cannot establish a key; leave it intact instead of inventing an alias.
        val raw = store.get(KEY) ?: return null
        val account = runCatching { json.decodeFromString(StoredAccount.serializer(), raw) }.getOrNull()
        return account?.takeIf(::valid)
    }

    fun save(receipt: AccountReceipt, keyAlias: String, evaluationMode: String? = null,
             demoPolicyId: String? = null, preserveExisting: Boolean = false) {
        val raw = store.get(KEY)
        val previous = raw?.let { runCatching { json.decodeFromString(StoredAccount.serializer(), it) }.getOrNull() }
        val replaced = preserveExisting && raw != null &&
            (previous?.receipt != receipt || previous?.keyAlias != keyAlias)
        val history = previous?.previousBindings.orEmpty().toMutableList()
        if (replaced && previous != null) history.add(previous.copy(previousBindings = emptyList()))
        val account = StoredAccount(receipt, keyAlias, evaluationMode, demoPolicyId, history,
            if (replaced && previous == null) raw else previous?.unreadableBindingBackup)
        require(valid(account))
        require(account.hasKnownEvaluationBinding || evaluationMode == null && demoPolicyId == null)
        store.put(KEY, json.encodeToString(StoredAccount.serializer(), account))
    }

    private fun valid(account: StoredAccount): Boolean {
        val receipt = account.receipt
        val expires = runCatching { OffsetDateTime.parse(receipt.expiresAt).toInstant() }.getOrNull()
        return receipt.accountId.isNotBlank() && receipt.deviceId.isNotBlank() &&
            KeyAliases.valid(account.keyAlias) && expires != null && expires.isAfter(now())
    }

    fun clear() = store.remove(KEY)

    private companion object {
        const val KEY = "account_binding.v2"
        val json = Json { ignoreUnknownKeys = true }
    }
}
