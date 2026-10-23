package vn.vericlue.app

import kotlinx.coroutines.test.runTest
import okhttp3.mockwebserver.MockResponse
import okhttp3.mockwebserver.MockWebServer
import org.junit.After
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Before
import org.junit.Test
import vn.vericlue.app.data.api.ApiError
import vn.vericlue.app.data.api.SessionApi
import vn.vericlue.app.flow.LiveFlow
import vn.vericlue.app.flow.Next
import vn.vericlue.app.flow.Routes

class LiveFlowTest {
    private lateinit var server: MockWebServer
    private lateinit var flow: LiveFlow

    private val session = """
        {"session_id":"ses_1","token":"tok_1","expires_at":"2026-10-23T10:00:00Z",
         "challenge":{"challenge_id":"ch_1","baseline_ms":1000,
           "color_sequence":[${List(8) { """{"rgb":"#ffcc73","hold_ms":450,"transition_ms":150}""" }.joinToString(",")}]}}
    """.trimIndent()
    private val ack = """{"step":"media","received":true}"""

    @Before
    fun setUp() {
        server = MockWebServer().apply { start() }
        flow = LiveFlow(SessionApi(server.url("/").toString()))
    }

    @After
    fun tearDown() = server.shutdown()

    private fun json(body: String, code: Int = 200) = MockResponse().setResponseCode(code).setBody(body)

    private suspend fun startAndCapture() {
        server.enqueue(json(session))
        assertEquals(null, flow.ensureSession("genuine"))
        flow.frontalJpeg = byteArrayOf(1, 2, 3)
    }

    @Test
    fun passGoesToSuccessAndSendsTokenAndScenario() = runTest {
        startAndCapture()
        server.enqueue(json(ack))
        server.enqueue(json("""{"step":"signals","received":true}"""))
        server.enqueue(json("""{"status":"pass"}"""))
        val next = flow.submitFace(null, emptyList(), emptyMap())
        assertEquals(Next.To(Routes.Success), next)
        val create = server.takeRequest()
        assertEquals("/v1/sessions", create.path)
        assertEquals("genuine", create.getHeader("X-Mock-Scenario"))
        val media = server.takeRequest()
        assertEquals("/v1/sessions/ses_1/media", media.path)
        assertEquals("Bearer tok_1", media.getHeader("Authorization"))
    }

    @Test
    fun voiceChallengeCarriesThePrompt() = runTest {
        startAndCapture()
        server.enqueue(json(ack))
        server.enqueue(json(ack))
        server.enqueue(json("""{"status":"voice_challenge","voice_prompt":"Tôi xác nhận mở tài khoản"}"""))
        assertEquals(Next.To(Routes.Voice), flow.submitFace(null, emptyList(), emptyMap()))
        assertEquals("Tôi xác nhận mở tài khoản", flow.voicePrompt)
    }

    @Test
    fun unknownStatusIsAnErrorNotAPass() = runTest {
        startAndCapture()
        server.enqueue(json(ack))
        server.enqueue(json(ack))
        server.enqueue(json("""{"status":"degraded"}"""))
        assertTrue(flow.submitFace(null, emptyList(), emptyMap()) is Next.Fail)
    }

    @Test
    fun brokenJsonAndHttpErrorsAreErrors() = runTest {
        startAndCapture()
        server.enqueue(json("{not json"))
        assertEquals(Next.Fail(ApiError.BadResponse), flow.submitFace(null, emptyList(), emptyMap()))
        server.enqueue(json("""{"error_code":"expired","message":"x"}""", 401))
        assertEquals(Next.Fail(ApiError.Unauthorized), flow.submitFace(null, emptyList(), emptyMap()))
    }

    @Test
    fun noNetworkIsANetworkError() = runTest {
        server.shutdown()
        assertEquals(ApiError.Network, flow.ensureSession(null))
    }

    @Test
    fun retryWithoutANewChallengeIsAnError() = runTest {
        startAndCapture()
        server.enqueue(json(ack))
        server.enqueue(json(ack))
        server.enqueue(json("""{"status":"retry","retry_hint":"MORE_LIGHT"}"""))
        assertTrue(flow.submitFace(null, emptyList(), emptyMap()) is Next.Fail)
    }
}
