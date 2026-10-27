package vn.vericlue.app.data

import android.content.SharedPreferences
import java.time.Instant
import java.time.OffsetDateTime
import kotlinx.serialization.json.Json
import vn.vericlue.app.data.api.AccountReceipt

/** Small key-value storage: app-private SharedPreferences on the phone, a map in tests. */
interface KeyValueStore {
    fun get(key: String): String?
    fun put(key: String, value: String)
    fun remove(key: String)
}

class PrefsStore(private val prefs: SharedPreferences) : KeyValueStore {
    override fun get(key: String) = prefs.getString(key, null)
    override fun put(key: String, value: String) { prefs.edit().putString(key, value).apply() }
    override fun remove(key: String) { prefs.edit().remove(key).apply() }
}

/**
 * SEC-02 receipt of the account enrolled on this phone. Not a secret: the private key stays in the
 * Keystore. An expired or unreadable receipt counts as no account and is dropped.
 */
class AccountStore(private val store: KeyValueStore, private val now: () -> Instant = Instant::now) {
    fun load(): AccountReceipt? {
        val raw = store.get(KEY) ?: return null
        val receipt = runCatching { json.decodeFromString(AccountReceipt.serializer(), raw) }.getOrNull()
        val expires = receipt?.let { runCatching { OffsetDateTime.parse(it.expiresAt).toInstant() }.getOrNull() }
        if (receipt == null || expires == null || !expires.isAfter(now())) {
            store.remove(KEY)
            return null
        }
        return receipt
    }

    fun save(receipt: AccountReceipt) = store.put(KEY, json.encodeToString(AccountReceipt.serializer(), receipt))

    fun clear() = store.remove(KEY)

    private companion object {
        const val KEY = "account_receipt.v1"
        val json = Json { ignoreUnknownKeys = true }
    }
}
