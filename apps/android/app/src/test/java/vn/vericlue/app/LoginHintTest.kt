package vn.vericlue.app

import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Assert.assertFalse
import org.junit.Test
import vn.vericlue.app.data.KeyValueStore
import vn.vericlue.app.data.LoginHint
import vn.vericlue.app.data.api.AccountProfile
import java.time.Instant

class LoginHintTest {
    @Test fun keepsOnlyMinimalGreetingUntilAccountExpiry() {
        val store = Memory()
        var now = Instant.parse("2026-11-03T10:00:00Z")
        val hint = LoginHint(store) { now }
        val profile = AccountProfile("acct_" + "a".repeat(32), "0901234567", "Nguyễn Thị Đặng", "********1234",
            "2026-11-03T09:00:00Z", "2026-11-03T11:00:00Z", "standard", null)
        hint.save(profile)
        assertEquals(profile.username, hint.load())
        assertEquals(profile.fullName, hint.profile()?.fullName)
        assertEquals(profile.accountId, hint.profile()?.accountId)
        assertFalse(store.values.values.single().contains("********1234"))
        assertFalse(store.values.values.single().contains("access_token"))
        now = Instant.parse("2026-11-03T11:00:00Z")
        assertNull(hint.load())
        assertNull(hint.profile())
        hint.clear()
        assertTrue(store.values.isEmpty())
    }
    private class Memory : KeyValueStore {
        val values = mutableMapOf<String, String>()
        var failWrite = false
        override fun get(key: String) = values[key]
        override fun put(key: String, value: String) {
            check(!failWrite) { "synthetic write failure" }
            values[key] = value
        }
        override fun remove(key: String) { values.remove(key) }
    }

    @Test fun remembersOnlyANormalisedValidUsername() {
        val store = Memory()
        val hint = LoginHint(store)
        hint.save("  NguoiDung.Demo ")
        assertEquals("nguoidung.demo", hint.load())
        assertEquals("Only the username key is written", setOf(LoginHint.KEY), store.values.keys)
    }

    @Test fun ignoresInvalidOrTamperedValues() {
        val store = Memory()
        val hint = LoginHint(store)
        hint.save("a")
        assertNull("Too-short usernames are never stored", hint.load())
        store.values[LoginHint.KEY] = "<script>"
        assertNull("A tampered value is not shown as a greeting", hint.load())
    }

    @Test fun aFailedWriteNeverBreaksLoginAndClearForgets() {
        val store = Memory().apply { failWrite = true }
        val hint = LoginHint(store)
        hint.save("nguoidung.demo")
        assertNull(hint.load())
        store.failWrite = false
        hint.save("nguoidung.demo")
        hint.clear()
        assertNull(hint.load())
    }
}
