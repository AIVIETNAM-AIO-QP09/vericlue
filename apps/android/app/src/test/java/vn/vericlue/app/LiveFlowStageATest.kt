package vn.vericlue.app

import kotlinx.coroutines.test.runTest
import okhttp3.mockwebserver.MockResponse
import okhttp3.mockwebserver.MockWebServer
import org.junit.After
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Before
import org.junit.Test
import vn.vericlue.app.data.api.ApiError
import vn.vericlue.app.data.api.IdCardFields
import vn.vericlue.app.data.api.SessionApi
import vn.vericlue.app.flow.FlowRules
import vn.vericlue.app.flow.LiveFlow

/** Stage A against the server (OTP, ID card), and a fresh challenge before each face attempt. */
class LiveFlowStageATest {
    private lateinit var server: MockWebServer
    private lateinit var flow: LiveFlow

    private fun challenge(id: String) = """
        {"challenge_id":"$id","baseline_ms":1000,
         "color_sequence":[${List(8) { """{"rgb":"#ffcc73","hold_ms":450,"transition_ms":150}""" }.joinToString(",")}],
         "turn_order":["right","left"],
         "dot_path":[{"t_ms":0,"x":0.2,"y":0.3},{"t_ms":1000,"x":0.8,"y":0.7}]}
    """.trimIndent()
    private val session = """{"session_id":"ses_1","token":"tok_1","expires_at":"2026-10-24T10:00:00Z","challenge":${challenge("ch_1")}}"""

    @Before
    fun setUp() {
        server = MockWebServer().apply { start() }
        flow = LiveFlow(SessionApi(server.url("/").toString()), mediaSigner = null)
    }

    @After
    fun tearDown() = server.shutdown()

    private fun json(body: String, code: Int = 200) = MockResponse().setResponseCode(code).setBody(body)

    @Test
    fun otpStartsTheSessionAndShowsTheSimulatedSms() = runTest {
        server.enqueue(json(session))
        server.enqueue(json("""{"expires_at":"2026-10-24T10:02:00Z","attempts_left":5,"simulated_sms":"VeriClue: Mã xác minh của bạn là 123456."}"""))
        assertNull(flow.sendOtp("0912345678", "genuine"))
        assertEquals("VeriClue: Mã xác minh của bạn là 123456.", flow.otpSms)
        assertEquals("/v1/sessions", server.takeRequest().path)
        val otp = server.takeRequest()
        assertEquals("/v1/sessions/ses_1/otp", otp.path)
        assertEquals("""{"phone":"0912345678"}""", otp.body.readUtf8())
    }

    @Test
    fun otpVerifyMapsPassWrongAndLocked() = runTest {
        server.enqueue(json(session))
        server.enqueue(json("""{"expires_at":"2026-10-24T10:02:00Z","attempts_left":5}"""))
        flow.sendOtp("0912345678", null)
        server.enqueue(json("""{"status":"retry","attempts_left":4}"""))
        assertEquals(LiveFlow.OtpResult.Wrong(4), flow.verifyOtp("000000"))
        server.enqueue(json("""{"error_code":"otp_locked","message":"x"}""", 409))
        assertEquals(LiveFlow.OtpResult.Fail(ApiError.Conflict, "otp_locked"), flow.verifyOtp("000000"))
        server.enqueue(json("""{"status":"pass","attempts_left":4}"""))
        assertEquals(LiveFlow.OtpResult.Pass, flow.verifyOtp("123456"))
    }

    @Test
    fun idCardSendsBothPhotosAndQrAndKeepsTheFields() = runTest {
        server.enqueue(json(session))
        flow.ensureSession(null)
        server.enqueue(json("""{"status":"ok","fields":{"full_name":"Nguyễn Văn An","id_number":"001099012345","date_of_birth":"1995-01-01","sex":"Nam"}}"""))
        assertEquals(null to null, flow.sendIdCard(byteArrayOf(1), byteArrayOf(2), "qr text"))
        assertEquals("001099012345", flow.idFields?.idNumber)
        server.takeRequest()
        val body = server.takeRequest().body.readUtf8()
        assertTrue(body.contains("name=\"front\"") && body.contains("name=\"back\"") && body.contains("qr text"))
        server.enqueue(json("""{"status":"retry","retry_hint":"QR_INVALID"}"""))
        assertEquals("QR_INVALID" to null, flow.sendIdCard(byteArrayOf(1), byteArrayOf(2), null))
    }

    @Test
    fun faceAttemptAfterStageAGetsAFreshChallenge() = runTest {
        server.enqueue(json(session))
        flow.ensureSession(null)
        server.enqueue(json("""{"token":"tok_2","expires_at":"2026-10-24T10:05:00Z","challenge":${challenge("ch_2")}}"""))
        assertNull(flow.prepareFace(null))
        assertEquals("ch_2", flow.challenge?.challengeId)
        server.takeRequest()
        assertEquals("/v1/sessions/ses_1/challenge", server.takeRequest().path)
        // The refresh hands out a new token (PLAT-06): every later call must use it.
        server.enqueue(json("""{"status":"pass","attempts_left":5}"""))
        flow.verifyOtp("123456")
        assertEquals("Bearer tok_2", server.takeRequest().getHeader("Authorization"))
    }

    @Test
    fun purposeSessionSendsPurposeAndNonce() = runTest {
        server.enqueue(json(session))
        assertNull(flow.ensureSession("genuine", "onboarding"))
        val body = server.takeRequest().body.readUtf8()
        assertTrue(body.contains("\"purpose\":\"onboarding\""))
        val nonce = Regex("\"nonce\":\"([^\"]+)\"").find(body)!!.groupValues[1]
        assertTrue(nonce.matches(Regex("[A-Za-z0-9_-]{16,128}")))
    }

    @Test
    fun firstFaceAttemptWithoutStageACreatesTheSession() = runTest {
        server.enqueue(json(session))
        assertNull(flow.prepareFace("genuine"))
        assertEquals("ch_1", flow.challenge?.challengeId)
        assertEquals(1, server.requestCount)
    }

    @Test
    fun onlyRealEditsDifferFromTheQr() {
        val server = IdCardFields("Nguyễn Văn An", "001099012345", "1995-01-01", "Nam", "12 Phố Huế")
        val shown = FlowRules.cccdFrom(server)!!.let {
            listOf(it.fullName.uppercase(), "001 099 012 345", it.dateOfBirth, it.gender, it.address)
        }
        assertEquals(server, FlowRules.confirmedFields(server, shown, shown))
        val edited = shown.toMutableList().apply { this[2] = "02/01/1995"; this[4] = "14 Phố Huế" }
        val out = FlowRules.confirmedFields(server, shown, edited)
        assertEquals("1995-01-02", out.dateOfBirth)
        assertEquals("14 Phố Huế", out.address)
        assertEquals(server.fullName, out.fullName)
    }

    @Test
    fun otpTextsOnlyTalkAboutTheCode() {
        assertEquals("Mã chưa đúng. Bạn còn 3 lần thử.", FlowRules.otpWrongText(3))
        assertTrue(FlowRules.otpErrorText("otp_expired")!!.contains("hết hạn"))
        assertNull(FlowRules.otpErrorText("session_closed"))
    }
}
