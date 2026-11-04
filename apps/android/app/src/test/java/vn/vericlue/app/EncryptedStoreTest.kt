package vn.vericlue.app

import java.util.Base64
import javax.crypto.spec.SecretKeySpec
import org.junit.Assert.*
import org.junit.Test
import vn.vericlue.app.data.EncryptedStore
import vn.vericlue.app.data.KeyValueStore

class EncryptedStoreTest {
    private class Memory : KeyValueStore {
        val values = mutableMapOf<String, String>()
        override fun get(key: String) = values[key]
        override fun put(key: String, value: String) { values[key] = value }
        override fun remove(key: String) { values.remove(key) }
    }

    @Test fun encryptsAtRestWithFreshIvAndRejectsChangedCiphertextAndWrongKey() {
        val raw = Memory()
        val secret = SecretKeySpec(ByteArray(32) { 1 }, "AES")
        val encrypted = EncryptedStore(raw) { secret }
        val privateText = "0901234567 Nguyễn Thị Đặng"
        encrypted.put("hint", privateText)
        val first = raw.values.getValue("hint")
        assertFalse(first.contains("0901234567"))
        assertFalse(first.contains("Nguyễn"))
        assertEquals(privateText, encrypted.get("hint"))
        encrypted.put("hint", privateText)
        assertNotEquals(first, raw.values["hint"])
        raw.values["other"] = raw.values.getValue("hint")
        assertNull("AAD binds the ciphertext to its storage key", encrypted.get("other"))
        val wrong = EncryptedStore(raw) { SecretKeySpec(ByteArray(32) { 2 }, "AES") }
        assertNull(wrong.get("hint"))
        val changed = Base64.getDecoder().decode(raw.values.getValue("hint"))
        changed[changed.lastIndex] = (changed.last().toInt() xor 1).toByte()
        raw.values["hint"] = Base64.getEncoder().encodeToString(changed)
        assertNull(encrypted.get("hint"))
        raw.values["hint"] = privateText
        assertNull("Never treat plaintext as a decrypted hint", encrypted.get("hint"))
    }
}
