package vn.vericlue.app.capture

import android.annotation.SuppressLint
import android.content.Context
import android.graphics.Bitmap
import android.graphics.Matrix
import android.hardware.camera2.CameraCharacteristics
import androidx.camera.camera2.interop.Camera2CameraInfo
import androidx.camera.camera2.interop.ExperimentalCamera2Interop
import androidx.camera.core.CameraSelector
import androidx.camera.core.ExperimentalGetImage
import androidx.camera.core.ImageAnalysis
import androidx.camera.core.ImageProxy
import androidx.camera.video.FileOutputOptions
import androidx.camera.video.Recording
import androidx.camera.video.VideoRecordEvent
import androidx.camera.view.CameraController
import androidx.camera.view.LifecycleCameraController
import androidx.camera.view.video.AudioConfig
import androidx.core.content.ContextCompat
import androidx.lifecycle.LifecycleOwner
import com.google.mlkit.vision.barcode.BarcodeScannerOptions
import com.google.mlkit.vision.barcode.BarcodeScanning
import com.google.mlkit.vision.barcode.common.Barcode
import com.google.mlkit.vision.common.InputImage
import com.google.mlkit.vision.face.FaceDetection
import com.google.mlkit.vision.face.FaceDetectorOptions
import java.io.ByteArrayOutputStream
import java.io.File
import java.util.concurrent.Executors
import kotlin.coroutines.resume
import kotlinx.coroutines.CompletableDeferred
import kotlinx.coroutines.suspendCancellableCoroutine
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import vn.vericlue.app.data.api.FrameTime

/**
 * One camera session for the whole face part: the front camera stays on from framing to the
 * end of the voice step (ADR-0013 principle 4). Screens only show its preview.
 *
 * Also collects frame_times, region_means and the camprobe facts sent with the signals.
 * Not done yet: the dot path (waits for LIVE-01) and media signing (SEC-02).
 */
class CameraSession(private val context: Context) {
    val controller = LifecycleCameraController(context)
    private val analysisExecutor = Executors.newSingleThreadExecutor()
    private val detector = FaceDetection.getClient(
        FaceDetectorOptions.Builder()
            .setPerformanceMode(FaceDetectorOptions.PERFORMANCE_MODE_FAST)
            .setMinFaceSize(0.15f)
            .build(),
    )

    private val qrScanner = BarcodeScanning.getClient(
        BarcodeScannerOptions.Builder().setBarcodeFormats(Barcode.FORMAT_QR_CODE).build(),
    )
    @Volatile private var backMode = false
    private var idRequest: CompletableDeferred<Pair<ByteArray, IdQuality>>? = null
    private val _qr = MutableStateFlow<String?>(null)

    /** Last QR text seen by the rear camera (ID card back side). */
    val qr: StateFlow<String?> = _qr

    private val _face = MutableStateFlow<FaceSignal?>(null)
    val face: StateFlow<FaceSignal?> = _face

    private var bound = false
    private var preview: androidx.camera.view.PreviewView? = null

    /**
     * One PreviewView reused by every screen. A new view per screen makes the controller
     * reconfigure the camera, which cancels a running recording.
     */
    fun previewView(activityContext: Context): androidx.camera.view.PreviewView =
        preview ?: androidx.camera.view.PreviewView(activityContext).apply {
            implementationMode = androidx.camera.view.PreviewView.ImplementationMode.COMPATIBLE
            scaleType = androidx.camera.view.PreviewView.ScaleType.FILL_CENTER
            controller = this@CameraSession.controller
        }.also { preview = it }
    private var jpegRequest: CompletableDeferred<ByteArray>? = null

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

    /**
     * Opens the front camera (face part) or the rear camera (ID card, APP-04). Main thread only.
     * Never throws: falls back to the other camera when the preferred one is missing, drops video
     * when the device cannot record alongside analysis, and returns false when no camera can be
     * opened, so the caller shows an error screen instead of crashing.
     */
    suspend fun start(owner: LifecycleOwner, back: Boolean): Boolean {
        if (!awaitInitialized()) return false
        if (backMode != back) _qr.value = null
        backMode = back
        val preferred = if (back) CameraSelector.DEFAULT_BACK_CAMERA else CameraSelector.DEFAULT_FRONT_CAMERA
        val other = if (back) CameraSelector.DEFAULT_FRONT_CAMERA else CameraSelector.DEFAULT_BACK_CAMERA
        val selector = listOf(preferred, other).firstOrNull { runCatching { controller.hasCamera(it) }.getOrDefault(false) }
            ?: return false
        if (!bound) {
            controller.imageAnalysisBackpressureStrategy = ImageAnalysis.STRATEGY_KEEP_ONLY_LATEST
            controller.setImageAnalysisAnalyzer(analysisExecutor, ::analyze)
        }
        for (useCases in listOf(CameraController.IMAGE_ANALYSIS or CameraController.VIDEO_CAPTURE, CameraController.IMAGE_ANALYSIS)) {
            val ok = runCatching {
                controller.setEnabledUseCases(useCases)
                controller.cameraSelector = selector
                if (!bound) controller.bindToLifecycle(owner)
            }.isSuccess
            if (ok) {
                bound = true
                videoEnabled = useCases and CameraController.VIDEO_CAPTURE != 0
                usedFallbackCamera = selector != preferred
                return true
            }
        }
        return false
    }

    private suspend fun awaitInitialized(): Boolean = suspendCancellableCoroutine { cont ->
        val future = controller.initializationFuture
        future.addListener(
            { cont.resume(runCatching { future.get() }.isSuccess) },
            ContextCompat.getMainExecutor(context),
        )
    }

    /** Photo of the card plus local quality checks, from the next analysed rear-camera frame. */
    suspend fun captureId(): Pair<ByteArray, IdQuality> {
        val req = CompletableDeferred<Pair<ByteArray, IdQuality>>()
        idRequest = req
        return req.await()
    }

    fun unbind() {
        stopRecording()
        controller.unbind()
        bound = false
        _face.value = null
    }

    /** JPEG of the next analysed frame (upright, high quality). Used for the frontal still. */
    suspend fun captureJpeg(): ByteArray {
        val req = CompletableDeferred<ByteArray>()
        jpegRequest = req
        return req.await()
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

    /** Starts the MP4 recording that the server receives as `video` in /media. Audio off. */
    @SuppressLint("MissingPermission")
    fun startRecording() {
        if (recording != null || !videoEnabled) return
        val file = File(context.cacheDir, "face_${System.currentTimeMillis()}.mp4").also { videoFile = it }
        synchronized(frames) { frames.clear() }
        synchronized(regionFrames) { regionFrames.clear() }
        firstFrameNs = 0L
        recordingFrames = true
        recording = runCatching {
            controller.startRecording(
                FileOutputOptions.Builder(file).build(),
                AudioConfig.AUDIO_DISABLED,
                ContextCompat.getMainExecutor(context),
            ) { event -> if (event is VideoRecordEvent.Finalize && event.hasError()) videoFile = null }
        }.getOrNull()
        if (recording == null) videoFile = null
    }

    fun stopRecording() {
        recordingFrames = false
        recording?.stop()
        recording = null
    }

    fun recordedVideo(): File? = videoFile?.takeIf { it.exists() && it.length() > 0 }

    /** Deletes every face video in the cache: once the server has it, or when the attempt is dropped. */
    fun deleteVideo() {
        videoFile = null
        context.cacheDir.listFiles { f -> f.name.startsWith("face_") && f.name.endsWith(".mp4") }?.forEach { it.delete() }
    }

    fun frameTimes(): List<FrameTime> = synchronized(frames) { frames.toList() }

    /** Facts the server needs to trust the timing, sent as Signals.client_quality. */
    @androidx.annotation.OptIn(ExperimentalCamera2Interop::class)
    fun clientQuality(): Map<String, String> {
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
            "video" to if (recordedVideo() != null) "mp4" else "missing",
            "frames_recorded" to frameTimes().size.toString(),
            "camera_fallback" to usedFallbackCamera.toString(),
        )
    }

    @androidx.annotation.OptIn(ExperimentalGetImage::class)
    private fun analyze(proxy: ImageProxy) {
        val media = proxy.image
        if (media == null) {
            proxy.close()
            return
        }
        if (analyzedFrames == 0) analysisStartMs = CaptureClock.nowMs()
        analyzedFrames++
        val ts = proxy.imageInfo.timestamp
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
        val luma = meanLuma(proxy)
        duplicates.add(thumbnail(proxy))
        val request = jpegRequest
        if (request != null) {
            jpegRequest = null
            request.complete(toJpeg(proxy, rotation))
        }
        // One listener on the analysis thread: the frame must stay open while regions are measured.
        detector.process(InputImage.fromMediaImage(media, rotation))
            .addOnCompleteListener(analysisExecutor) { task ->
                try {
                    val faces = if (task.isSuccessful) task.result else emptyList()
                    val face = faces.maxByOrNull { it.boundingBox.width() }
                    _face.value = if (face == null) {
                        FaceSignal(0, 0f, 0f, 0f, 0f, luma, ts)
                    } else {
                        val b = face.boundingBox
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
                            luma = luma,
                            timestampNs = ts,
                        )
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
        val request = idRequest
        if (request != null) {
            idRequest = null
            val plane = proxy.planes[0]
            val buf = plane.buffer.duplicate()
            val luma = ByteArray(buf.remaining()).also { buf.get(it) }
            val quality = IdQuality(
                sharpness = ImageChecks.laplacianVariance(luma, proxy.width, proxy.height, plane.rowStride),
                glareFraction = ImageChecks.glareFraction(luma, proxy.width, proxy.height, plane.rowStride),
                qr = _qr.value,
            )
            request.complete(toJpeg(proxy, rotation) to quality)
        }
        qrScanner.process(InputImage.fromMediaImage(media, rotation))
            .addOnSuccessListener { codes -> codes.firstNotNullOfOrNull { it.rawValue }?.let { _qr.value = it } }
            .addOnCompleteListener { proxy.close() }
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
