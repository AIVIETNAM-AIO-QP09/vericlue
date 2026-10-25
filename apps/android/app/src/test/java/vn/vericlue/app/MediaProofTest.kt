package vn.vericlue.app

import java.io.File
import java.security.KeyFactory
import java.security.Signature
import java.security.spec.X509EncodedKeySpec
import java.util.Base64
import kotlinx.serialization.json.Json
import kotlinx.serialization.json.jsonObject
import kotlinx.serialization.json.jsonPrimitive
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test
import vn.vericlue.app.data.api.Challenge
import vn.vericlue.app.data.api.CreateSessionResponse
import vn.vericlue.app.security.MediaProof

class MediaProofTest {
    @Test
    fun canonicalBytesAndPythonSignatureMatchSharedVector() {
        val vector = Json.parseToJsonElement(File("../../../packages/contracts/test-vectors/media-proof-v1.json").readText()).jsonObject
        val challenge = Challenge("ch_golden", colorSequence = emptyList(), mediaNonce = "0".repeat(64))
        val session = CreateSessionResponse("ses_golden", "synthetic-token", "synthetic-expiry", challenge, "onboarding", "synthetic_nonce_1234")
        val payload = MediaProof.manifest(session, challenge, "face", "ch_golden",
            mapOf("image" to MediaProof.digest("face.jpg", "abc".toByteArray())))
        assertEquals(vector["canonical"]!!.jsonPrimitive.content, payload.toString(Charsets.US_ASCII))
        val key = KeyFactory.getInstance("EC").generatePublic(X509EncodedKeySpec(Base64.getDecoder().decode(vector["public_key_spki"]!!.jsonPrimitive.content)))
        val signature = Base64.getDecoder().decode(vector["signature"]!!.jsonPrimitive.content)
        fun verify(data: ByteArray) = Signature.getInstance("SHA256withECDSA").run {
            initVerify(key); update(data); verify(signature)
        }
        assertTrue(verify(payload))
        assertFalse(verify(payload + byteArrayOf(0)))
    }

    @Test
    fun hashingFileAndByteArrayUseSameBytesAndSuffix() {
        val file = File.createTempFile("synthetic", ".MP4")
        try {
            file.writeBytes(byteArrayOf(1, 2, 3, 4))
            assertEquals(MediaProof.digest("video.MP4", file.readBytes()), MediaProof.digest(file))
        } finally { file.delete() }
    }

    @Test(expected = IllegalArgumentException::class)
    fun absentServerNonceNeverFallsBackToUnsignedMedia() {
        val challenge = Challenge("ch_synthetic", colorSequence = emptyList())
        val session = CreateSessionResponse("ses_synthetic", "token", "expiry", challenge, "onboarding", "synthetic_nonce_1234")
        MediaProof.manifest(session, challenge, "face", challenge.challengeId,
            mapOf("image" to MediaProof.digest("face.jpg", byteArrayOf(1))))
    }
}
