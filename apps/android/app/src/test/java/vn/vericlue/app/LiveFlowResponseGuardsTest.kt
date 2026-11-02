package vn.vericlue.app

import java.util.concurrent.TimeUnit
import kotlinx.coroutines.test.runTest
import okhttp3.OkHttpClient
import okhttp3.mockwebserver.MockResponse
import okhttp3.mockwebserver.MockWebServer
import org.junit.Assert.*
import org.junit.Rule
import org.junit.Test
import org.junit.rules.TemporaryFolder
import vn.vericlue.app.data.api.ApiError
import vn.vericlue.app.data.api.SessionApi
import vn.vericlue.app.flow.LiveFlow
import vn.vericlue.app.flow.Next
import vn.vericlue.app.flow.Routes

/** A successful HTTP status alone must never release unacknowledged capture media. */
class LiveFlowResponseGuardsTest {
    @get:Rule val temporary = TemporaryFolder()

    private val mediaAck = """{"step":"media","received":true}"""
    private val signalsAck = """{"step":"signals","received":true}"""
    private val initialPrompt = "Câu đọc thử ban đầu"
    private val nextPrompt = "Câu đọc thử kế tiếp"

    private fun json(body: String, code: Int = 200) = MockResponse().setResponseCode(code).setBody(body)

    private suspend fun withFlow(purpose: String? = "onboarding", block: suspend (MockWebServer, LiveFlow) -> Unit) {
        val server = MockWebServer().apply { start() }
        val http = OkHttpClient.Builder().retryOnConnectionFailure(false)
            .readTimeout(1, TimeUnit.SECONDS).build()
        try {
            val colors = List(8) { """{"rgb":"#ffcc73","hold_ms":450,"transition_ms":150}""" }.joinToString(",")
            val purposeField = purpose?.let { ", \"purpose\":\"$it\"" } ?: ""
            server.enqueue(json("""{"session_id":"ses_guard","token":"token","expires_at":"2030-01-01T00:00:00Z",
                "challenge":{"challenge_id":"ch_guard","baseline_ms":1000,"color_sequence":[$colors]}$purposeField}"""))
            val flow = LiveFlow(SessionApi(server.url("/").toString(), http), mediaSigner = null)
            assertNull(flow.ensureSession(null, purpose))
            flow.frontalJpeg = byteArrayOf(1, 2, 3)
            block(server, flow)
        } finally {
            server.shutdown()
            http.connectionPool.evictAll()
            http.dispatcher.executorService.shutdown()
        }
    }

    private suspend fun requestVoice(server: MockWebServer, flow: LiveFlow) {
        server.enqueue(json(mediaAck))
        server.enqueue(json(signalsAck))
        server.enqueue(json("""{"status":"voice_challenge","voice_prompt":"$initialPrompt","voice_challenge_id":"vc_initial"}"""))
        assertEquals(Next.To(Routes.Voice), flow.submitFace(null, emptyList(), emptyMap()))
    }

    @Test fun malformedMediaAcknowledgmentKeepsTheVideoAndStopsThePipeline() = runTest {
        for (ack in listOf(
            """{"step":"media","received":false}""",
            """{"step":"signals","received":true}""",
            """{"step":"media"}""",
        )) withFlow { server, flow ->
            val video = temporary.newFile().apply { writeBytes(byteArrayOf(4, 5)) }
            var released = 0
            server.enqueue(json(ack))
            server.enqueue(json(signalsAck))
            server.enqueue(json("""{"status":"pass"}"""))
            assertEquals(Next.Fail(ApiError.BadResponse), flow.submitFace(video, emptyList(), emptyMap(),
                onMediaAcked = { released++; video.delete() }))
            assertFalse(flow.mediaAcked)
            assertFalse(flow.signalsAcked)
            assertEquals(0, released)
            assertTrue(video.exists())
            assertEquals("Only create and media may have been sent", 2, server.requestCount)
        }
    }

    @Test fun malformedSignalsAcknowledgmentDoesNotReachFinalize() = runTest {
        for (ack in listOf(
            """{"step":"signals","received":false}""",
            """{"step":"media","received":true}""",
            """{"step":"signals"}""",
        )) withFlow { server, flow ->
            var released = 0
            server.enqueue(json(mediaAck))
            server.enqueue(json(ack))
            server.enqueue(json("""{"status":"pass"}"""))
            assertEquals(Next.Fail(ApiError.BadResponse), flow.submitFace(null, emptyList(), emptyMap(),
                onMediaAcked = { released++ }))
            assertTrue(flow.mediaAcked)
            assertFalse(flow.signalsAcked)
            assertEquals(1, released)
            assertEquals("An unacknowledged signal step must not finalize", 3, server.requestCount)
        }
    }

    @Test fun validAcknowledgmentsReleaseMediaOnceAndKeepTheServerRoute() = runTest {
        withFlow { server, flow ->
            var released = 0
            server.enqueue(json(mediaAck))
            server.enqueue(json(signalsAck))
            server.enqueue(json("""{"status":"review"}"""))
            assertEquals(Next.To(Routes.Review), flow.submitFace(null, emptyList(), emptyMap(),
                onMediaAcked = { released++ }))
            assertTrue(flow.mediaAcked)
            assertTrue(flow.signalsAcked)
            assertEquals(1, released)
            assertEquals(4, server.requestCount)
        }
    }

    @Test fun duplicateStepReceiptsStillRecoverALostAcknowledgment() = runTest {
        withFlow { server, flow ->
            var released = 0
            repeat(2) { server.enqueue(json("""{"error_code":"step_already_received","message":"received"}""", 409)) }
            server.enqueue(json("""{"status":"review"}"""))
            assertEquals(Next.To(Routes.Review), flow.submitFace(null, emptyList(), emptyMap(),
                onMediaAcked = { released++ }))
            assertTrue(flow.mediaAcked)
            assertTrue(flow.signalsAcked)
            assertEquals(1, released)
        }
    }

    private suspend fun rejectsVoiceWithoutMutation(reply: String, purpose: String? = "onboarding") {
        withFlow(purpose) { server, flow ->
            requestVoice(server, flow)
            val wav = byteArrayOf(6, 7, 8)
            flow.pendingWav = wav
            val video = temporary.newFile().apply { writeBytes(byteArrayOf(9)) }
            var released = 0
            server.enqueue(json(reply))
            assertEquals(Next.Fail(ApiError.BadResponse), flow.submitVoice(wav, video,
                onAccepted = { released++; video.delete() }))
            assertSame("Malformed replies must retain the pending WAV", wav, flow.pendingWav)
            assertFalse(flow.voiceChecked)
            assertNull(flow.accountReceipt)
            assertEquals(initialPrompt, flow.voicePrompt)
            assertEquals("vc_initial", flow.voiceChallengeId)
            assertEquals(0, released)
            assertTrue(video.exists())
            assertEquals(5, server.requestCount)
        }
    }

    @Test fun unknownVoiceStatusesKeepThePendingRecording() = runTest {
        for (status in listOf("unknown", "error", "degraded", "retry", "recovery_required")) {
            rejectsVoiceWithoutMutation("""{"status":"$status"}""")
        }
    }

    @Test fun rereadWithoutANonblankPromptKeepsThePendingRecordingAndOldChallenge() = runTest {
        for (prompt in listOf("null", "\"\"", "\"   \"")) {
            rejectsVoiceWithoutMutation("""{"status":"voice_challenge","voice_prompt":$prompt,"voice_challenge_id":"vc_next"}""")
        }
    }

    @Test fun purposeRereadRequiresANonblankChallengeIdBeforeReleasingMedia() = runTest {
        for (id in listOf("null", "\"\"", "\"   \"")) {
            rejectsVoiceWithoutMutation("""{"status":"voice_challenge","voice_prompt":"$nextPrompt","voice_challenge_id":$id}""")
        }
    }

    @Test fun legacyRereadAlsoRejectsABlankPrompt() = runTest {
        rejectsVoiceWithoutMutation("""{"status":"voice_challenge","voice_prompt":"   "}""", purpose = null)
    }

    @Test fun validTerminalVoiceStatusesCommitStateOnlyOnceAndKeepTheirRoutes() = runTest {
        for ((status, route) in listOf("pass" to Routes.Success, "review" to Routes.Review, "deny" to Routes.Deny)) {
            withFlow { server, flow ->
                requestVoice(server, flow)
                val wav = byteArrayOf(6, 7)
                flow.pendingWav = wav
                var released = 0
                server.enqueue(json("""{"status":"$status"}"""))
                assertEquals(Next.To(route), flow.submitVoice(wav, onAccepted = { released++ }))
                assertNull(flow.pendingWav)
                assertTrue(flow.voiceChecked)
                assertEquals(1, released)
                assertEquals(initialPrompt, flow.voicePrompt)
                assertEquals("vc_initial", flow.voiceChallengeId)
            }
        }
    }

    @Test fun validPurposeRereadCommitsTheNewChallengeBeforeAcceptanceCallback() = runTest {
        withFlow { server, flow ->
            requestVoice(server, flow)
            val wav = byteArrayOf(6, 7)
            flow.pendingWav = wav
            var callbackChallenge: Pair<String?, String?>? = null
            server.enqueue(json("""{"status":"voice_challenge","voice_prompt":"$nextPrompt","voice_challenge_id":"vc_next"}"""))
            assertEquals(Next.To(Routes.VoiceAgain), flow.submitVoice(wav,
                onAccepted = { callbackChallenge = flow.voicePrompt to flow.voiceChallengeId }))
            assertEquals(nextPrompt to "vc_next", callbackChallenge)
            assertNull(flow.pendingWav)
            assertTrue(flow.voiceChecked)
        }
    }

    @Test fun legacyRereadCanOmitThePurposeOnlyChallengeId() = runTest {
        withFlow(purpose = null) { server, flow ->
            requestVoice(server, flow)
            val wav = byteArrayOf(6, 7)
            flow.pendingWav = wav
            var released = 0
            server.enqueue(json("""{"status":"voice_challenge","voice_prompt":"$nextPrompt"}"""))
            assertEquals(Next.To(Routes.VoiceAgain), flow.submitVoice(wav, onAccepted = { released++ }))
            assertEquals(nextPrompt, flow.voicePrompt)
            assertNull(flow.voiceChallengeId)
            assertNull(flow.pendingWav)
            assertTrue(flow.voiceChecked)
            assertEquals(1, released)
        }
    }
}
