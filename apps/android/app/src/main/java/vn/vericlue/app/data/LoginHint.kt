package vn.vericlue.app.data

import vn.vericlue.app.flow.AccountAccessRules
import vn.vericlue.app.data.api.AccountProfile
import java.time.Instant
import kotlinx.serialization.Serializable
import kotlinx.serialization.encodeToString
import kotlinx.serialization.json.Json

/**
 * Minimal, expiring greeting, never an authentication credential. The app supplies EncryptedStore.
 * Passwords, access tokens and identity numbers are never stored here.
 */
class LoginHint(private val store: KeyValueStore, private val now: () -> Instant = Instant::now) {
    @Serializable
    data class Hint(val username: String, val fullName: String?, val accountId: String, val expiresAt: String)

    fun profile(): Hint? = runCatching {
        val value = store.get(PROFILE) ?: return@runCatching null
        val hint = Json.decodeFromString<Hint>(value).takeIf {
            AccountAccessRules.validUsername(it.username) &&
                Regex("acct_[0-9a-f]{32}").matches(it.accountId) &&
                (it.fullName == null || it.fullName.length <= 200) &&
                AccountAccessRules.instant(it.expiresAt)?.isAfter(now()) == true
        }
        if (hint == null) store.remove(PROFILE)
        hint
    }.getOrNull()

    fun load(): String? = profile()?.username ?: runCatching {
        store.get(KEY)?.let(AccountAccessRules::username)?.takeIf(AccountAccessRules::validUsername)
    }.getOrNull()

    fun save(profile: AccountProfile) {
        if (!AccountAccessRules.profileValid(profile, now())) return
        runCatching {
            store.put(PROFILE, Json.encodeToString(Hint(profile.username, profile.fullName, profile.accountId, profile.expiresAt)))
            store.remove(KEY)
        }
    }

    /** Best effort: a failed write only costs the greeting, never the login itself. */
    fun save(username: String) {
        val normalized = AccountAccessRules.username(username)
        if (AccountAccessRules.validUsername(normalized)) runCatching { store.put(KEY, normalized) }
    }

    fun clear() { store.remove(KEY); store.remove(PROFILE) }

    companion object {
        const val KEY = "login_hint.username.v1"
        private const val PROFILE = "login_hint.profile.v2"
    }
}
