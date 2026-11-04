package vn.vericlue.app.data

import java.nio.charset.StandardCharsets.UTF_8
import java.util.Base64
import javax.crypto.Cipher
import javax.crypto.SecretKey
import javax.crypto.spec.GCMParameterSpec

/** Encrypts display hints at rest; associated data prevents swapping values between keys. */
class EncryptedStore(private val store: KeyValueStore, private val secret: () -> SecretKey) : KeyValueStore {
    override fun get(key: String): String? = runCatching {
        val value = store.get(key) ?: return@runCatching null
        val bytes = Base64.getDecoder().decode(value)
        require(bytes.size >= 28)
        val cipher = Cipher.getInstance("AES/GCM/NoPadding")
        cipher.init(Cipher.DECRYPT_MODE, secret(), GCMParameterSpec(128, bytes.copyOfRange(0, 12)))
        cipher.updateAAD("vericlue-login-hint-v1:$key".toByteArray(UTF_8))
        String(cipher.doFinal(bytes.copyOfRange(12, bytes.size)), UTF_8)
    }.getOrNull()

    override fun put(key: String, value: String) {
        val cipher = Cipher.getInstance("AES/GCM/NoPadding")
        cipher.init(Cipher.ENCRYPT_MODE, secret())
        cipher.updateAAD("vericlue-login-hint-v1:$key".toByteArray(UTF_8))
        store.put(key, Base64.getEncoder().encodeToString(cipher.iv + cipher.doFinal(value.toByteArray(UTF_8))))
    }

    override fun remove(key: String) = store.remove(key)
}
