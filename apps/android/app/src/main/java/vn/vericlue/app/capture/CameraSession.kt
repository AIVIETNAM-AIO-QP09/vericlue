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
import kotlinx.coroutines.CompletableDeferred
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import vn.vericlue.app.data.api.FrameTime

/**
 * One camera session for the whole face part: the front camera stays on from framing to the
 * end of the voice step (ADR-0013 principle 4). Screens only show its preview.
 *
 * Not done yet (plan phase 3/9): AE/AWB lock during the colour flash, region_means, camprobe.
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
    private var analysisStartMs = 0.0

    fun bind(owner: LifecycleOwner) {
        if (bound) return
        controller.cameraSelector = CameraSelector.DEFAULT_FRONT_CAMERA
        controller.setEnabledUseCases(CameraController.IMAGE_ANALYSIS or CameraController.VIDEO_CAPTURE)
        controller.imageAnalysisBackpressureStrategy = ImageAnalysis.STRATEGY_KEEP_ONLY_LATEST
        controller.setImageAnalysisAnalyzer(analysisExecutor, ::analyze)
        controller.bindToLifecycle(owner)
        bound = true
    }

    /** Rear camera for the ID card (APP-04), front camera for the face part. Main thread only. */
    fun useBackCamera(back: Boolean) {
        if (backMode == back) return
        backMode = back
        _qr.value = null
        controller.cameraSelector = if (back) CameraSelector.DEFAULT_BACK_CAMERA else CameraSelector.DEFAULT_FRONT_CAMERA
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
        if (recording != null) return
        val file = File(context.cacheDir, "face_${System.currentTimeMillis()}.mp4").also { videoFile = it }
        synchronized(frames) { frames.clear() }
        firstFrameNs = 0L
        recordingFrames = true
        recording = controller.startRecording(
            FileOutputOptions.Builder(file).build(),
            AudioConfig.AUDIO_DISABLED,
            ContextCompat.getMainExecutor(context),
        ) { event -> if (event is VideoRecordEvent.Finalize && event.hasError()) videoFile = null }
    }

    fun stopRecording() {
        recordingFrames = false
        recording?.stop()
        recording = null
    }

    fun recordedVideo(): File? = videoFile?.takeIf { it.exists() && it.length() > 0 }

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
        val request = jpegRequest
        if (request != null) {
            jpegRequest = null
            request.complete(toJpeg(proxy, rotation))
        }
        detector.process(InputImage.fromMediaImage(media, rotation))
            .addOnSuccessListener { faces ->
                val face = faces.maxByOrNull { it.boundingBox.width() }
                _face.value = if (face == null) {
                    FaceSignal(0, 0f, 0f, 0f, 0f, luma, ts)
                } else {
                    val b = face.boundingBox
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
            }
            .addOnCompleteListener { proxy.close() }
    }

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
