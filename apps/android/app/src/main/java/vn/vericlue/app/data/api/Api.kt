package vn.vericlue.app.data.api

import java.io.File
import java.io.IOException
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import kotlinx.serialization.SerialName
import kotlinx.serialization.Serializable
import kotlinx.serialization.SerializationException
import kotlinx.serialization.json.Json
import okhttp3.HttpUrl.Companion.toHttpUrl
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.MultipartBody
import okhttp3.OkHttpClient
import okhttp3.Request
import okhttp3.RequestBody
import okhttp3.RequestBody.Companion.asRequestBody
import okhttp3.RequestBody.Companion.toRequestBody
import java.util.concurrent.TimeUnit

/*
 * Session API (packages/contracts/schemas/session.schema.json, openapi.json).
 * Hand-written for the scaffold; APP-01 asks for a client generated from openapi.json.
 * Every call returns ApiResult and never throws to the UI: any failure is an error,
 * never a pass (AGENTS.md §6 rule 4).
 */

@Serializable
data class ColorStep(
    val rgb: String,
    @SerialName("hold_ms") val holdMs: Int,
    // Contract: const 150, not required.
    @SerialName("transition_ms") val transitionMs: Int = 150,
)

@Serializable
data class Challenge(
    @SerialName("challenge_id") val challengeId: String,
    @SerialName("baseline_ms") val baselineMs: Int = 1000,
    @SerialName("color_sequence") val colorSequence: List<ColorStep>,
    @SerialName("capture_at_ms") val captureAtMs: List<Int> = emptyList(),
    @SerialName("expires_at") val expiresAt: String? = null,
    /** FLOW-01/LIVE-01 schedule; only for sessions created with purpose onboarding or recovery. */
    val dynamic: DynamicChallenge? = null,
    @SerialName("media_nonce") val mediaNonce: String? = null,
)

/** One mark of the dot path: x/y as a fraction of the display area, time from the recording's start. */
@Serializable
data class GazePoint(val x: Double, val y: Double, @SerialName("at_ms") val atMs: Int)

/** Every *_at_ms is counted from the first frame of the face recording (dynamic-session-api.md). */
@Serializable
data class DynamicChallenge(
    val version: Int,
    @SerialName("session_id") val sessionId: String,
    val nonce: String,
    @SerialName("gaze_points") val gazePoints: List<GazePoint>,
    /** e.g. ["left","right","center"], user's point of view. */
    @SerialName("head_turns") val headTurns: List<String>,
    @SerialName("head_start_at_ms") val headStartAtMs: Int,
    @SerialName("head_duration_ms") val headDurationMs: Int,
    @SerialName("voice_start_at_ms") val voiceStartAtMs: Int,
    @SerialName("voice_prompt") val voicePrompt: String,
    @SerialName("voice_challenge_id") val voiceChallengeId: String,
    @SerialName("frontal_capture_at_ms") val frontalCaptureAtMs: Int,
)

@Serializable
data class CreateSessionRequest(
    val purpose: String, val nonce: String,
    @SerialName("device_public_key_spki") val devicePublicKeySpki: String? = null,
    @SerialName("account_id") val accountId: String? = null,
    @SerialName("device_id") val deviceId: String? = null,
)

@Serializable
data class AccountReceipt(
    @SerialName("account_id") val accountId: String,
    @SerialName("device_id") val deviceId: String,
    @SerialName("expires_at") val expiresAt: String,
)

@Serializable
data class DeviceChallenge(val message: String, @SerialName("expires_at") val expiresAt: String)

@Serializable
data class DeviceProofRequest(val signature: String)

@Serializable
data class DeviceProofResponse(val received: Boolean = false)

/** Opaque signed result for the integrator; signature validity is not a pass decision. */
@Serializable
data class SignedResult(val algorithm: String, @SerialName("key_id") val keyId: String,
    val payload: String, val signature: String)

@Serializable
data class SigningKey(val algorithm: String, @SerialName("key_id") val keyId: String,
    @SerialName("public_key_spki") val publicKeySpki: String)

@Serializable
data class CreateSessionResponse(
    @SerialName("session_id") val sessionId: String,
    val token: String,
    @SerialName("expires_at") val expiresAt: String,
    val challenge: Challenge,
    val purpose: String? = null,
    val nonce: String? = null,
    @SerialName("device_challenge") val deviceChallenge: DeviceChallenge? = null,
)

@Serializable
data class ColorEvent(val index: Int, val rgb: String, @SerialName("painted_at") val paintedAt: Double)

@Serializable
data class FrameTime(
    @SerialName("capture_time") val captureTime: Double?,
    @SerialName("presented_frames") val presentedFrames: Int,
    @SerialName("media_time") val mediaTime: Double,
)

@Serializable
data class Signals(
    @SerialName("color_events") val colorEvents: List<ColorEvent>,
    @SerialName("frame_times") val frameTimes: List<FrameTime>,
    @SerialName("client_quality") val clientQuality: Map<String, String> = emptyMap(),
    val camprobe: vn.vericlue.app.capture.CamProbe? = null,
    @SerialName("region_means") val regionMeans: List<vn.vericlue.app.capture.RegionFrame>? = null,
    /** Required for sessions with a purpose: the current challenge (FLOW-01). */
    @SerialName("challenge_id") val challengeId: String? = null,
)

@Serializable
data class StepAck(val step: String, val received: Boolean = false)

@Serializable
data class FinalizeResponse(
    val status: String,
    @SerialName("retry_hint") val retryHint: String? = null,
    @SerialName("voice_prompt") val voicePrompt: String? = null,
    @SerialName("attempts_left") val attemptsLeft: Int? = null,
    val challenge: Challenge? = null,
    @SerialName("voice_challenge_id") val voiceChallengeId: String? = null,
)

@Serializable
data class VoiceResponse(
    val status: String,
    @SerialName("voice_prompt") val voicePrompt: String? = null,
    @SerialName("attempts_left") val attemptsLeft: Int? = null,
    @SerialName("voice_challenge_id") val voiceChallengeId: String? = null,
    val account: AccountReceipt? = null,
)

@Serializable
data class FinalizeRequest(@SerialName("challenge_id") val challengeId: String)

@Serializable
data class OtpRequest(val phone: String)

@Serializable
data class OtpSent(
    @SerialName("expires_at") val expiresAt: String,
    @SerialName("attempts_left") val attemptsLeft: Int,
    /** Only from the simulated channel (demo): the text shown in the "SMS mô phỏng" box. */
    @SerialName("simulated_sms") val simulatedSms: String? = null,
)

@Serializable
data class OtpVerifyRequest(val code: String)

@Serializable
data class OtpVerifyResponse(val status: String, @SerialName("attempts_left") val attemptsLeft: Int)

@Serializable
data class IdCardFields(
    @SerialName("full_name") val fullName: String? = null,
    @SerialName("id_number") val idNumber: String? = null,
    @SerialName("date_of_birth") val dateOfBirth: String? = null,
    val sex: String? = null,
    val address: String? = null,
    @SerialName("issued_on") val issuedOn: String? = null,
)

@Serializable
data class IdCardResponse(
    val status: String,
    val fields: IdCardFields? = null,
    @SerialName("retry_hint") val retryHint: String? = null,
)

@Serializable
data class IdCardConfirmResponse(val received: Boolean = false)

@Serializable
data class ChallengeResponse(
    /** New session token: the old one stops working (PLAT-06). */
    val token: String,
    @SerialName("expires_at") val expiresAt: String,
    val challenge: Challenge,
)

@Serializable
data class ErrorResponse(@SerialName("error_code") val errorCode: String, val message: String)

/** Why a call failed. Each maps to an error screen; none of them is ever a pass. */
enum class ApiError { Network, Unauthorized, Conflict, RecoveryRequired, Expired, Busy, BadResponse, Server }

sealed interface ApiResult<out T> {
    data class Ok<T>(val value: T) : ApiResult<T>
    data class Err(val error: ApiError, val code: String? = null) : ApiResult<Nothing>
}

class SessionApi(
    baseUrl: String,
    private val http: OkHttpClient = OkHttpClient.Builder()
        .connectTimeout(15, TimeUnit.SECONDS)
        .readTimeout(60, TimeUnit.SECONDS)
        .writeTimeout(60, TimeUnit.SECONDS)
        .build(),
) {
    private val base = baseUrl.toHttpUrl()
    private val json = Json { ignoreUnknownKeys = true; explicitNulls = false }

    /** [request] null = the old MVP session (no purpose, no dynamic schedule). */
    suspend fun createSession(mockScenario: String? = null, request: CreateSessionRequest? = null): ApiResult<CreateSessionResponse> {
        val body = request?.let { json.encodeToString(CreateSessionRequest.serializer(), it) } ?: "{}"
        return call(post(url("v1", "sessions"), body.toRequestBody(JSON), null, mockScenario))
    }

    suspend fun proveDevice(sessionId: String, token: String, signature: String): ApiResult<DeviceProofResponse> =
        call(post(url("v1", "sessions", sessionId, "device-proof"),
            json.encodeToString(DeviceProofRequest.serializer(), DeviceProofRequest(signature)).toRequestBody(JSON), token))

    suspend fun accountReceipt(sessionId: String, token: String): ApiResult<AccountReceipt> =
        call(Request.Builder().url(url("v1", "sessions", sessionId, "account"))
            .header("Authorization", "Bearer $token").header("Cache-Control", "no-store").get().build())

    /** Forward to the integrator backend; do not decode and authorize based on payload alone. */
    suspend fun signedResult(sessionId: String, token: String): ApiResult<SignedResult> =
        call(Request.Builder().url(url("v1", "sessions", sessionId, "result"))
            .header("Authorization", "Bearer $token").header("Cache-Control", "no-store").get().build())

    suspend fun uploadMedia(sessionId: String, token: String, imageJpeg: ByteArray, video: File?, challengeId: String? = null, mediaSignature: String? = null): ApiResult<StepAck> {
        val body = MultipartBody.Builder().setType(MultipartBody.FORM)
            .addFormDataPart("image", "face.jpg", imageJpeg.toRequestBody(JPEG))
            .apply { if (video != null) addFormDataPart("video", video.name, video.asRequestBody(MP4)) }
            .apply { if (challengeId != null) addFormDataPart("challenge_id", challengeId) }
            .apply { if (mediaSignature != null) addFormDataPart("media_signature", mediaSignature) }
            .build()
        return call(post(url("v1", "sessions", sessionId, "media"), body, token))
    }

    suspend fun sendSignals(sessionId: String, token: String, signals: Signals): ApiResult<StepAck> =
        call(post(url("v1", "sessions", sessionId, "signals"), json.encodeToString(Signals.serializer(), signals).toRequestBody(JSON), token))

    suspend fun finalize(sessionId: String, token: String, challengeId: String? = null): ApiResult<FinalizeResponse> {
        val body = challengeId?.let { json.encodeToString(FinalizeRequest.serializer(), FinalizeRequest(it)) } ?: ""
        return call(post(url("v1", "sessions", sessionId, "finalize"), body.toRequestBody(JSON), token))
    }

    /** [audioOffsetMs]: when the WAV starts, from the video's first frame (sent only with a video). */
    suspend fun sendVoice(
        sessionId: String,
        token: String,
        wav: ByteArray,
        video: File?,
        audioOffsetMs: Int? = null,
        voiceChallengeId: String? = null,
        mediaSignature: String? = null,
    ): ApiResult<VoiceResponse> {
        val body = MultipartBody.Builder().setType(MultipartBody.FORM)
            .addFormDataPart("audio", "voice.wav", wav.toRequestBody(WAV))
            .apply {
                if (video != null) {
                    addFormDataPart("video", video.name, video.asRequestBody(MP4))
                    audioOffsetMs?.let { addFormDataPart("audio_offset_ms", it.coerceIn(-5000, 5000).toString()) }
                }
                if (voiceChallengeId != null) addFormDataPart("voice_challenge_id", voiceChallengeId)
                if (mediaSignature != null) addFormDataPart("media_signature", mediaSignature)
            }
            .build()
        return call(post(url("v1", "sessions", sessionId, "voice"), body, token))
    }

    suspend fun sendOtp(sessionId: String, token: String, phone: String): ApiResult<OtpSent> =
        call(post(url("v1", "sessions", sessionId, "otp"), json.encodeToString(OtpRequest.serializer(), OtpRequest(phone)).toRequestBody(JSON), token))

    suspend fun verifyOtp(sessionId: String, token: String, code: String): ApiResult<OtpVerifyResponse> =
        call(post(url("v1", "sessions", sessionId, "otp", "verify"), json.encodeToString(OtpVerifyRequest.serializer(), OtpVerifyRequest(code)).toRequestBody(JSON), token))

    suspend fun uploadIdCard(sessionId: String, token: String, front: ByteArray, back: ByteArray, qr: String?): ApiResult<IdCardResponse> {
        val body = MultipartBody.Builder().setType(MultipartBody.FORM)
            .addFormDataPart("front", "front.jpg", front.toRequestBody(JPEG))
            .addFormDataPart("back", "back.jpg", back.toRequestBody(JPEG))
            .apply { if (!qr.isNullOrBlank()) addFormDataPart("qr", qr) }
            .build()
        return call(post(url("v1", "sessions", sessionId, "id-card"), body, token))
    }

    suspend fun confirmIdCard(sessionId: String, token: String, fields: IdCardFields): ApiResult<IdCardConfirmResponse> =
        call(post(url("v1", "sessions", sessionId, "id-card", "confirm"), json.encodeToString(IdCardFields.serializer(), fields).toRequestBody(JSON), token))

    /** Fresh challenge for the face part, with the token extended (ADR-0017 §2). */
    suspend fun refreshChallenge(sessionId: String, token: String): ApiResult<ChallengeResponse> =
        call(post(url("v1", "sessions", sessionId, "challenge"), "".toRequestBody(JSON), token))

    private fun url(vararg segments: String) = base.newBuilder().apply { segments.forEach { addPathSegment(it) } }.build()

    private fun post(url: okhttp3.HttpUrl, body: RequestBody, token: String?, mockScenario: String? = null): Request =
        Request.Builder().url(url).post(body).apply {
            if (token != null) header("Authorization", "Bearer $token")
            if (mockScenario != null) header("X-Mock-Scenario", mockScenario)
        }.build()

    private suspend inline fun <reified T> call(request: Request): ApiResult<T> = withContext(Dispatchers.IO) {
        try {
            http.newCall(request).execute().use { res ->
                val text = res.body?.string().orEmpty()
                if (!res.isSuccessful) {
                    val code = runCatching { json.decodeFromString(ErrorResponse.serializer(), text).errorCode }.getOrNull()
                    return@withContext ApiResult.Err(errorFor(res.code, code), code)
                }
                ApiResult.Ok(json.decodeFromString<T>(text))
            }
        } catch (e: IOException) {
            ApiResult.Err(ApiError.Network)
        } catch (e: SerializationException) {
            ApiResult.Err(ApiError.BadResponse)
        } catch (e: IllegalArgumentException) {
            ApiResult.Err(ApiError.BadResponse)
        }
    }

    companion object {
        private val JSON = "application/json".toMediaType()
        private val JPEG = "image/jpeg".toMediaType()
        private val MP4 = "video/mp4".toMediaType()
        private val WAV = "audio/wav".toMediaType()

        fun errorFor(httpCode: Int, code: String? = null): ApiError = when (httpCode) {
            401 -> ApiError.Unauthorized
            409 -> if (code == "recovery_required") ApiError.RecoveryRequired else ApiError.Conflict
            410 -> ApiError.Expired
            503 -> ApiError.Busy
            in 400..499 -> ApiError.BadResponse
            else -> ApiError.Server
        }
    }
}
