package vn.vericlue.app

import kotlinx.coroutines.test.runTest
import kotlinx.coroutines.async
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import kotlinx.coroutines.cancelAndJoin
import java.util.concurrent.TimeUnit
import okhttp3.mockwebserver.MockResponse
import okhttp3.mockwebserver.MockWebServer
import org.junit.Assert.*
import org.junit.Test
import vn.vericlue.app.data.api.*
import vn.vericlue.app.flow.*

class SessionPrivacyTest {
    private val session = CreateSessionResponse("ses_test", "current_token", "expiry", Challenge("ch_test", colorSequence = emptyList()))
    private fun receipt(policy: String = "demo-v1", status: String = "granted", categories: String = "\"contact\",\"id_document\",\"face_biometrics\",\"voice_biometrics\"", scope: String = "session") = """{
        "session_id":"ses_test","scope":"$scope","policy_version":"$policy","status":"$status",
        "categories":[$categories],"consent_receipt_id":"prv_${"a".repeat(32)}","consented_at":"2026-10-30T01:00:00Z",
        "withdrawal_receipt_id":null,"withdrawn_at":null,"storage_erasure":"not_requested",
        "processing_cleanup":"not_applicable","account_data_erased":false,"credential_revocation":"not_performed"} """
    private suspend fun withPrivacy(block: suspend (MockWebServer, SessionPrivacyFlow) -> Unit) {
        val server = MockWebServer().apply { start() }
        try { block(server, SessionPrivacyFlow(SessionApi(server.url("/").toString())) { session }) }
        finally { server.shutdown() }
    }

    @Test fun explicitConsentChecksPolicyBeforeGrantAndKeepsReceipt() = runTest {
        withPrivacy { server, privacy ->
            server.enqueue(MockResponse().setBody(receipt(status = "not_granted", categories = "")))
            server.enqueue(MockResponse().setBody(receipt()))
            assertNull(privacy.grant(Purpose.Onboarding, PrivacyNotice.VERSION))
            assertEquals("/v1/sessions/ses_test/privacy", server.takeRequest().path)
            val grant = server.takeRequest()
            assertEquals("Bearer current_token", grant.getHeader("Authorization"))
            assertTrue(grant.body.readUtf8().contains("\"consent\":true"))
            assertEquals("granted", privacy.receipt?.status)
        }
    }

    @Test fun changedPolicyNeverSilentlyGrantsANewVersion() = runTest {
        withPrivacy { server, privacy ->
            server.enqueue(MockResponse().setBody(receipt(policy = "new-policy")))
            assertEquals(ApiError.BadResponse, privacy.grant(Purpose.Onboarding, PrivacyNotice.VERSION))
            assertEquals(1, server.requestCount)
            assertNull(privacy.receipt)
        }
    }

    @Test fun partialOrWrongScopeReceiptCannotAuthorizeCapture() = runTest {
        for (bad in listOf(receipt(categories = "\"contact\""), receipt(scope = "account"), receipt(status = "unknown"))) {
            withPrivacy { server, privacy ->
                server.enqueue(MockResponse().setBody(receipt(status = "not_granted", categories = "")))
                server.enqueue(MockResponse().setBody(bad))
                assertEquals(ApiError.BadResponse, privacy.grant(Purpose.Onboarding, PrivacyNotice.VERSION))
                assertNull(privacy.receipt)
            }
        }
    }

    @Test fun withdrawalFailureKeepsContextForRetryAndReceiptDoesNotClaimAccountErasure() = runTest {
        withPrivacy { server, privacy ->
            server.enqueue(MockResponse().setResponseCode(503).setBody("""{"error_code":"storage_busy","message":"retry"}"""))
            assertEquals(ApiError.Busy, privacy.withdraw())
            assertTrue(privacy.stopping)
            assertNull(privacy.receipt)
            val withdrawn = receipt(status = "withdrawn").replace("\"withdrawal_receipt_id\":null", "\"withdrawal_receipt_id\":\"prv_${"b".repeat(32)}\"")
                .replace("\"withdrawn_at\":null", "\"withdrawn_at\":\"2026-10-30T01:01:00Z\"").replace("not_requested", "key_destroyed")
            server.enqueue(MockResponse().setBody(withdrawn))
            assertNull(privacy.withdraw())
            assertEquals("key_destroyed", privacy.receipt?.storageErasure)
            assertFalse(privacy.receipt!!.accountDataErased)
            assertEquals(ApiError.Expired, privacy.grant(Purpose.Onboarding, PrivacyNotice.VERSION))
            assertEquals(2, server.requestCount)
        }
    }

    @Test fun accountBoundRecoverySkipsCardAndReauthSkipsPhoneAfterConsent() {
        assertEquals(Routes.FaceReady, FlowRules.afterConsent(Purpose.Reauth))
        assertEquals(Routes.Phone, FlowRules.afterConsent(Purpose.Recovery))
        assertEquals(Routes.FaceReady, FlowRules.afterOtp(Purpose.Recovery, accountBound = true))
        assertEquals(Routes.Uploading, FlowRules.afterFace(Purpose.Recovery, false, true, accountBound = true))
    }

    @Test fun productionFlowDoesNotSendDataBeforeReceipt() = runTest {
        val server = MockWebServer().apply { start() }
        try {
            val live = LiveFlow(SessionApi(server.url("/").toString()), mediaSigner = null, enforcePrivacy = true)
            assertEquals(ApiError.Conflict, live.sendOtp("0912345678", null, "onboarding"))
            assertEquals(ApiError.Conflict, live.prepareFace(null, "onboarding"))
            assertEquals(null to ApiError.Conflict, live.sendIdCard(byteArrayOf(1), null, null))
            assertEquals(Next.Fail(ApiError.Conflict), live.submitVoice(byteArrayOf(1)))
            assertEquals(0, server.requestCount)
        } finally { server.shutdown() }
    }

    @Test fun withdrawalBetweenMediaAndSignalsStopsTheRemainingUpload() = runTest {
        val server = MockWebServer().apply { start() }
        try {
            val live = LiveFlow(SessionApi(server.url("/").toString()), mediaSigner = null)
            server.enqueue(MockResponse().setBody("""{"session_id":"ses_test","token":"token","expires_at":"expiry","challenge":{"challenge_id":"ch_test","color_sequence":[]}}"""))
            assertNull(live.ensureSession(null))
            live.frontalJpeg = byteArrayOf(1)
            server.enqueue(MockResponse().setBody("""{"step":"media","received":true}"""))
            server.enqueue(MockResponse().setResponseCode(503).setBody("""{"error_code":"storage_busy","message":"retry"}"""))
            // Catch any forbidden follow-up without a hanging network call.
            server.enqueue(MockResponse().setBody("""{"step":"signals","received":true}"""))
            server.enqueue(MockResponse().setBody("""{"status":"pass"}"""))
            val next = live.submitFace(null, emptyList(), emptyMap(), onMediaAcked = {
                kotlinx.coroutines.runBlocking { live.privacy.withdraw() }
            })
            assertEquals(Next.Fail(ApiError.Expired), next)
            assertEquals(3, server.requestCount)
        } finally { server.shutdown() }
    }

    @Test fun withdrawalWaitsForCancelledRefreshAndUsesItsNewBearer() = runTest {
        val server = MockWebServer().apply { start() }
        try {
            val live = LiveFlow(SessionApi(server.url("/").toString()), mediaSigner = null)
            server.enqueue(MockResponse().setBody("""{"session_id":"ses_test","token":"old","expires_at":"expiry","challenge":{"challenge_id":"ch_test","color_sequence":[]}}"""))
            live.ensureSession(null)
            server.takeRequest()
            server.enqueue(MockResponse().setBody("""{"token":"new","expires_at":"expiry","challenge":{"challenge_id":"ch_new","color_sequence":[]}}""").setBodyDelay(300, TimeUnit.MILLISECONDS))
            var continuedAfterCancellation = false
            val refresh = async { live.prepareFace(null); continuedAfterCancellation = true }
            withContext(Dispatchers.IO) { checkNotNull(server.takeRequest(5, TimeUnit.SECONDS)) }
            refresh.cancel()
            val withdrawn = receipt(status = "withdrawn").replace("\"withdrawal_receipt_id\":null", "\"withdrawal_receipt_id\":\"prv_${"b".repeat(32)}\"")
                .replace("\"withdrawn_at\":null", "\"withdrawn_at\":\"2026-10-30T01:01:00Z\"").replace("not_requested", "key_destroyed")
            server.enqueue(MockResponse().setBody(withdrawn))
            assertNull(live.privacy.withdraw())
            refresh.cancelAndJoin()
            assertFalse(continuedAfterCancellation)
            assertEquals("Bearer new", server.takeRequest().getHeader("Authorization"))
        } finally { server.shutdown() }
    }
}
