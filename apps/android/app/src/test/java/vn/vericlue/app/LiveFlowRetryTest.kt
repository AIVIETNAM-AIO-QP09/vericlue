package vn.vericlue.app

import java.util.concurrent.TimeUnit
import kotlinx.coroutines.test.runTest
import okhttp3.OkHttpClient
import okhttp3.mockwebserver.MockResponse
import okhttp3.mockwebserver.MockWebServer
import okhttp3.mockwebserver.SocketPolicy
import org.junit.After
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNotEquals
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Before
import org.junit.Test
import vn.vericlue.app.data.api.ApiError
import vn.vericlue.app.data.api.SessionApi
import vn.vericlue.app.flow.LiveFlow
import vn.vericlue.app.flow.Next
import vn.vericlue.app.flow.Routes

/** Retry after a failed step resends only what the server has not acknowledged, and never turns into a pass. */
class LiveFlowRetryTest {
    private lateinit var server: MockWebServer
    private lateinit var flow: LiveFlow

    private val challenge = """
        {"challenge_id":"ch_1","baseline_ms":1000,
         "color_sequence":[${List(8) { """{"rgb":"#ffcc73","hold_ms":450,"transition_ms":150}""" }.joinToString(",")}]}
    """.trimIndent()
    private val session = """{"session_id":"ses_1","token":"tok_1","expires_at":"2026-10-23T10:00:00Z","challenge":$challenge}"""
    private val mediaAck = """{"step":"media","received":true}"""
    private val signalsAck = """{"step":"signals","received":true}"""
    private val pass = """{"status":"pass"}"""

    private val createPath = "/v1/sessions"
    private val mediaPath = "/v1/sessions/ses_1/media"
    private val signalsPath = "/v1/sessions/ses_1/signals"
    private val finalizePath = "/v1/sessions/ses_1/finalize"
    private val voicePath = "/v1/sessions/ses_1/voice"

    @Before
    fun setUp() {
        server = MockWebServer().apply { start() }
        flow = newFlow(server)
    }

    @After
    fun tearDown() = server.shutdown()

    // No silent OkHttp retry: a dropped connection must reach LiveFlow as a network error.
    private fun newFlow(s: MockWebServer) = LiveFlow(
        SessionApi(s.url("/").toString(), OkHttpClient.Builder().retryOnConnectionFailure(false).build()),
    )

    private fun json(body: String, code: Int = 200) = MockResponse().setResponseCode(code).setBody(body)
    private fun error(code: Int, errorCode: String) = json("""{"error_code":"$errorCode","message":"x"}""", code)

    /** Server reads the request, then drops the connection: the client sees an IOException. */
    private fun dropped() = MockResponse().setSocketPolicy(SocketPolicy.DISCONNECT_AFTER_REQUEST)

    private suspend fun startAndCapture(f: LiveFlow = flow, s: MockWebServer = server) {
        s.enqueue(json(session))
        assertEquals(null, f.ensureSession("genuine"))
        f.frontalJpeg = byteArrayOf(1, 2, 3)
    }

    private suspend fun submit(f: LiveFlow = flow) = f.submitFace(null, emptyList(), emptyMap())

    /** Paths of all requests not yet taken, in order. */
    private fun paths(s: MockWebServer = server): List<String?> =
        generateSequence { s.takeRequest(200, TimeUnit.MILLISECONDS) }.map { it.path }.toList()

    @Test
    fun networkErrorOnMediaResendsMediaThenContinues() = runTest {
        startAndCapture()
        server.enqueue(dropped())
        assertEquals(Next.Fail(ApiError.Network), submit())
        assertFalse(flow.mediaAcked)
        server.enqueue(json(mediaAck))
        server.enqueue(json(signalsAck))
        server.enqueue(json(pass))
        assertEquals(Next.To(Routes.Success), submit())
        assertEquals(listOf(createPath, mediaPath, mediaPath, signalsPath, finalizePath), paths())
    }

    @Test
    fun networkErrorOnSignalsResendsOnlySignals() = runTest {
        startAndCapture()
        server.enqueue(json(mediaAck))
        server.enqueue(dropped())
        assertEquals(Next.Fail(ApiError.Network), submit())
        assertTrue(flow.mediaAcked)
        assertFalse(flow.signalsAcked)
        server.enqueue(json(signalsAck))
        server.enqueue(json(pass))
        assertEquals(Next.To(Routes.Success), submit())
        assertEquals(5, server.requestCount)
        assertEquals(listOf(createPath, mediaPath, signalsPath, signalsPath, finalizePath), paths())
    }

    @Test
    fun networkErrorOnFinalizeRetriesOnlyFinalizeAndConflictIsAFailure() = runTest {
        startAndCapture()
        server.enqueue(json(mediaAck))
        server.enqueue(json(signalsAck))
        server.enqueue(dropped())
        assertEquals(Next.Fail(ApiError.Network), submit())
        server.enqueue(error(409, "already_finalized"))
        val next = submit()
        assertEquals(Next.Fail(ApiError.Conflict), next)
        assertNotEquals(Next.To(Routes.Success), next)
        assertEquals(listOf(createPath, mediaPath, signalsPath, finalizePath, finalizePath), paths())
    }

    @Test
    fun conflictOnMediaResendCountsAsReceived() = runTest {
        startAndCapture()
        server.enqueue(dropped())
        assertEquals(Next.Fail(ApiError.Network), submit())
        server.enqueue(error(409, "step_already_received"))
        server.enqueue(json(signalsAck))
        server.enqueue(json(pass))
        assertEquals(Next.To(Routes.Success), submit())
        assertTrue(flow.mediaAcked)
        assertEquals(listOf(createPath, mediaPath, mediaPath, signalsPath, finalizePath), paths())
    }

    @Test
    fun conflictWithSessionClosedIsAFailure() = runTest {
        startAndCapture()
        server.enqueue(error(409, "session_closed"))
        val next = submit()
        assertEquals(Next.Fail(ApiError.Conflict), next)
        assertFalse(flow.mediaAcked)
        assertEquals(listOf(createPath, mediaPath), paths())
    }

    @Test
    fun retryAfterNetworkErrorNeverPassesOnANonPassStatus() = runTest {
        val finals = listOf(
            """{"status":"retry","challenge":$challenge}""",
            """{"status":"review"}""",
            """{"status":"voice_challenge","voice_prompt":"Tôi xác nhận mở tài khoản"}""",
            """{"status":"degraded"}""",
            """{"status":"error"}""",
        )
        for (failAt in 0..2) for (final in finals) {
            val s = MockWebServer().apply { start() }
            try {
                val f = newFlow(s)
                startAndCapture(f, s)
                val steps = listOf(json(mediaAck), json(signalsAck), json(final))
                steps.take(failAt).forEach(s::enqueue)
                s.enqueue(dropped())
                assertEquals("failAt=$failAt final=$final", Next.Fail(ApiError.Network), submit(f))
                steps.drop(failAt).forEach(s::enqueue)
                val next = submit(f)
                assertNotEquals("failAt=$failAt final=$final", Next.To(Routes.Success), next)
            } finally {
                s.shutdown()
            }
        }
    }

    @Test
    fun voiceNetworkErrorKeepsTheRecordingUntilTheServerAcceptsIt() = runTest {
        startAndCapture()
        server.enqueue(json(mediaAck))
        server.enqueue(json(signalsAck))
        server.enqueue(json("""{"status":"voice_challenge","voice_prompt":"Tôi xác nhận mở tài khoản"}"""))
        assertEquals(Next.To(Routes.Voice), submit())
        val wav = byteArrayOf(9, 8, 7)
        flow.pendingWav = wav
        server.enqueue(dropped())
        assertEquals(Next.Fail(ApiError.Network), flow.submitVoice(wav))
        assertTrue(flow.pendingWav.contentEquals(wav))
        assertFalse(flow.voiceChecked)
        server.enqueue(json(pass))
        assertEquals(Next.To(Routes.Success), flow.submitVoice(flow.pendingWav!!))
        assertNull(flow.pendingWav)
        assertTrue(flow.voiceChecked)
        assertEquals(listOf(createPath, mediaPath, signalsPath, finalizePath, voicePath, voicePath), paths())
    }

    @Test
    fun finalizeRetryResetsAcksSoTheNextAttemptSendsMediaAgain() = runTest {
        startAndCapture()
        server.enqueue(json(mediaAck))
        server.enqueue(json(signalsAck))
        server.enqueue(json("""{"status":"retry","challenge":$challenge}"""))
        assertEquals(Next.To(Routes.RetryChallenge), submit())
        assertFalse(flow.mediaAcked)
        assertFalse(flow.signalsAcked)
        flow.frontalJpeg = byteArrayOf(4, 5, 6)
        server.enqueue(json(mediaAck))
        server.enqueue(json(signalsAck))
        server.enqueue(json(pass))
        assertEquals(Next.To(Routes.Success), submit())
        assertEquals(
            listOf(createPath, mediaPath, signalsPath, finalizePath, mediaPath, signalsPath, finalizePath),
            paths(),
        )
    }

    @Test
    fun localVideoIsReleasedOnlyOnceTheServerHasTheMedia() = runTest {
        startAndCapture()
        var released = 0
        server.enqueue(dropped())
        assertEquals(Next.Fail(ApiError.Network), flow.submitFace(null, emptyList(), emptyMap(), onMediaAcked = { released++ }))
        assertEquals(0, released) // still needed for the retry
        server.enqueue(json(mediaAck))
        server.enqueue(json(signalsAck))
        server.enqueue(json("""{"status":"retry","challenge":$challenge}"""))
        assertEquals(Next.To(Routes.RetryChallenge), flow.submitFace(null, emptyList(), emptyMap(), onMediaAcked = { released++ }))
        assertEquals(1, released) // released even though the retry status resets the acks
    }
}
