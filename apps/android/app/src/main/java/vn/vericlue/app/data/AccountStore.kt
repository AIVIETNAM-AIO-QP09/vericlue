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
        check(prefs.edit().putString(key, value).commit()) { "Account receipt write failed" }
    }
    override fun remove(key: String) { prefs.edit().remove(key).apply() }
}

/**
 * SEC-02 receipt of the account enrolled on this phone. Not a secret: the private key stays in the
 * Keystore. An expired or unreadable receipt counts as no account and is dropped.
 */
@Serializable
data class StoredAccount(val receipt: AccountReceipt, val keyAlias: String)

class AccountStore(private val store: KeyValueStore, private val now: () -> Instant = Instant::now) {
    fun load(): StoredAccount? {
        // The old receipt-only format cannot establish which key was enrolled.
        store.remove("account_receipt.v1")
        val raw = store.get(KEY) ?: return null
        val account = runCatching { json.decodeFromString(StoredAccount.serializer(), raw) }.getOrNull()
        if (account == null || !valid(account)) {
            store.remove(KEY)
            return null
        }
        return account
    }

    fun save(receipt: AccountReceipt, keyAlias: String) {
        val account = StoredAccount(receipt, keyAlias)
        require(valid(account))
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
