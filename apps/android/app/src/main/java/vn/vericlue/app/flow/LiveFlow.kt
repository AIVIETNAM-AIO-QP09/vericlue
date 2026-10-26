package vn.vericlue.app.flow

import java.io.File
import java.security.SecureRandom
import java.util.Base64
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import vn.vericlue.app.security.MediaSigner
import vn.vericlue.app.security.MediaProof
import vn.vericlue.app.security.AndroidMediaSigner
import vn.vericlue.app.security.DeviceProof
import vn.vericlue.app.BuildConfig
import vn.vericlue.app.capture.CamProbe
import vn.vericlue.app.capture.RegionFrame
import vn.vericlue.app.data.api.ApiError
import vn.vericlue.app.data.api.ApiResult
import vn.vericlue.app.data.api.AccountReceipt
import vn.vericlue.app.data.api.Challenge
import vn.vericlue.app.data.api.ColorEvent
import vn.vericlue.app.data.api.CreateSessionResponse
import vn.vericlue.app.data.api.CreateSessionRequest
import vn.vericlue.app.data.api.IdCardFields
import vn.vericlue.app.data.api.FrameTime
import vn.vericlue.app.data.api.SessionApi
import vn.vericlue.app.data.api.Signals

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
class LiveFlow(
    private val api: SessionApi,
    private val mediaSigner: MediaSigner? = if (BuildConfig.SIGNED_MEDIA) AndroidMediaSigner() else null,
) {
    var session: CreateSessionResponse? = null
        private set
    var challenge: Challenge? = null
        private set
    var accountReceipt: AccountReceipt? = null
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
        accountReceipt = null
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
    suspend fun ensureSession(mockScenario: String?, purpose: String? = null, account: AccountReceipt? = null): ApiError? {
        if (session != null) return null
        if (mediaSigner != null && purpose !in setOf("onboarding", "recovery", "reauth")) return ApiError.BadResponse
        if (purpose == "reauth" && (account == null || mediaSigner == null)) return ApiError.BadResponse
        if (account != null && purpose !in setOf("reauth", "recovery")) return ApiError.BadResponse
        if (account != null && mediaSigner == null) return ApiError.BadResponse
        val spki = if (purpose == "reauth") null else mediaSigner?.let { signer -> withContext(Dispatchers.IO) {
            runCatching { signer.publicKeySpki }.getOrNull()
        } }
        if (mediaSigner != null && spki == null && purpose != "reauth") return ApiError.Server
        val nonce = newNonce()
        val request = purpose?.let { CreateSessionRequest(it, nonce, spki, account?.accountId, account?.deviceId?.takeIf { purpose == "reauth" }) }
        return when (val r = api.createSession(mockScenario, request)) {
            is ApiResult.Ok -> {
                if (mediaSigner != null && r.value.challenge.mediaNonce == null) return ApiError.BadResponse
                if (purpose == "reauth") {
                    val signature = withContext(Dispatchers.IO) {
                        runCatching { requireNotNull(mediaSigner).sign(DeviceProof.payload(r.value, requireNotNull(account), nonce)) }.getOrNull()
                    } ?: return ApiError.BadResponse
                    when (val proof = api.proveDevice(r.value.sessionId, r.value.token, signature)) {
                        is ApiResult.Err -> return proof.error
                        is ApiResult.Ok -> if (!proof.value.received) return ApiError.BadResponse
                    }
                } else if (r.value.deviceChallenge != null) return ApiError.BadResponse
                session = r.value
                challenge = r.value.challenge
                null
            }
            is ApiResult.Err -> r.error
        }
    }

    /** Recover a committed receipt after the voice HTTP response was lost. No biometrics returned. */
    suspend fun fetchAccountReceipt(): ApiError? {
        val current = session ?: return ApiError.BadResponse
        return when (val result = api.accountReceipt(current.sessionId, current.token)) {
            is ApiResult.Err -> result.error
            is ApiResult.Ok -> { accountReceipt = result.value; null }
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
                if (mediaSigner != null && r.value.challenge.mediaNonce == null) return ApiError.BadResponse
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

    suspend fun confirmIdCard(fields: IdCardFields): ApiError? {
        val s = session ?: return ApiError.Expired
        val error = (api.confirmIdCard(s.sessionId, s.token, fields) as? ApiResult.Err)?.error
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
            val proof = withContext(Dispatchers.IO) { runCatching {
                mediaSigner?.let { signer ->
                    val c = requireNotNull(challenge)
                    val files = mutableMapOf("image" to MediaProof.digest("face.jpg", jpeg))
                    video?.let { files["video"] = MediaProof.digest(it) }
                    signer.sign(MediaProof.manifest(s, c, "face", c.challengeId, files))
                }
            } }
            if (proof.isFailure) return Next.Fail(ApiError.Server)
            api.uploadMedia(s.sessionId, s.token, jpeg, video, challengeId, proof.getOrNull()).ackOrFail()?.let { return it }
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
        val proof = withContext(Dispatchers.IO) { runCatching {
            mediaSigner?.let { signer ->
                val files = mutableMapOf("audio" to MediaProof.digest("voice.wav", wav))
                video?.let { files["video"] = MediaProof.digest(it) }
                signer.sign(MediaProof.manifest(s, requireNotNull(challenge), "voice",
                    requireNotNull(voiceChallengeId), files,
                    if (video != null) audioOffsetMs?.coerceIn(-5000, 5000) else null))
            }
        } }
        if (proof.isFailure) return Next.Fail(ApiError.Server)
        return when (val r = api.sendVoice(s.sessionId, s.token, wav, video, audioOffsetMs, voiceChallengeId, proof.getOrNull())) {
            is ApiResult.Err -> Next.Fail(r.error)
            is ApiResult.Ok -> {
                pendingWav = null
                voiceChecked = true
                if (r.value.status == "pass") accountReceipt = r.value.account
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
        return Next.Fail(err.error)
    }

    private fun newNonce(): String {
        val bytes = ByteArray(18).also { SecureRandom().nextBytes(it) }
        return "app_" + Base64.getUrlEncoder().withoutPadding().encodeToString(bytes)
    }
}

/** Error → screen. Every branch is an error screen; none is a pass (AGENTS.md §6 rule 4). */
fun errorRoute(error: ApiError): String = when (error) {
    ApiError.Network -> Routes.ErrorNetwork
    ApiError.Unauthorized, ApiError.Expired -> Routes.ErrorSession
    ApiError.Busy, ApiError.Server -> Routes.ErrorService
    ApiError.Conflict, ApiError.BadResponse -> Routes.ErrorService
}
