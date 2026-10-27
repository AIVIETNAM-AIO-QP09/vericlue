package vn.vericlue.app.flow

import java.io.File
import java.security.SecureRandom
import java.util.Base64
import vn.vericlue.app.capture.CamProbe
import vn.vericlue.app.capture.RegionFrame
import vn.vericlue.app.data.api.ApiError
import vn.vericlue.app.data.api.ApiResult
import vn.vericlue.app.data.api.Challenge
import vn.vericlue.app.data.api.ColorEvent
import vn.vericlue.app.data.api.CreateSessionResponse
import vn.vericlue.app.data.api.CreateSessionRequest
import vn.vericlue.app.data.api.IdCardFields
import vn.vericlue.app.data.api.FrameTime
import vn.vericlue.app.data.api.SessionApi
import vn.vericlue.app.data.api.Signals
import vn.vericlue.app.capture.VideoResult

/** Where the flow goes after a server call: a route, or an error screen. */
sealed interface Next {
    data class To(val route: String) : Next
    data class Fail(val error: ApiError) : Next
}

/**
 * Talks to the session API for one verification (APP-01 vertical slice):
 * create session → media → signals → finalize → (voice). The server decides; this class only
 * carries data and maps statuses to screens. Anything unexpected becomes [Next.Fail].
 */
class LiveFlow(private val api: SessionApi) {
    var session: CreateSessionResponse? = null
        private set
    var challenge: Challenge? = null
        private set
    var frontalJpeg: ByteArray? = null
    val colorEvents = mutableListOf<ColorEvent>()
    var voicePrompt: String? = null
        private set

    /** Sessions with a purpose (FLOW-01): the id that must come back with the voice step. */
    var voiceChallengeId: String? = null
        private set
    var retryHint: String? = null
        private set
    var attemptsLeft: Int? = null
        private set

    /** WAV waiting to be sent from the upload screen. Kept until the server accepts it, so a retry can resend it. */
    var pendingWav: ByteArray? = null

    /** When the WAV started, from the reading video's first frame (ms); sent with that video. */
    var audioOffsetMs: Int? = null

    /** Steps the server already received in this attempt; a retry skips them (a second send is 409). */
    var mediaAcked = false
        private set
    var signalsAcked = false
        private set

    /** The server received and checked a voice recording in this session. */
    var voiceChecked = false
        private set

    fun reset() {
        session = null
        challenge = null
        frontalJpeg = null
        colorEvents.clear()
        otpSms = null
        idFields = null
        voicePrompt = null
        voiceChallengeId = null
        retryHint = null
        attemptsLeft = null
        pendingWav = null
        mediaAcked = false
        signalsAcked = false
        voiceChecked = false
    }

    /**
     * Drops everything captured in the current face attempt. The session (and its stage A data)
     * stays; [prepareFace] asks the server for a fresh challenge before the next attempt.
     */
    fun dropFaceAttempt() {
        frontalJpeg = null
        colorEvents.clear()
        pendingWav = null
        mediaAcked = false
        signalsAcked = false
        voiceChecked = false
    }

    /**
     * Starts the session once. [purpose] ("onboarding", "reauth", "recovery") asks for the FLOW-01
     * flow: a `dynamic` schedule for onboarding/recovery, purpose rules on the server. Null keeps the
     * old MVP session.
     */
    suspend fun ensureSession(mockScenario: String?, purpose: String? = null): ApiError? {
        if (session != null) return null
        val request = purpose?.let { CreateSessionRequest(it, newNonce()) }
        return when (val r = api.createSession(mockScenario, request)) {
            is ApiResult.Ok -> {
                session = r.value
                challenge = r.value.challenge
                null
            }
            is ApiResult.Err -> r.error
        }
    }

    /**
     * Before each face attempt: a new session, or a fresh challenge with the token extended when the
     * session already exists (stage A took time, a retry, or a redo after an interruption).
     */
    suspend fun prepareFace(mockScenario: String?, purpose: String? = null): ApiError? {
        val s = session ?: return ensureSession(mockScenario, purpose)
        return when (val r = api.refreshChallenge(s.sessionId, s.token)) {
            is ApiResult.Ok -> {
                // The old token stops working (PLAT-06): carry on with the new one.
                session = s.copy(token = r.value.token, expiresAt = r.value.expiresAt)
                challenge = r.value.challenge
                colorEvents.clear()
                        mediaAcked = false
                signalsAcked = false
                voiceChecked = false
                null
            }
            is ApiResult.Err -> r.error
        }
    }

    // --- Stage A: OTP (FLOW-02), ID card (FLOW-03) ------------------------------------------

    /** Text of the simulated SMS (demo channel only). */
    var otpSms: String? = null
        private set

    /** Fields the server read from the ID card QR. */
    var idFields: IdCardFields? = null
        private set

    /** Starts the session if needed and asks for a code. Null = sent. */
    suspend fun sendOtp(phone: String, mockScenario: String?, purpose: String? = null): ApiError? {
        ensureSession(mockScenario, purpose)?.let { return it }
        val s = session ?: return ApiError.Expired
        return when (val r = api.sendOtp(s.sessionId, s.token, phone)) {
            is ApiResult.Ok -> {
                otpSms = r.value.simulatedSms
                null
            }
            is ApiResult.Err -> r.error
        }
    }

    /** Pass = true; a wrong code gives the attempts left; anything else is an error (expired, locked). */
    sealed interface OtpResult {
        data object Pass : OtpResult
        data class Wrong(val attemptsLeft: Int) : OtpResult
        data class Fail(val error: ApiError, val code: String?) : OtpResult
    }

    suspend fun verifyOtp(code: String): OtpResult {
        val s = session ?: return OtpResult.Fail(ApiError.Expired, null)
        return when (val r = api.verifyOtp(s.sessionId, s.token, code)) {
            is ApiResult.Ok -> if (r.value.status == "pass") OtpResult.Pass else OtpResult.Wrong(r.value.attemptsLeft)
            is ApiResult.Err -> OtpResult.Fail(r.error, r.code)
        }
    }

    /** Sends both photos and the QR text. Returns null when the server read the card, else a retry hint or error. */
    suspend fun sendIdCard(front: ByteArray, back: ByteArray, qr: String?): Pair<String?, ApiError?> {
        val s = session ?: return null to ApiError.Expired
        return when (val r = api.uploadIdCard(s.sessionId, s.token, front, back, qr)) {
            is ApiResult.Ok -> {
                idFields = r.value.fields
                if (r.value.status == "ok") null to null else (r.value.retryHint ?: "QR_UNREADABLE") to null
            }
            is ApiResult.Err -> null to r.error
        }
    }

    /** Null when the server took the fields; otherwise the error with its code (e.g. 422 `identity_incomplete`). */
    suspend fun confirmIdCard(fields: IdCardFields): ApiResult.Err? {
        val s = session ?: return ApiResult.Err(ApiError.Expired)
        val error = api.confirmIdCard(s.sessionId, s.token, fields) as? ApiResult.Err
        if (error == null) idFields = fields
        return error
    }

    /**
     * Sends the face part and returns the next screen. Calling it again after a failure (the
     * "Thử lại" button) only sends the steps the server has not acknowledged yet.
     */
    suspend fun submitFace(
        video: File?,
        frameTimes: List<FrameTime>,
        clientQuality: Map<String, String>,
        camprobe: CamProbe? = null,
        regionMeans: List<RegionFrame>? = null,
        onMediaAcked: () -> Unit = {},
    ): Next {
        val s = session ?: return Next.Fail(ApiError.Expired)
        val jpeg = frontalJpeg ?: return Next.Fail(ApiError.BadResponse)
        val challengeId = challenge?.challengeId
        if (!mediaAcked) {
            api.uploadMedia(s.sessionId, s.token, jpeg, video, challengeId).ackOrFail()?.let { return it }
            mediaAcked = true
            onMediaAcked() // the server has the video: the local copy can go
        }
        if (!signalsAcked) {
            api.sendSignals(s.sessionId, s.token, Signals(colorEvents.toList(), frameTimes, clientQuality, camprobe, regionMeans, challengeId))
                .ackOrFail()?.let { return it }
            signalsAcked = true
        }
        return when (val r = api.finalize(s.sessionId, s.token, challengeId)) {
            is ApiResult.Err -> Next.Fail(r.error)
            is ApiResult.Ok -> {
                val f = r.value
                if (f.status == "retry") {
                    // A retry comes with a fresh challenge for the next attempt (contract).
                    challenge = f.challenge ?: return Next.Fail(ApiError.BadResponse)
                    colorEvents.clear()
                                frontalJpeg = null
                    mediaAcked = false
                    signalsAcked = false
                }
                retryHint = f.retryHint
                attemptsLeft = f.attemptsLeft
                if (f.status == "voice_challenge") {
                    voicePrompt = f.voicePrompt ?: return Next.Fail(ApiError.BadResponse)
                    voiceChallengeId = f.voiceChallengeId
                    if (s.purpose != null && voiceChallengeId == null) return Next.Fail(ApiError.BadResponse)
                }
                FlowRules.routeForStatus(f.status, f.retryHint, inVoiceStep = false)?.let { Next.To(it) } ?: Next.Fail(ApiError.BadResponse)
            }
        }
    }

    /**
     * Sends the reading: the WAV, plus the MP4 recorded over the same span when there is one
     * (lip sync, VOICE-05). [onAccepted] runs once the server has both, so the local video can go.
     */
    suspend fun submitVoice(wav: ByteArray, video: File? = null, audioOffsetMs: Int? = null, onAccepted: () -> Unit = {}): Next {
        val s = session ?: return Next.Fail(ApiError.Expired)
        if (wav.isEmpty()) return Next.To(Routes.NoVoice)
        return when (val r = api.sendVoice(s.sessionId, s.token, wav, video, audioOffsetMs, voiceChallengeId)) {
            is ApiResult.Err -> Next.Fail(r.error)
            is ApiResult.Ok -> {
                pendingWav = null
                voiceChecked = true
                onAccepted()
                if (r.value.status == "voice_challenge") {
                    // A re-read has a new sentence and a new id; the old recording cannot be resent.
                    voicePrompt = r.value.voicePrompt ?: return Next.Fail(ApiError.BadResponse)
                    voiceChallengeId = r.value.voiceChallengeId
                }
                FlowRules.routeForStatus(r.value.status, null, inVoiceStep = true)?.let { Next.To(it) } ?: Next.Fail(ApiError.BadResponse)
            }
        }
    }

    /**
     * Null when the step counts as received: OK, or 409 `step_already_received` (the server has this
     * step of the attempt, the earlier response was lost). Any other 409 (closed session, stale or
     * expired challenge) is an error.
     */
    private fun <T> ApiResult<T>.ackOrFail(): Next? {
        val err = this as? ApiResult.Err ?: return null
        if (err.error == ApiError.Conflict && err.code == "step_already_received") return null
        // Nothing of this attempt reached the server yet: a fresh challenge and a new recording fix it.
        if (err.error == ApiError.Conflict && err.code == "challenge_expired" && !mediaAcked) return Next.To(Routes.FaceExpired)
        return Next.Fail(err.error)
    }

    private fun newNonce(): String {
        val bytes = ByteArray(18).also { SecureRandom().nextBytes(it) }
        return "app_" + Base64.getUrlEncoder().withoutPadding().encodeToString(bytes)
    }
}

/** Do not start any upload while the recording is still being finalized locally. */
internal suspend fun submitWithVideo(video: VideoResult, submit: suspend (File?) -> Next): Next = when (video) {
    is VideoResult.Ready -> submit(video.file)
    VideoResult.NotRecorded -> submit(null)
    VideoResult.Timeout -> Next.To(Routes.UploadFailed)
}

/** Error → screen. Every branch is an error screen; none is a pass (AGENTS.md §6 rule 4). */
fun errorRoute(error: ApiError): String = when (error) {
    ApiError.Network -> Routes.ErrorNetwork
    ApiError.Unauthorized, ApiError.Expired -> Routes.ErrorSession
    ApiError.Busy, ApiError.Server -> Routes.ErrorService
    ApiError.Conflict, ApiError.BadResponse -> Routes.ErrorService
}
