package vn.vericlue.app.capture

import android.annotation.SuppressLint
import android.content.Context
import android.graphics.Bitmap
import android.graphics.Matrix
import android.graphics.RectF
import android.hardware.camera2.CameraCharacteristics
import android.os.SystemClock
import android.util.Log
import android.util.Size
import androidx.camera.camera2.interop.Camera2CameraInfo
import androidx.camera.camera2.interop.ExperimentalCamera2Interop
import androidx.camera.core.CameraSelector
import androidx.camera.core.ExperimentalGetImage
import androidx.camera.core.ImageCapture
import androidx.camera.core.ImageCaptureException
import androidx.camera.core.ImageAnalysis
import androidx.camera.core.ImageProxy
import androidx.camera.core.resolutionselector.AspectRatioStrategy
import androidx.camera.core.resolutionselector.ResolutionSelector
import androidx.camera.core.resolutionselector.ResolutionStrategy
import androidx.camera.video.FileOutputOptions
import androidx.camera.video.AudioStats
import androidx.camera.video.Recording
import androidx.camera.video.VideoRecordEvent
import androidx.camera.view.CameraController
import androidx.camera.view.LifecycleCameraController
import androidx.camera.view.transform.CoordinateTransform
import androidx.camera.view.transform.ImageProxyTransformFactory
import androidx.camera.view.transform.OutputTransform
import androidx.camera.view.video.AudioConfig
import androidx.core.content.ContextCompat
import androidx.lifecycle.LifecycleOwner
import com.google.mlkit.vision.barcode.BarcodeScannerOptions
import com.google.mlkit.vision.barcode.BarcodeScanning
import com.google.mlkit.vision.barcode.ZoomSuggestionOptions
import com.google.mlkit.vision.barcode.common.Barcode
import com.google.mlkit.vision.common.InputImage
import com.google.mlkit.vision.face.FaceDetection
import com.google.mlkit.vision.face.FaceDetectorOptions
import com.google.mlkit.vision.face.FaceLandmark
import com.google.android.gms.tasks.Tasks
import java.io.ByteArrayOutputStream
import java.io.File
import java.util.concurrent.Executors
import kotlin.coroutines.resume
import kotlinx.coroutines.CompletableDeferred
import kotlinx.coroutines.suspendCancellableCoroutine
import kotlinx.coroutines.withTimeoutOrNull
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import vn.vericlue.app.data.api.FrameTime
import vn.vericlue.app.BuildConfig

/**
 * One camera session for the whole face part: the front camera stays on from framing to the
 * end of the voice step (ADR-0013 principle 4). Screens only show its preview.
 *
 * Also collects frame_times, region_means and the camprobe facts sent with the signals.
 * Not done yet: the dot path (waits for LIVE-01) and media signing (SEC-02).
 */
@androidx.annotation.OptIn(androidx.camera.view.TransformExperimental::class)
class CameraSession(
    private val context: Context,
    val debugTrace: PresenceDebugTrace = PresenceDebugTrace(enabled = BuildConfig.DEBUG && BuildConfig.PRESENCE_TRACE_ENABLED),
) {
    private val diagnosticCache = PresenceTraceCache(File(context.cacheDir, "presence-debug.json"))
    init {
        // Diagnostic data stays private and short-lived; never survives into a regular build.
        diagnosticCache.prune()
        if (!debugTrace.enabled) diagnosticCache.clear()
    }

    fun savePresenceDebugTrace() {
        if (debugTrace.enabled) runCatching {
            diagnosticCache.save(debugTrace)
            val cache = diagnosticCache
            android.os.Handler(android.os.Looper.getMainLooper()).postDelayed(
                { cache.prune() }, PresenceTraceCache.TTL_MS,
            )
        }
    }

    fun clearPresenceDebugTrace() {
        debugTrace.clear()
        diagnosticCache.clear()
    }
    val controller = LifecycleCameraController(context)
    private val analysisExecutor = Executors.newSingleThreadExecutor()
    private val detector = FaceDetection.getClient(
        FaceDetectorOptions.Builder()
            .setPerformanceMode(FaceDetectorOptions.PERFORMANCE_MODE_FAST)
            .setLandmarkMode(FaceDetectorOptions.LANDMARK_MODE_ALL)
            .enableTracking()
            .setMinFaceSize(0.15f)
            .build(),
    )

    private val cardFaceDetector = FaceDetection.getClient(
        FaceDetectorOptions.Builder().setPerformanceMode(FaceDetectorOptions.PERFORMANCE_MODE_FAST)
            .setMinFaceSize(0.05f).build(),
    )
    private val _idQuality = MutableStateFlow<IdQuality?>(null)
    val idQuality: StateFlow<IdQuality?> = _idQuality
    private val qrScanner = BarcodeScanning.getClient(
        BarcodeScannerOptions.Builder().setBarcodeFormats(Barcode.FORMAT_QR_CODE)
            .enableAllPotentialBarcodes()
            .setZoomSuggestionOptions(ZoomSuggestionOptions.Builder(::suggestQrZoom)
                .setMaxSupportedZoomRatio(3f).build())
            .build(),
    )
    @Volatile private var backMode = false
    @Volatile private var idQrOnly = false
    private var lastQrZoomMs = 0L
    private var lastCardDiagnosticMs = 0L
    private val cardResolution = ResolutionSelector.Builder()
        .setAspectRatioStrategy(AspectRatioStrategy.RATIO_4_3_FALLBACK_AUTO_STRATEGY)
        .setResolutionStrategy(ResolutionStrategy(Size(1920, 1440),
            ResolutionStrategy.FALLBACK_RULE_CLOSEST_LOWER_THEN_HIGHER))
        .setResolutionFilter { sizes, _ -> sizes.filter { it.width.toLong() * it.height <= 1920L * 1440 }
            .ifEmpty { sizes } }
        .build()
    private var idRequest: CompletableDeferred<Pair<ByteArray, IdQuality>>? = null
    private val qrState = QrCaptureState()

    /** Last QR text seen during the current card side/retake. */
    val qr: StateFlow<String?> = qrState.qr

    /** Clears a card side's QR and rejects scanner callbacks from before this reset. */
    fun clearQr() { qrState.clear(); _idQuality.value = null }

    private val _face = MutableStateFlow<FaceSignal?>(null)
    val face: StateFlow<FaceSignal?> = _face
    @Volatile private var faceGeneration = 0L
    @Volatile private var faceOutput: Pair<Long, OutputTransform>? = null
    private val faceTransformFactory = ImageProxyTransformFactory().apply { isUsingRotationDegrees = true }

    /** Main thread: actual CameraX crop, rotation and selfie mirroring, in PreviewView pixels. */
    fun previewBounds(signal: FaceSignal?): RectF? {
        if (signal == null) return null
        val source = faceOutput?.takeIf { it.first == signal.timestampNs }?.second ?: return null
        val target = preview?.outputTransform ?: return null
        return runCatching {
            RectF(signal.left * signal.imageWidth, signal.top * signal.imageHeight,
                signal.right * signal.imageWidth, signal.bottom * signal.imageHeight).also {
                CoordinateTransform(source, target).mapRect(it)
            }.takeIf { listOf(it.left, it.top, it.right, it.bottom).all { coordinate -> coordinate.isFinite() } }
        }.getOrNull()
    }

    @Volatile private var bound = false
    private var preview: androidx.camera.view.PreviewView? = null

    /**
     * One PreviewView reused by every screen. A new view per screen makes the controller
     * reconfigure the camera, which cancels a running recording.
     */
    fun previewView(activityContext: Context): androidx.camera.view.PreviewView =
        preview ?: androidx.camera.view.PreviewView(activityContext).apply {
            implementationMode = androidx.camera.view.PreviewView.ImplementationMode.COMPATIBLE
            scaleType = if (backMode) androidx.camera.view.PreviewView.ScaleType.FILL_CENTER
                else androidx.camera.view.PreviewView.ScaleType.FIT_CENTER
            controller = this@CameraSession.controller
        }.also { preview = it }
    private data class JpegRequest(val result: CompletableDeferred<ByteArray>, val afterMs: Long)
    @Volatile private var jpegRequest: JpegRequest? = null

    private fun clearFaceAnalysis() {
        faceGeneration++
        _face.value = null
        faceOutput = null
        synchronized(this) { jpegRequest?.result?.cancel(); jpegRequest = null }
    }

    // Frame timing while recording (Signals.frame_times).
    private val frames = mutableListOf<FrameTime>()
    @Volatile private var recordingFrames = false
    private var firstFrameNs = 0L
    private var recording: Recording? = null
    private var videoFile: File? = null
    private var analyzedFrames = 0
    private val duplicates = DuplicateFrameMeter()
    private val regionFrames = mutableListOf<RegionFrame>()
    private var analysisStartMs = 0.0

    private var videoEnabled = false
    private var usedFallbackCamera = false
    @Volatile private var realtimeTimestampSource = false

    @androidx.annotation.OptIn(ExperimentalCamera2Interop::class)
    private fun queryTimestampSource(): String = runCatching {
        val info = controller.cameraInfo ?: return@runCatching "unknown"
        when (Camera2CameraInfo.from(info).getCameraCharacteristic(CameraCharacteristics.SENSOR_INFO_TIMESTAMP_SOURCE)) {
            CameraCharacteristics.SENSOR_INFO_TIMESTAMP_SOURCE_REALTIME -> "realtime"
            else -> "unknown"
        }
    }.getOrDefault("unknown")

    /**
     * Opens the front camera (face part) or the rear camera (ID card, APP-04). Main thread only.
     * Never throws: falls back to the other camera when the preferred one is missing, drops video
     * when the device cannot record alongside analysis, and returns false when no camera can be
     * opened, so the caller shows an error screen instead of crashing.
     */
    suspend fun start(owner: LifecycleOwner, back: Boolean, idQrOnly: Boolean = false): Boolean {
        clearFaceAnalysis()
        if (!awaitInitialized()) return false
        if (backMode != back) clearQr()
        backMode = back
        preview?.scaleType = if (back) androidx.camera.view.PreviewView.ScaleType.FILL_CENTER
            else androidx.camera.view.PreviewView.ScaleType.FIT_CENTER
        this.idQrOnly = back && idQrOnly
        val preferred = if (back) CameraSelector.DEFAULT_BACK_CAMERA else CameraSelector.DEFAULT_FRONT_CAMERA
        val other = if (back) CameraSelector.DEFAULT_FRONT_CAMERA else CameraSelector.DEFAULT_BACK_CAMERA
        val selector = listOf(preferred, other).firstOrNull { runCatching { controller.hasCamera(it) }.getOrDefault(false) }
            ?: return false
        if (!bound) {
            controller.imageAnalysisBackpressureStrategy = ImageAnalysis.STRATEGY_KEEP_ONLY_LATEST
            controller.setImageAnalysisAnalyzer(analysisExecutor, ::analyze)
        }
        val choices = if (back) listOf(CameraController.IMAGE_ANALYSIS or CameraController.IMAGE_CAPTURE)
            else listOf(CameraController.IMAGE_ANALYSIS or CameraController.VIDEO_CAPTURE, CameraController.IMAGE_ANALYSIS)
        val resolutions = if (back) listOf(cardResolution, null) else listOf(null)
        for (resolution in resolutions) for (useCases in choices) {
            val ok = runCatching {
                controller.imageAnalysisResolutionSelector = resolution
                controller.setEnabledUseCases(useCases)
                controller.cameraSelector = selector
                if (!bound) controller.bindToLifecycle(owner)
            }.isSuccess
            if (ok) {
                bound = true
                videoEnabled = useCases and CameraController.VIDEO_CAPTURE != 0
                usedFallbackCamera = selector != preferred
                runCatching { controller.setZoomRatio(1f) }
                lastQrZoomMs = 0L
                lastCardDiagnosticMs = 0L
                analyzedFrames = 0
                return true
            }
        }
        return false
    }

    /** ML Kit invokes this on the main thread. Never zoom the portrait or face-video step. */
    private fun suggestQrZoom(suggestion: Float): Boolean {
        if (!bound || !backMode || !idQrOnly) return false
        val state = controller.zoomState.value ?: return false
        val target = suggestion.coerceIn(1f, minOf(3f, state.maxZoomRatio))
        val now = SystemClock.elapsedRealtime()
        if (now - lastQrZoomMs < 700 || kotlin.math.abs(target - state.zoomRatio) < 0.1f) return false
        return runCatching {
            controller.setZoomRatio(target)
            lastQrZoomMs = now
            true
        }.getOrDefault(false)
    }

    private suspend fun awaitInitialized(): Boolean = suspendCancellableCoroutine { cont ->
        val future = controller.initializationFuture
        future.addListener(
            { cont.resume(runCatching { future.get() }.isSuccess) },
            ContextCompat.getMainExecutor(context),
        )
    }

    /**
     * Photo of the card plus local quality checks, from the next analysed rear-camera frame.
     * Callers waiting at the same time share that frame: the auto-capture loop must not swallow
     * a tap on the shutter.
     */
    suspend fun captureId(): Pair<ByteArray, IdQuality> {
        val generation = qrState.generation()
        val pair = synchronized(this) {
            idRequest?.let { it to false } ?: (CompletableDeferred<Pair<ByteArray, IdQuality>>().also { idRequest = it } to true)
        }
        val req = pair.first
        if (pair.second) {
            controller.takePicture(analysisExecutor, object : ImageCapture.OnImageCapturedCallback() {
                override fun onCaptureSuccess(image: ImageProxy) {
                    if (!req.isActive || generation != qrState.generation()) { image.close(); req.cancel(); return }
                    val bitmap = try {
                        var b = image.toBitmap()
                        val rotation = image.imageInfo.rotationDegrees
                        if (rotation != 0) b = Bitmap.createBitmap(b, 0, 0, b.width, b.height, Matrix().apply { postRotate(rotation.toFloat()) }, true)
                        // CameraController's viewport may already crop the capture; the center crop
                        // below also bounds devices which return the full sensor image.
                        cropCardBitmap(b)
                    } catch (_: Exception) {
                        req.completeExceptionally(IllegalStateException("Card capture unavailable")); image.close(); return
                    }
                    image.close()
                    val qrTask = qrScanner.process(InputImage.fromBitmap(bitmap, 0))
                    val faceTask = if (idQrOnly) null else cardFaceDetector.process(InputImage.fromBitmap(bitmap, 0))
                    Tasks.whenAllComplete(listOfNotNull(qrTask, faceTask)).addOnCompleteListener(analysisExecutor) {
                        try {
                            if (generation != qrState.generation() || !req.isActive) { req.cancel(); return@addOnCompleteListener }
                            if (!qrTask.isSuccessful || faceTask?.isSuccessful == false) throw IllegalStateException("Card analysis unavailable")
                            val qr = qrTask.result.firstNotNullOfOrNull { it.rawValue?.takeIf { raw -> CccdQr.parse(raw) != null } }
                            val faces = faceTask?.result.orEmpty()
                            val q = bitmapQuality(bitmap).copy(qr = qr, portraitPresent = faces.size == 1,
                                tilted = faces.singleOrNull()?.let { kotlin.math.abs(it.headEulerAngleZ) > 15f } ?: false,
                                looksLikeCard = faces.size == 1 || qr != null)
                            val bytes = ByteArrayOutputStream().use { out -> bitmap.compress(Bitmap.CompressFormat.JPEG, 95, out); out.toByteArray() }
                            req.complete(bytes to q)
                        } catch (_: Exception) {
                            req.completeExceptionally(IllegalStateException("Card analysis unavailable"))
                        } finally { bitmap.recycle() }
                    }
                }
                override fun onError(exception: ImageCaptureException) {
                    req.completeExceptionally(IllegalStateException("Card capture unavailable"))
                }
            })
        }
        try { return req.await() } finally {
            if (req.isActive) req.cancel()
            synchronized(this) { if (idRequest === req) idRequest = null }
        }
    }

    fun unbind() {
        clearFaceAnalysis()
        stopRecording()
        controller.unbind()
        bound = false
    }

    /** Next freshly analysed, complete frontal face. A timed-out request cannot capture later. */
    suspend fun captureJpeg(): ByteArray {
        val req = synchronized(this) {
            jpegRequest?.takeIf { it.result.isActive }
                ?: JpegRequest(CompletableDeferred(), SystemClock.elapsedRealtime()).also { jpegRequest = it }
        }
        try { return req.result.await() } finally {
            if (req.result.isActive) req.result.cancel()
            synchronized(this) { if (jpegRequest === req) jpegRequest = null }
        }
    }

    @Volatile private var aeAwbLocked = false

    /**
     * Locks auto-exposure and auto white balance so the camera does not cancel out the colour
     * reflected on the skin (ADR-0016 layer 1). Call after the grey baseline; unlock afterwards.
     * Some devices ignore the request; client_quality reports what was asked.
     */
    @androidx.annotation.OptIn(ExperimentalCamera2Interop::class)
    fun lockAeAwb(lock: Boolean) {
        val control = controller.cameraControl ?: return
        runCatching {
            androidx.camera.camera2.interop.Camera2CameraControl.from(control).captureRequestOptions =
                androidx.camera.camera2.interop.CaptureRequestOptions.Builder()
                    .setCaptureRequestOption(android.hardware.camera2.CaptureRequest.CONTROL_AE_LOCK, lock)
                    .setCaptureRequestOption(android.hardware.camera2.CaptureRequest.CONTROL_AWB_LOCK, lock)
                    .build()
            aeAwbLocked = lock || aeAwbLocked
        }
    }

    private var finalized: CompletableDeferred<Boolean>? = null
    private var muxedReady: CompletableDeferred<Boolean>? = null
    private var recordingGeneration = 0L
    private val _voiceLevel = MutableStateFlow(0f)
    val voiceLevel: StateFlow<Float> = _voiceLevel
    var muxedVoiceFailure: VoiceCaptureFailure? = null
        private set

    /**
     * Starts an MP4 recording, audio off. [voice] = false: the colour flash, sent as `video` in
     * /media, with frame_times and region_means. [voice] = true: the sentence reading, sent as
     * `video` in /voice next to the WAV (lip sync, VOICE-05); the face signals are left untouched.
     */
    @SuppressLint("MissingPermission")
    fun startRecording(voice: Boolean = false) {
        beginRecording(voice = voice, muxedVoice = false)
    }

    /** The live voice source: CameraX records its microphone and video into one capped MP4. */
    @SuppressLint("MissingPermission")
    fun startMuxedVoiceRecording(): Boolean = beginRecording(voice = true, muxedVoice = true)

    @SuppressLint("MissingPermission")
    private fun beginRecording(voice: Boolean, muxedVoice: Boolean): Boolean {
        if (recording != null) return false
        val attempt = ++recordingGeneration
        muxedVoiceFailure = null
        _voiceLevel.value = 0f
        val ready = if (muxedVoice) CompletableDeferred<Boolean>() else null
        muxedReady = ready
        if (!videoEnabled) {
            videoFile = null
            finalized = null
            muxedVoiceFailure = VoiceCaptureFailure.Camera
            ready?.complete(false)
            return false
        }
        val prefix = if (voice) "voice_" else "face_"
        val file = File(context.cacheDir, "$prefix${System.currentTimeMillis()}_$attempt.mp4").also { videoFile = it }
        if (!voice) {
            synchronized(frames) { frames.clear() }
            synchronized(regionFrames) { regionFrames.clear() }
            debugTrace.clear()
            diagnosticCache.clear()
            firstFrameNs = 0L
            recordingFrames = true
        }
        val done = CompletableDeferred<Boolean>().also { finalized = it }
        val begun = CompletableDeferred<Unit>().also { started = it }
        recordedAt = null
        var audioBroken = false
        var readySeen = false
        recording = runCatching {
            val output = FileOutputOptions.Builder(file).apply {
                if (muxedVoice) setDurationLimitMillis(MUXED_VOICE_LIMIT_MS)
            }.build()
            controller.startRecording(
                output,
                if (muxedVoice) AudioConfig.create(true) else AudioConfig.AUDIO_DISABLED,
                ContextCompat.getMainExecutor(context),
            ) events@{ event ->
                if (attempt != recordingGeneration) {
                    if (event is VideoRecordEvent.Finalize) {
                        begun.complete(Unit)
                        ready?.complete(false)
                        done.complete(false)
                        if (videoFile != file) file.delete()
                    }
                    return@events
                }
                val audio = event.recordingStats.audioStats
                if (muxedVoice && event !is VideoRecordEvent.Finalize) {
                    val active = audio.audioState == AudioStats.AUDIO_STATE_ACTIVE
                    val failed = audio.hasError() || audio.audioState in setOf(
                        AudioStats.AUDIO_STATE_SOURCE_SILENCED, AudioStats.AUDIO_STATE_MUTED,
                    ) || (readySeen && !active)
                    if (failed) {
                        audioBroken = true
                        muxedVoiceFailure = VoiceCaptureFailure.Audio
                        ready?.complete(false)
                        stopRecording()
                    } else if (muxedVoiceReady(event.recordingStats.recordedDurationNanos, active, audio.hasError())) {
                        readySeen = true
                        ready?.complete(true)
                    }
                    val amplitude = audio.audioAmplitude
                    _voiceLevel.value = if (active && amplitude.isFinite()) amplitude.toFloat().coerceIn(0f, 1f) else 0f
                }
                // Start arrives before any frame; the first frame shows as recorded time > 0.
                if (event is VideoRecordEvent.Status && recording != null &&
                    event.recordingStats.recordedDurationNanos > 0) {
                    recordedAt = event.recordingStats.recordedDurationNanos to SystemClock.elapsedRealtimeNanos()
                    begun.complete(Unit)
                }
                if (event is VideoRecordEvent.Finalize) {
                    if (muxedVoice && (audio.hasError() || audio.audioState in setOf(
                            AudioStats.AUDIO_STATE_SOURCE_SILENCED, AudioStats.AUDIO_STATE_MUTED,
                        ))) {
                        audioBroken = true
                        muxedVoiceFailure = VoiceCaptureFailure.Audio
                    }
                    begun.complete(Unit)
                    ready?.complete(false)
                    _voiceLevel.value = 0f
                    done.complete(voiceFinalizeAccepted(
                        muxedVoice = muxedVoice,
                        controlledDurationCap = muxedVoice && output.durationLimitMillis == MUXED_VOICE_LIMIT_MS,
                        noError = !event.hasError(),
                        durationLimitReached = event.error == VideoRecordEvent.Finalize.ERROR_DURATION_LIMIT_REACHED,
                        audioFault = audioBroken,
                    ))
                    // Finalize may arrive after this attempt was discarded.
                    if (videoFile != file) file.delete()
                }
            }
        }.getOrNull()
        if (recording == null) {
            videoFile = null
            done.complete(false)
            begun.complete(Unit)
            ready?.complete(false)
            muxedVoiceFailure = VoiceCaptureFailure.Camera
        }
        return recording != null
    }

    /** A native Start event alone is insufficient: require a video frame and active audio. */
    suspend fun awaitMuxedVoiceReady(timeoutMs: Long = 3000): Boolean {
        val ready = muxedReady ?: return false
        val result = withTimeoutOrNull(timeoutMs) { ready.await() } == true
        if (!result && muxedVoiceFailure == null) muxedVoiceFailure =
            if (recordedAt == null) VoiceCaptureFailure.Camera else VoiceCaptureFailure.Audio
        return result && recording != null && finalized?.isActive == true
    }

    private var started: CompletableDeferred<Unit>? = null

    /** Last Status event: recorded video length (ns) and when it arrived (elapsedRealtime ns). */
    @Volatile private var recordedAt: Pair<Long, Long>? = null

    /**
     * How far the running recording is from its first frame, in ms, right now: the last reported
     * length plus the time since that report. Sent as `audio_offset_ms` when the WAV starts.
     */
    /**
     * The first frame of the running recording's file, on the capture clock (ms); null until CameraX
     * reports one. This is t = 0 of the server's schedule (FLOW-01). It is not the first analysed
     * frame: the encoder starts 0.1–0.9 s after analysis does.
     */
    fun recordingStartMs(): Double? {
        if (recording == null) return null
        val (lengthNs, atNs) = recordedAt ?: return null
        return (atNs - lengthNs) / 1e6
    }

    fun videoElapsedMs(): Int? = runningVideoElapsedMs(
        recordingActive = recording != null,
        recordedAt = recordedAt,
        finalized = finalized,
        nowNs = SystemClock.elapsedRealtimeNanos(),
    )

    /**
     * Waits until the first video frame is written (about 0.9 s after the start on the emulator).
     * Starting the WAV only then keeps both files on the same start time (VOICE-05).
     */
    suspend fun awaitRecordingStarted(timeoutMs: Long = 2000) {
        withTimeoutOrNull(timeoutMs) { started?.await() }
    }

    fun stopRecording() {
        recordingFrames = false
        val running = recording
        recording = null
        recordedAt = null
        running?.stop()
        _voiceLevel.value = 0f
    }

    /** A file is ready only after CameraX successfully closes that recording. */
    suspend fun finishedVideo(timeoutMs: Long = 3000): VideoResult =
        awaitVideoFile(videoFile, finalized, timeoutMs)

    /** A decoded payload may only be paired with the same attempt's unchanged MP4. */
    fun isCurrentVideo(file: File): Boolean = videoFile == file

    /** Deletes every recorded video in the cache: once the server has it, or when the attempt is dropped. */
    fun deleteVideo(preserveDiagnostics: Boolean = false) {
        diagnosticCache.mediaDeleted(preserveDiagnostics)
        videoFile = null
        finalized = null
        debugTrace.clear()
        context.cacheDir.listFiles { f -> (f.name.startsWith("face_") || f.name.startsWith("voice_")) && f.name.endsWith(".mp4") }
            ?.forEach { it.delete() }
    }

    fun frameTimes(): List<FrameTime> = synchronized(frames) { frames.toList() }

    /** Facts the server needs to trust the timing, sent as Signals.client_quality. */
    @androidx.annotation.OptIn(ExperimentalCamera2Interop::class)
    fun clientQuality(readyVideo: File?): Map<String, String> {
        val source = runCatching {
            val info = controller.cameraInfo ?: return@runCatching "unknown"
            when (Camera2CameraInfo.from(info).getCameraCharacteristic(CameraCharacteristics.SENSOR_INFO_TIMESTAMP_SOURCE)) {
                CameraCharacteristics.SENSOR_INFO_TIMESTAMP_SOURCE_REALTIME -> "realtime"
                else -> "unknown"
            }
        }.getOrDefault("unknown")
        val elapsed = CaptureClock.nowMs() - analysisStartMs
        val fps = if (elapsed > 0) analyzedFrames * 1000.0 / elapsed else 0.0
        return mapOf(
            "client" to "android",
            "clock" to "elapsedRealtime",
            "timestamp_source" to source,
            "analysis_fps" to (Math.round(fps * 10) / 10.0).toString(),
            "ae_awb_lock_requested" to aeAwbLocked.toString(),
            "video" to if (readyVideo != null) "mp4" else "missing",
            "frames_recorded" to frameTimes().size.toString(),
            "camera_fallback" to usedFallbackCamera.toString(),
        )
    }

    @androidx.annotation.OptIn(ExperimentalGetImage::class)
    private fun analyze(proxy: ImageProxy) {
        val generation = faceGeneration
        val observedAtMs = SystemClock.elapsedRealtime()
        val media = proxy.image
        if (media == null) {
            proxy.close()
            return
        }
        if (analyzedFrames == 0) {
            analysisStartMs = CaptureClock.nowMs()
            realtimeTimestampSource = queryTimestampSource() == "realtime"
        }
        analyzedFrames++
        val ts = CaptureClock.sensorTimestampToElapsedNanos(proxy.imageInfo.timestamp, realtimeTimestampSource)
        if (ts <= 0L) {
            _face.value = null
            proxy.close()
            return
        }
        if (recordingFrames) {
            if (firstFrameNs == 0L) firstFrameNs = ts
            synchronized(frames) {
                frames += FrameTime(captureTime = ts / 1e6, presentedFrames = frames.size + 1, mediaTime = (ts - firstFrameNs) / 1e9)
            }
        }
        val rotation = proxy.imageInfo.rotationDegrees
        if (backMode) {
            analyzeIdFrame(proxy, media, rotation)
            return
        }
        val upright = rotation % 180 == 0
        val w = if (upright) proxy.width else proxy.height
        val h = if (upright) proxy.height else proxy.width
        val outputTransform = runCatching { faceTransformFactory.getOutputTransform(proxy) }.getOrNull()
        val luma = meanLuma(proxy)
        duplicates.add(thumbnail(proxy))
        // One listener on the analysis thread: the frame must stay open while regions are measured.
        detector.process(InputImage.fromMediaImage(media, rotation))
            .addOnCompleteListener(analysisExecutor) { task ->
                try {
                    if (generation != faceGeneration || backMode || !bound) return@addOnCompleteListener
                    val faces = if (task.isSuccessful) task.result else emptyList()
                    val face = faces.maxByOrNull { it.boundingBox.width() }
                    val signal = if (face == null) {
                        FaceSignal(0, 0f, 0f, 0f, 0f, luma, ts,
                            imageWidth = w, imageHeight = h, observedAtMs = observedAtMs)
                    } else {
                        val b = face.boundingBox
                        fun visibleLandmark(type: Int): Boolean = face.getLandmark(type)?.position?.let { p ->
                            p.x.isFinite() && p.y.isFinite() &&
                                p.x >= 0 && p.x < w && p.y >= 0 && p.y < h &&
                                p.x >= b.left && p.x <= b.right && p.y >= b.top && p.y <= b.bottom
                        } == true
                        val leftEye = visibleLandmark(FaceLandmark.LEFT_EYE)
                        val rightEye = visibleLandmark(FaceLandmark.RIGHT_EYE)
                        val noseAndMouth = visibleLandmark(FaceLandmark.NOSE_BASE) && visibleLandmark(FaceLandmark.MOUTH_BOTTOM)
                        if (recordingFrames) {
                            val box = Box(b.left.toFloat(), b.top.toFloat(), b.right.toFloat(), b.bottom.toFloat())
                            val stats = Regions.measure(box, w, h) { x, y -> rgbAt(proxy, x, y, rotation) }
                            synchronized(regionFrames) { regionFrames += RegionFrame(ts / 1e6, stats) }
                        }
                        FaceSignal(
                            faces = faces.size,
                            widthFraction = b.width().toFloat() / w,
                            centerX = b.exactCenterX() / w,
                            centerY = b.exactCenterY() / h,
                            yaw = face.headEulerAngleY,
                            pitch = face.headEulerAngleX,
                            roll = face.headEulerAngleZ,
                            luma = luma,
                            timestampNs = ts,
                            heightFraction = b.height().toFloat() / h,
                            imageWidth = w,
                            imageHeight = h,
                            landmarksComplete = leftEye && rightEye && noseAndMouth,
                            landmarksVisible = (leftEye || rightEye) && noseAndMouth,
                            observedAtMs = observedAtMs,
                            trackingId = face.trackingId,
                        )
                    }
                    if (generation != faceGeneration || backMode || !bound) return@addOnCompleteListener
                    faceOutput = outputTransform?.let { ts to it }
                    _face.value = signal
                    val request = jpegRequest
                    if (request != null && request.result.isActive && signal.observedAtMs >= request.afterMs &&
                        QualityGate.evaluate(signal, SystemClock.elapsedRealtime()) == vn.vericlue.app.flow.FramingState.Good) {
                        runCatching { toJpeg(proxy, rotation) }.fold(request.result::complete, request.result::completeExceptionally)
                        synchronized(this) { if (jpegRequest === request) jpegRequest = null }
                    }
                } finally {
                    proxy.close()
                }
            }
    }

    /** Colour of an upright pixel, read from the YUV_420_888 planes. */
    private fun rgbAt(proxy: ImageProxy, u: Int, v: Int, rotation: Int): Int {
        val (x, y) = Regions.sensorXY(u, v, rotation, proxy.width, proxy.height)
        val (yp, up, vp) = proxy.planes
        val yv = yp.buffer.get(y * yp.rowStride + x * yp.pixelStride).toInt() and 0xFF
        val uv = up.buffer.get((y / 2) * up.rowStride + (x / 2) * up.pixelStride).toInt() and 0xFF
        val vv = vp.buffer.get((y / 2) * vp.rowStride + (x / 2) * vp.pixelStride).toInt() and 0xFF
        return Regions.yuvToRgb(yv, uv, vv)
    }

    private fun thumbnail(proxy: ImageProxy): ByteArray {
        val plane = proxy.planes[0]
        val buf = plane.buffer
        val size = DuplicateFrameMeter.SIZE
        return ByteArray(size * size) { i ->
            val x = (i % size) * proxy.width / size
            val y = (i / size) * proxy.height / size
            buf.get(y * plane.rowStride + x * plane.pixelStride)
        }
    }

    /** Device and frame checks for Signals.camprobe. Reads /proc, so call it off the main thread. */
    fun camProbe(): CamProbe = CamProbe(
        apiTamperFlags = CamProbeRules.flags(DeviceProbe.facts()),
        deviceLabel = DeviceProbe.label(if (backMode) "back" else "front"),
        duplicateFrameRatio = duplicates.ratio(),
    )

    fun regionMeans(): List<RegionFrame> = synchronized(regionFrames) { regionFrames.toList() }

    @androidx.annotation.OptIn(ExperimentalGetImage::class)
    private fun analyzeIdFrame(proxy: ImageProxy, media: android.media.Image, rotation: Int) {
        val generation = qrState.generation()
        val started = SystemClock.elapsedRealtime()
        val luma = meanLuma(proxy).toDouble()
        val plane = proxy.planes[0]
        val buf = plane.buffer.duplicate()
        val bytes = ByteArray(buf.remaining()).also { buf.get(it) }
        val sharp = ImageChecks.laplacianVariance(bytes, proxy.width, proxy.height, plane.rowStride)
        val glare = ImageChecks.glareFraction(bytes, proxy.width, proxy.height, plane.rowStride)
        val qrTask = qrScanner.process(InputImage.fromMediaImage(media, rotation))
        val faceTask = if (idQrOnly) null else cardFaceDetector.process(InputImage.fromMediaImage(media, rotation))
        val width = if (rotation % 180 == 0) proxy.width else proxy.height
        val height = if (rotation % 180 == 0) proxy.height else proxy.width
        val cardHeight = minOf(height.toFloat(), width / 1.586f)
        val top = (height - cardHeight) / 2f
        Tasks.whenAllComplete(listOfNotNull(qrTask, faceTask)).addOnCompleteListener(analysisExecutor) {
            try {
                if (generation != qrState.generation() || !backMode) return@addOnCompleteListener
                if ((_idQuality.value?.frameTimeNs ?: 0L) >= proxy.imageInfo.timestamp) return@addOnCompleteListener
                if (!qrTask.isSuccessful || faceTask?.isSuccessful == false) { _idQuality.value = null; return@addOnCompleteListener }
                val qr = qrTask.result.firstNotNullOfOrNull { code ->
                    val box = code.boundingBox
                    code.rawValue?.takeIf { raw -> box != null && box.top >= top && box.bottom <= top + cardHeight && CccdQr.parse(raw) != null }
                }
                val faces = faceTask?.result.orEmpty().filter { it.boundingBox.top >= top && it.boundingBox.bottom <= top + cardHeight }
                qrState.update(generation, qr, proxy.imageInfo.timestamp)
                _idQuality.value = IdQuality(sharp, glare, qr, faces.size == 1 || qr != null,
                    portraitPresent = faces.size == 1, brightness = luma,
                    tilted = faces.singleOrNull()?.let { kotlin.math.abs(it.headEulerAngleZ) > 15f } ?: false,
                    frameTimeNs = proxy.imageInfo.timestamp,
                    qrRecentlySeen = qrState.recentlySeen(generation, proxy.imageInfo.timestamp))
                if (BuildConfig.DEBUG && started - lastCardDiagnosticMs >= 1000) {
                    lastCardDiagnosticMs = started
                    // Fixed technical flags only; never log QR contents or document fields.
                    Log.d("VeriClueCardScan", "size=${proxy.width}x${proxy.height} rotation=$rotation crop=${proxy.cropRect} qrOnly=$idQrOnly candidate=${qrTask.result.any { it.boundingBox != null }} decoded=${qrTask.result.any { it.rawValue != null }} formatValid=${qrTask.result.any { CccdQr.parse(it.rawValue) != null }} qrRead=${qr != null} portrait=${faces.size == 1} sharp=${sharp >= IdQuality.MIN_SHARPNESS} glareClear=${glare <= IdQuality.MAX_GLARE} bright=${luma >= 45} elapsedMs=${SystemClock.elapsedRealtime() - started}")
                }
            } finally { proxy.close() }
        }
    }

    private fun cropCardBitmap(source: Bitmap): Bitmap {
        val targetHeight = minOf(source.height, (source.width / 1.586f).toInt())
        val targetWidth = minOf(source.width, (targetHeight * 1.586f).toInt())
        val crop = Bitmap.createBitmap(source, (source.width - targetWidth) / 2, (source.height - targetHeight) / 2, targetWidth, targetHeight)
        val ratio = minOf(1f, 2560f / maxOf(crop.width, crop.height))
        return if (ratio == 1f) crop else Bitmap.createScaledBitmap(crop, (crop.width * ratio).toInt(), (crop.height * ratio).toInt(), true)
    }

    private fun bitmapQuality(bitmap: Bitmap): IdQuality {
        val ratio = minOf(1f, 640f / maxOf(bitmap.width, bitmap.height))
        val small = Bitmap.createScaledBitmap(bitmap, (bitmap.width * ratio).toInt(), (bitmap.height * ratio).toInt(), true)
        val pixels = IntArray(small.width * small.height)
        small.getPixels(pixels, 0, small.width, 0, 0, small.width, small.height)
        val luma = ByteArray(pixels.size) { i -> val c = pixels[i]; (((c shr 16 and 255) * 77 + (c shr 8 and 255) * 150 + (c and 255) * 29) shr 8).toByte() }
        val q = IdQuality(ImageChecks.laplacianVariance(luma, small.width, small.height, small.width),
            ImageChecks.glareFraction(luma, small.width, small.height, small.width), null,
            brightness = luma.sumOf { it.toInt() and 255 }.toDouble() / luma.size)
        if (small !== bitmap) small.recycle()
        return q
    }

    private fun meanLuma(proxy: ImageProxy): Float {
        val plane = proxy.planes[0]
        val buf = plane.buffer.duplicate()
        var sum = 0L
        var n = 0
        val step = 16
        var i = 0
        while (i < buf.limit()) {
            sum += buf.get(i).toInt() and 0xFF
            n++
            i += step
        }
        return if (n == 0) 0f else sum.toFloat() / n
    }

    private fun toJpeg(proxy: ImageProxy, rotation: Int): ByteArray {
        var bmp: Bitmap = proxy.toBitmap()
        if (rotation != 0) {
            bmp = Bitmap.createBitmap(bmp, 0, 0, bmp.width, bmp.height, Matrix().apply { postRotate(rotation.toFloat()) }, true)
        }
        return ByteArrayOutputStream().use { out ->
            bmp.compress(Bitmap.CompressFormat.JPEG, 92, out)
            out.toByteArray()
        }
    }
}
