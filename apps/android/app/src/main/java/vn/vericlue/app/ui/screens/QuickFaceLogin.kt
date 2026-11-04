package vn.vericlue.app.ui.screens

import android.Manifest
import android.content.pm.PackageManager
import android.os.SystemClock
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.outlined.Face
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.semantics.LiveRegionMode
import androidx.compose.ui.semantics.liveRegion
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import androidx.compose.ui.window.Dialog
import androidx.compose.ui.window.DialogProperties
import androidx.core.content.ContextCompat
import androidx.lifecycle.LifecycleOwner
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.delay
import kotlinx.coroutines.launch
import kotlinx.coroutines.withTimeoutOrNull
import vn.vericlue.app.capture.*
import vn.vericlue.app.data.api.ApiError
import vn.vericlue.app.data.api.ApiResult
import vn.vericlue.app.flow.*
import vn.vericlue.app.ui.components.CameraXPreview
import vn.vericlue.app.ui.components.PrimaryButton
import vn.vericlue.app.ui.theme.Vc
import vn.vericlue.app.ui.theme.VcType

enum class QuickFaceStage { Consent, Preparing, Aligning, Recording, Checking, Error }

/** One preview and one popup for the entire passive login. Server verification still owns success. */
@Composable
fun QuickFaceLogin(
    camera: CameraSession,
    live: LiveFlow,
    owner: LifecycleOwner,
    onPrepare: suspend () -> ApiError?,
    onSubmit: suspend () -> Unit,
    onCancel: () -> Unit,
) {
    val context = LocalContext.current
    val scope = rememberCoroutineScope()
    var stage by remember { mutableStateOf(QuickFaceStage.Consent) }
    var hint by remember { mutableStateOf("Nhìn thẳng vào camera") }
    var ready by remember { mutableStateOf(false) }
    var attempt by remember { mutableStateOf(0) }
    var permission by remember { mutableStateOf(false) }
    var frontalReady by remember { mutableStateOf(false) }
    var terminal by remember { mutableStateOf(false) }
    var frontalJob by remember { mutableStateOf<kotlinx.coroutines.Job?>(null) }
    val prepare by rememberUpdatedState(onPrepare)
    val submit by rememberUpdatedState(onSubmit)
    fun failure(message: String) { hint = message; stage = QuickFaceStage.Error }
    val askCamera = rememberLauncherForActivityResult(ActivityResultContracts.RequestPermission()) { granted ->
        permission = granted
        if (!granted) failure("Cho phép camera để đăng nhập bằng khuôn mặt.")
    }
    fun begin() {
        if (stage != QuickFaceStage.Consent && stage != QuickFaceStage.Error) return
        frontalReady = false; terminal = false; ready = false
        stage = QuickFaceStage.Preparing
        attempt++
        permission = ContextCompat.checkSelfPermission(context, Manifest.permission.CAMERA) == PackageManager.PERMISSION_GRANTED
        if (!permission) askCamera.launch(Manifest.permission.CAMERA)
    }
    DisposableEffect(camera) {
        onDispose {
            frontalJob?.cancel()
            camera.stopRecording(); camera.lockAeAwb(false)
            camera.unbind(); camera.deleteVideo()
        }
    }
    LaunchedEffect(attempt, permission) {
        if (attempt == 0 || !permission || stage != QuickFaceStage.Preparing) return@LaunchedEffect
        val error = prepare()
        if (error != null) {
            failure(AccountAccessRules.error(ApiResult.Err(error)))
        } else if (!camera.start(owner, back = false)) {
            failure("Chưa mở được camera. Vui lòng thử lại.")
        } else {
            ready = true
            stage = QuickFaceStage.Aligning
        }
    }
    LaunchedEffect(stage) {
        if (stage == QuickFaceStage.Aligning) {
            val stable = StableFaceGate()
            while (true) {
                val now = SystemClock.elapsedRealtime()
                val face = camera.face.value
                hint = when (QualityGate.evaluate(face, now)) {
                    FramingState.NoFace -> "Nhìn vào camera để tiếp tục"
                    FramingState.LowLight -> "Chọn nơi đủ sáng"
                    FramingState.TooFar -> "Đưa điện thoại gần hơn một chút"
                    FramingState.TooClose -> "Đưa điện thoại xa hơn một chút"
                    FramingState.MultipleFaces -> "Chỉ giữ một người trước camera"
                    FramingState.IncompleteFace -> "Để camera thấy toàn bộ khuôn mặt"
                    FramingState.NotStraight -> "Nhìn thẳng vào camera"
                    FramingState.OffCenter -> "Giữ khuôn mặt ở giữa camera"
                    FramingState.Good -> "Giữ điện thoại ổn định"
                }
                // Sensor geometry/landmarks/freshness remain mandatory; no oval-fill constraint.
                if (stable.update(face, now)) { stage = QuickFaceStage.Recording; break }
                delay(50)
            }
        } else if (stage == QuickFaceStage.Checking) {
            // This callback waits for the real API result and account access exchange.
            submit()
        }
    }
    fun incomplete() {
        if (terminal) return
        terminal = true
        frontalJob?.cancel()
        camera.stopRecording(); camera.lockAeAwb(false); camera.deleteVideo()
        live.dropFaceAttempt()
        failure("Chưa thu đủ khuôn mặt. Nhìn thẳng vào camera rồi thử lại.")
    }
    Dialog(onDismissRequest = onCancel, properties = DialogProperties(
        usePlatformDefaultWidth = false, dismissOnClickOutside = false,
    )) {
        QuickFaceLoginContent(stage, hint, onStart = ::begin, onCancel = onCancel,
            camera = {
                // Kept at the same composition position and size through all capture phases.
                CameraXPreview(camera, Modifier.fillMaxSize())
                if (!ready) Box(Modifier.fillMaxSize().background(Vc.colors.surfaceSubtle), contentAlignment = Alignment.Center) {
                    Icon(Icons.Outlined.Face, null, Modifier.size(64.dp), tint = Vc.colors.accent)
                }
            }, progress = {
                if (stage == QuickFaceStage.Recording) key(attempt) {
                    FaceTimelineScreen(
                        timeline = FaceTimeline.passive(), onStop = onCancel,
                        onStart = { live.colorEvents.clear(); camera.startRecording() },
                        recordingStartMs = { camera.recordingStartMs() }, onPainted = { _, _ -> },
                        onFrontal = {
                            frontalJob = scope.launch {
                                val shot = try { withTimeoutOrNull(1500) { camera.captureJpeg() } }
                                catch (cancelled: CancellationException) { throw cancelled }
                                catch (_: Exception) { null }
                                if (!terminal) {
                                    if (shot != null) { live.frontalJpeg = shot; frontalReady = true }
                                    else incomplete()
                                }
                            }
                        },
                        onBaselineDone = { camera.lockAeAwb(true) },
                        onColorsDone = { camera.lockAeAwb(false) },
                        onDone = {
                            if (!terminal) {
                                if (!frontalReady || live.frontalJpeg == null) incomplete()
                                else {
                                    terminal = true
                                    camera.stopRecording(); camera.lockAeAwb(false)
                                    stage = QuickFaceStage.Checking
                                }
                            }
                        },
                        onNoRecording = ::incomplete, faceSignal = { camera.face.value },
                        onIncomplete = { incomplete() },
                        captureContent = { captured -> LinearProgressIndicator(progress = { captured }, modifier = Modifier.fillMaxWidth()) },
                    )
                } else if (stage in setOf(QuickFaceStage.Preparing, QuickFaceStage.Checking)) {
                    LinearProgressIndicator(Modifier.fillMaxWidth())
                }
            },
        )
    }
}

/** Stateless surface for snapshots; completion is never inferred from animation progress. */
@Composable
fun QuickFaceLoginContent(
    stage: QuickFaceStage,
    hint: String,
    onStart: () -> Unit,
    onCancel: () -> Unit,
    camera: @Composable BoxScope.() -> Unit = {},
    progress: @Composable () -> Unit = {},
) {
    var details by remember { mutableStateOf(false) }
    // Dialogs center their content; a fixed available height also prevents the preview moving
    // when consent buttons disappear or the status text changes.
    Surface(Modifier.padding(20.dp).widthIn(max = 360.dp).fillMaxWidth()
        .heightIn(max = 680.dp).fillMaxHeight().testTag("quick-face-panel"),
        shape = RoundedCornerShape(28.dp), color = Vc.colors.surface) {
        Column(Modifier.verticalScroll(rememberScrollState()).padding(24.dp),
            horizontalAlignment = Alignment.CenterHorizontally, verticalArrangement = Arrangement.spacedBy(16.dp)) {
            Text("Đăng nhập khuôn mặt", style = VcType.section, color = Vc.colors.ink)
            Box(Modifier.width(168.dp).height(224.dp).clip(RoundedCornerShape(24.dp))
                .background(Vc.colors.surfaceSubtle).testTag("quick-face-preview"), content = camera)
            Box(Modifier.fillMaxWidth().height(4.dp)) { progress() }
            val message = when (stage) {
                QuickFaceStage.Consent -> "Cho phép VeriClue xử lý khuôn mặt và giọng nói khi cần để xác minh lượt đăng nhập này."
                QuickFaceStage.Preparing -> "Đang mở camera…"
                QuickFaceStage.Aligning, QuickFaceStage.Error -> hint
                QuickFaceStage.Recording -> "Đang quét · Giữ điện thoại ổn định"
                QuickFaceStage.Checking -> "Đang xác minh…"
            }
            Text(message, style = VcType.bodySmall, color = Vc.colors.ink, textAlign = TextAlign.Center,
                modifier = Modifier.semantics { liveRegion = LiveRegionMode.Polite })
            if (stage == QuickFaceStage.Consent) {
                TextButton(onClick = { details = !details }) { Text("Quyền riêng tư", style = VcType.label) }
                if (details) Text("Thông báo ${PrivacyNotice.VERSION}. Video được gửi đến máy chủ để đối chiếu tài khoản. Giọng nói chỉ được yêu cầu khi cần bổ sung xác minh. Hủy lượt quét để yêu cầu rút lại đồng ý cho phiên này.",
                    style = VcType.bodySmall, color = Vc.colors.muted)
                PrimaryButton("Đồng ý và quét", onStart)
            } else if (stage == QuickFaceStage.Error) PrimaryButton("Thử lại", onStart)
            TextButton(onClick = onCancel, modifier = Modifier.heightIn(min = 48.dp)) { Text("Hủy", style = VcType.label) }
        }
    }
}
