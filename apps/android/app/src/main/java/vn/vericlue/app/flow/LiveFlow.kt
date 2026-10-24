package vn.vericlue.app.flow

import java.io.File
import vn.vericlue.app.capture.CamProbe
import vn.vericlue.app.capture.RegionFrame
import vn.vericlue.app.data.api.ApiError
import vn.vericlue.app.data.api.ApiResult
import vn.vericlue.app.data.api.Challenge
import vn.vericlue.app.data.api.ColorEvent
import vn.vericlue.app.data.api.CreateSessionResponse
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
class LiveFlow(private val api: SessionApi) {
    var session: CreateSessionResponse? = null
        private set
    var challenge: Challenge? = null
        private set
    var frontalJpeg: ByteArray? = null
    val colorEvents = mutableListOf<ColorEvent>()
    var voicePrompt: String? = null
        private set
    var retryHint: String? = null
        private set
    var attemptsLeft: Int? = null
        private set

    /** WAV waiting to be sent from the upload screen. Kept until the server accepts it, so a retry can resend it. */
    var pendingWav: ByteArray? = null

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
        voicePrompt = null
        retryHint = null
        attemptsLeft = null
        pendingWav = null
        mediaAcked = false
        signalsAcked = false
        voiceChecked = false
    }

    /**
     * Drops everything captured in the current face attempt. Stage A data would be kept, but the
     * API cannot issue a fresh challenge on its own yet (LIVE-06), so a live run starts a new session.
     */
    fun dropFaceAttempt() {
        frontalJpeg = null
        colorEvents.clear()
        pendingWav = null
        session = null
        challenge = null
        mediaAcked = false
        signalsAcked = false
        voiceChecked = false
    }

    suspend fun ensureSession(mockScenario: String?): ApiError? {
        if (session != null) return null
        return when (val r = api.createSession(mockScenario)) {
            is ApiResult.Ok -> {
                session = r.value
                challenge = r.value.challenge
                null
            }
            is ApiResult.Err -> r.error
        }
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
        if (!mediaAcked) {
            api.uploadMedia(s.sessionId, s.token, jpeg, video).ackOrFail()?.let { return it }
            mediaAcked = true
            onMediaAcked() // the server has the video: the local copy can go
        }
        if (!signalsAcked) {
            api.sendSignals(s.sessionId, s.token, Signals(colorEvents.toList(), frameTimes, clientQuality, camprobe, regionMeans))
                .ackOrFail()?.let { return it }
            signalsAcked = true
        }
        return when (val r = api.finalize(s.sessionId, s.token)) {
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
                if (f.status == "voice_challenge") voicePrompt = f.voicePrompt ?: return Next.Fail(ApiError.BadResponse)
                FlowRules.routeForStatus(f.status, f.retryHint, inVoiceStep = false)?.let { Next.To(it) } ?: Next.Fail(ApiError.BadResponse)
            }
        }
    }

    suspend fun submitVoice(wav: ByteArray): Next {
        val s = session ?: return Next.Fail(ApiError.Expired)
        if (wav.isEmpty()) return Next.To(Routes.NoVoice)
        return when (val r = api.sendVoice(s.sessionId, s.token, wav, null)) {
            is ApiResult.Err -> Next.Fail(r.error)
            is ApiResult.Ok -> {
                pendingWav = null
                voiceChecked = true
                if (r.value.status == "voice_challenge") voicePrompt = r.value.voicePrompt ?: return Next.Fail(ApiError.BadResponse)
                FlowRules.routeForStatus(r.value.status, null, inVoiceStep = true)?.let { Next.To(it) } ?: Next.Fail(ApiError.BadResponse)
            }
        }
    }

    /**
     * Null when the step counts as received. A 409 means the server already has this step in
     * the attempt (the earlier response was lost), unless the session itself is closed.
     */
    private fun <T> ApiResult<T>.ackOrFail(): Next? {
        val err = this as? ApiResult.Err ?: return null
        if (err.error == ApiError.Conflict && err.code != "session_closed") return null
        return Next.Fail(err.error)
    }
}

/** Error → screen. Every branch is an error screen; none is a pass (AGENTS.md §6 rule 4). */
fun errorRoute(error: ApiError): String = when (error) {
    ApiError.Network -> Routes.ErrorNetwork
    ApiError.Unauthorized, ApiError.Expired -> Routes.ErrorSession
    ApiError.Busy, ApiError.Server -> Routes.ErrorService
    ApiError.Conflict, ApiError.BadResponse -> Routes.ErrorService
}
