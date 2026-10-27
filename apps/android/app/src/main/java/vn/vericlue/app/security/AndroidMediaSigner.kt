package vn.vericlue.app.security

import android.security.keystore.KeyGenParameterSpec
import android.security.keystore.KeyProperties
import java.security.KeyPairGenerator
import java.security.KeyStore
import java.security.Signature
import java.security.spec.ECGenParameterSpec
import java.util.Base64

/**
 * SEC-02: non-exportable app key, P-256/SHA256withECDSA, DER signatures.
 * Recipe: https://developer.android.com/privacy-and-security/keystore
 * Call on Dispatchers.IO. This does not attest hardware or prove camera origin.
 */
class AndroidMediaSigner(private val alias: String = "vericlue.media.v1") : MediaSigner {
    init { require(alias.matches(Regex("vericlue\\.media\\.[A-Za-z0-9._-]{1,100}"))) }

    private fun entry(): KeyStore.PrivateKeyEntry = synchronized(creationLock) {
        val store = KeyStore.getInstance("AndroidKeyStore").apply { load(null) }
        if (!store.containsAlias(alias)) {
            KeyPairGenerator.getInstance(KeyProperties.KEY_ALGORITHM_EC, "AndroidKeyStore").apply {
                initialize(KeyGenParameterSpec.Builder(alias, KeyProperties.PURPOSE_SIGN)
                    .setAlgorithmParameterSpec(ECGenParameterSpec("secp256r1"))
                    .setDigests(KeyProperties.DIGEST_SHA256)
                    .build())
                generateKeyPair()
            }
        }
        store.getEntry(alias, null) as KeyStore.PrivateKeyEntry
    }

    override val publicKeySpki: String
        get() = Base64.getEncoder().encodeToString(entry().certificate.publicKey.encoded)

    override fun sign(canonicalManifest: ByteArray): String {
        val signature = Signature.getInstance("SHA256withECDSA").run {
            initSign(entry().privateKey)
            update(canonicalManifest)
            sign()
        }
        return Base64.getEncoder().encodeToString(signature)
    }

    private companion object { val creationLock = Any() }
}
