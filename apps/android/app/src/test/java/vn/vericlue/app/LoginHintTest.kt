package vn.vericlue.app

import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Test
import vn.vericlue.app.data.KeyValueStore
import vn.vericlue.app.data.LoginHint

class LoginHintTest {
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
