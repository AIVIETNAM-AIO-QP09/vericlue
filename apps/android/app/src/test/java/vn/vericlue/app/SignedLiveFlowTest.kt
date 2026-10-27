package vn.vericlue.app

import java.security.KeyPairGenerator
import java.security.Signature
import java.security.spec.ECGenParameterSpec
import java.util.Base64
import kotlinx.coroutines.test.runTest
import okhttp3.mockwebserver.MockResponse
import okhttp3.mockwebserver.MockWebServer
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test
import vn.vericlue.app.data.api.ApiError
import vn.vericlue.app.data.api.SessionApi
import vn.vericlue.app.flow.LiveFlow
import vn.vericlue.app.flow.Next
import vn.vericlue.app.security.MediaSigner

class SignedLiveFlowTest {
    private class Signer : MediaSigner {
        private val pair = KeyPairGenerator.getInstance("EC").run {
            initialize(ECGenParameterSpec("secp256r1")); generateKeyPair()
        }
        val payloads = mutableListOf<String>()
        override val publicKeySpki = Base64.getEncoder().encodeToString(pair.public.encoded)
        override fun sign(canonicalManifest: ByteArray): String {
            payloads.add(canonicalManifest.toString(Charsets.US_ASCII))
            return Base64.getEncoder().encodeToString(Signature.getInstance("SHA256withECDSA").run {
                initSign(pair.private); update(canonicalManifest); sign()
            })
        }
    }

    private fun response(signed: Boolean = true) = """
        {"session_id":"ses_test","token":"token","expires_at":"expiry","purpose":"onboarding","nonce":"synthetic_nonce_1234",
        "challenge":{"challenge_id":"ch_test","color_sequence":[],${if (signed) "\"media_nonce\":\"${"0".repeat(64)}\"," else ""}"capture_at_ms":[]}}
    """.trimIndent()

    @Test
    fun signsFaceAndVoiceAndBindsTransmittedOffset() = runTest {
        val server = MockWebServer().apply { start() }
        try {
            val signer = Signer()
            val flow = LiveFlow(SessionApi(server.url("/").toString()), signer)
            server.enqueue(MockResponse().setBody(response()))
            assertEquals(null, flow.ensureSession(null, "onboarding"))
            assertTrue(server.takeRequest().body.readUtf8().contains("device_public_key_spki"))
            flow.frontalJpeg = byteArrayOf(1, 2, 3)
            server.enqueue(MockResponse().setBody("""{"step":"media","received":true}"""))
            server.enqueue(MockResponse().setBody("""{"step":"signals","received":true}"""))
            server.enqueue(MockResponse().setBody("""{"status":"voice_challenge","voice_prompt":"synthetic prompt","voice_challenge_id":"vc_test"}"""))
            assertTrue(flow.submitFace(null, emptyList(), emptyMap()) is Next.To)
            assertTrue(server.takeRequest().body.readUtf8().contains("media_signature"))
            server.takeRequest(); server.takeRequest()
            server.enqueue(MockResponse().setBody("""{"status":"pass"}"""))
            assertTrue(flow.submitVoice(byteArrayOf(4, 5, 6)) is Next.To)
            assertTrue(server.takeRequest().body.readUtf8().contains("media_signature"))
            assertEquals(2, signer.payloads.size)
            assertTrue(signer.payloads[0].contains("\"stage\":\"face\""))
            assertTrue(signer.payloads[1].contains("\"attempt_id\":\"vc_test\""))
            assertTrue(signer.payloads[1].contains("\"audio_offset_ms\":null"))
        } finally { server.shutdown() }
    }

    @Test
    fun missingServerNonceIsAnErrorWithoutUnsignedUpload() = runTest {
        val server = MockWebServer().apply { start() }
        try {
            server.enqueue(MockResponse().setBody(response(false)))
            val flow = LiveFlow(SessionApi(server.url("/").toString()), Signer())
            assertEquals(ApiError.BadResponse, flow.ensureSession(null, "onboarding"))
            assertEquals(null, flow.session)
        } finally { server.shutdown() }
    }
}
