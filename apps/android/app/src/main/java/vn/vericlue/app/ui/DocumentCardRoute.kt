package vn.vericlue.app.ui

import android.app.Activity
import android.content.Context
import android.content.ContextWrapper
import androidx.activity.compose.BackHandler
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.IntentSenderRequest
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.runtime.Composable
import androidx.compose.runtime.DisposableEffect
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.rememberUpdatedState
import androidx.compose.runtime.setValue
import androidx.compose.ui.platform.LocalContext
import com.google.mlkit.vision.documentscanner.GmsDocumentScanning
import com.google.mlkit.vision.documentscanner.GmsDocumentScanningResult
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.Job
import kotlinx.coroutines.ensureActive
import kotlinx.coroutines.currentCoroutineContext
import kotlinx.coroutines.launch
import kotlinx.coroutines.suspendCancellableCoroutine
import kotlinx.coroutines.withContext
import kotlinx.coroutines.withTimeout
import kotlin.coroutines.resume
import kotlin.coroutines.resumeWithException
import vn.vericlue.app.capture.DocumentCaptureAttempt
import vn.vericlue.app.capture.cardDocumentScannerOptions
import vn.vericlue.app.capture.discardDocumentImage
import vn.vericlue.app.capture.readDocumentJpeg
import vn.vericlue.app.ui.screens.DocumentCardScreen
import vn.vericlue.app.ui.screens.DocumentScanStage

/** Native document capture; processing one returned JPEG never reopens the camera automatically. */
@Composable
fun DocumentCardRoute(
    onBack: () -> Unit, onStop: () -> Unit, onFallback: () -> Unit,
    onImage: suspend (ByteArray) -> String?,
) {
    val context = LocalContext.current
    val scope = rememberCoroutineScope()
    val attempt = remember { DocumentCaptureAttempt() }
    val consumeImage by rememberUpdatedState(onImage)
    var stage by remember { mutableStateOf(DocumentScanStage.Preparing) }
    var message by remember { mutableStateOf<String?>(null) }
    var pending by remember { mutableStateOf<Job?>(null) }
    val scanner = remember {
        GmsDocumentScanning.getClient(cardDocumentScannerOptions())
    }
    fun leave(action: () -> Unit) {
        attempt.close()
        pending?.cancel()
        action()
    }
    DisposableEffect(attempt) { onDispose { attempt.close(); pending?.cancel() } }
    BackHandler { leave(onBack) }
    val launcher = rememberLauncherForActivityResult(ActivityResultContracts.StartIntentSenderForResult()) { result ->
        val pages = runCatching {
            result.data?.let(GmsDocumentScanningResult::fromActivityResultIntent)?.pages.orEmpty()
        }.getOrDefault(emptyList())
        val ticket = attempt.result()
        if (ticket == null) {
            pages.forEach { discardDocumentImage(context, it.imageUri) }
        } else if (result.resultCode != Activity.RESULT_OK) {
            pages.forEach { discardDocumentImage(context, it.imageUri) }
            attempt.retry(ticket)
            stage = DocumentScanStage.Ready
            message = null
        } else if (pages.size != 1) {
            pages.forEach { discardDocumentImage(context, it.imageUri) }
            attempt.retry(ticket)
            stage = DocumentScanStage.Failed
            message = "Vui lòng quét một mặt thẻ có chân dung và mã QR."
        } else {
            stage = DocumentScanStage.Reading
            message = null
            val uri = pages.single().imageUri
            pending = scope.launch {
                try {
                    val bytes = withContext(Dispatchers.IO) { readDocumentJpeg(context, uri) }
                    currentCoroutineContext().ensureActive()
                    if (!attempt.current(ticket)) return@launch
                    val retry = consumeImage(bytes)
                    currentCoroutineContext().ensureActive()
                    if (!attempt.current(ticket)) return@launch
                    if (retry == null) attempt.finish(ticket)
                    else {
                        attempt.retry(ticket)
                        stage = DocumentScanStage.Failed
                        message = retry
                    }
                } catch (cancelled: CancellationException) {
                    throw cancelled
                } catch (_: Exception) {
                    if (attempt.current(ticket)) {
                        attempt.retry(ticket)
                        stage = DocumentScanStage.Failed
                        message = "Chưa đọc được ảnh thẻ. Quét lại hoặc dùng camera của ứng dụng."
                    }
                } finally { discardDocumentImage(context, uri) }
            }
        }
    }
    fun openScanner() {
        val ticket = attempt.begin() ?: return
        stage = DocumentScanStage.Preparing
        message = null
        pending = scope.launch {
            try {
                val activity = requireNotNull(context.scannerActivity())
                val intent = withTimeout(45_000) {
                    suspendCancellableCoroutine { continuation ->
                        scanner.getStartScanIntent(activity)
                            .addOnSuccessListener { if (continuation.isActive) continuation.resume(it) }
                            .addOnFailureListener { if (continuation.isActive) continuation.resumeWithException(it) }
                    }
                }
                if (attempt.opened(ticket)) {
                    stage = DocumentScanStage.Scanning
                    launcher.launch(IntentSenderRequest.Builder(intent).build())
                }
            } catch (cancelled: CancellationException) {
                // Timeout is recoverable; leaving the route must stay cancelled.
                if (cancelled !is kotlinx.coroutines.TimeoutCancellationException) throw cancelled
                if (attempt.current(ticket)) {
                    attempt.retry(ticket)
                    stage = DocumentScanStage.Failed
                    message = "Bộ quét chưa sẵn sàng. Kiểm tra kết nối và thử lại."
                }
            } catch (_: Exception) {
                if (attempt.current(ticket)) {
                    attempt.retry(ticket)
                    stage = DocumentScanStage.Failed
                    message = "Chưa mở được bộ quét. Thử lại hoặc dùng camera của ứng dụng."
                }
            }
        }
    }
    LaunchedEffect(Unit) { openScanner() }
    DocumentCardScreen(stage, message, onBack = { leave(onBack) }, onStop = { leave(onStop) },
        onRetry = ::openScanner, onFallback = { leave(onFallback) })
}

private tailrec fun Context.scannerActivity(): Activity? = when (this) {
    is Activity -> this
    is ContextWrapper -> baseContext.scannerActivity()
    else -> null
}
