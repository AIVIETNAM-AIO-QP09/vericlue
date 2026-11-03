package vn.vericlue.app.data

import vn.vericlue.app.flow.AccountAccessRules

/**
 * Remembers only the last username that signed in with a password, so the login card can greet the
 * user and ask for the password alone. Never stores a password, token, profile or identity number.
 */
class LoginHint(private val store: KeyValueStore) {
    fun load(): String? = store.get(KEY)?.let(AccountAccessRules::username)?.takeIf(AccountAccessRules::validUsername)

    /** Best effort: a failed write only costs the greeting, never the login itself. */
    fun save(username: String) {
        val normalized = AccountAccessRules.username(username)
        if (AccountAccessRules.validUsername(normalized)) runCatching { store.put(KEY, normalized) }
    }

    fun clear() = store.remove(KEY)

    companion object {
        const val KEY = "login_hint.username.v1"
    }
}
