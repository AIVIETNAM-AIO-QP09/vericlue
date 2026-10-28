package vn.vericlue.app

import kotlinx.coroutines.test.runTest
import okhttp3.mockwebserver.MockResponse
import okhttp3.mockwebserver.MockWebServer
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test
import vn.vericlue.app.data.api.Challenge
import vn.vericlue.app.data.api.CreateSessionResponse
import vn.vericlue.app.data.api.SessionApi
import vn.vericlue.app.flow.LiveFlow
import vn.vericlue.app.flow.Routes
import vn.vericlue.app.flow.errorRoute
import vn.vericlue.app.security.MediaProof

class AccountRoutingRegressionTest {
    @Test fun anExistingSessionCannotBeReusedForADifferentPurpose() = runTest {
        val server = MockWebServer().apply { start() }
        try {
            server.enqueue(MockResponse().setBody("""{"session_id":"ses_test","token":"token","expires_at":"expiry","purpose":"onboarding","challenge":{"challenge_id":"ch_test","color_sequence":[]}}"""))
            val live = LiveFlow(SessionApi(server.url("/").toString()), mediaSigner = null)
            assertNull(live.ensureSession(null, "onboarding"))
            assertEquals(vn.vericlue.app.data.api.ApiError.BadResponse, live.ensureSession(null, "recovery"))
            assertEquals(1, server.requestCount)
        } finally { server.shutdown() }
    }

    @Test fun recoveryRequiredFromHttpDoesNotBecomeServiceDown() = runTest {
        val server = MockWebServer().apply { start() }
        try {
            server.enqueue(MockResponse().setResponseCode(409)
                .setBody("""{"error_code":"recovery_required","message":"retry"}"""))
            val live = LiveFlow(SessionApi(server.url("/").toString()), mediaSigner = null)
            assertEquals(Routes.RecoveryRequired, errorRoute(live.ensureSession(null, "onboarding")!!))
        } finally { server.shutdown() }
    }

    @Test fun reauthCanSignTheSameManifestContextAsTheServerVerifier() {
        val challenge = Challenge("ch_test", colorSequence = emptyList(), mediaNonce = "0".repeat(64))
        val session = CreateSessionResponse("ses_test", "token", "expiry", challenge, "reauth", "synthetic_nonce_1234")
        val payload = MediaProof.manifest(session, challenge, "face", challenge.challengeId,
            mapOf("image" to MediaProof.digest("face.jpg", byteArrayOf(1))))
        assertTrue(payload.toString(Charsets.US_ASCII).contains("\"purpose\":\"reauth\""))
    }
}
