package vn.vericlue.app.ui

import androidx.compose.animation.fadeIn
import androidx.compose.animation.fadeOut
import androidx.compose.animation.core.tween
import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.ExperimentalLayoutApi
import androidx.compose.foundation.layout.FlowRow
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.FilterChip
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.unit.dp
import androidx.navigation.NavHostController
import androidx.navigation.compose.NavHost
import androidx.navigation.compose.composable
import androidx.navigation.compose.rememberNavController
import android.Manifest
import android.content.Context
import android.content.pm.PackageManager
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.runtime.CompositionLocalProvider
import androidx.compose.runtime.DisposableEffect
import androidx.lifecycle.Lifecycle
import androidx.lifecycle.LifecycleEventObserver
import androidx.navigation.compose.currentBackStackEntryAsState
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.platform.LocalLifecycleOwner
import androidx.core.content.ContextCompat
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.delay
import kotlinx.coroutines.withContext
import kotlinx.coroutines.launch
import kotlinx.coroutines.withTimeoutOrNull
import vn.vericlue.app.BuildConfig
import vn.vericlue.app.capture.CameraSession
import vn.vericlue.app.capture.CccdInfo
import vn.vericlue.app.capture.CccdQr
import vn.vericlue.app.capture.IdQuality
import vn.vericlue.app.ui.screens.idFields
import vn.vericlue.app.capture.ColorSchedule
import vn.vericlue.app.capture.QualityGate
import vn.vericlue.app.capture.WavRecorder
import vn.vericlue.app.data.api.ColorEvent
import vn.vericlue.app.data.api.SessionApi
import vn.vericlue.app.flow.FramingState
import vn.vericlue.app.flow.LiveFlow
import vn.vericlue.app.flow.Next
import vn.vericlue.app.flow.errorRoute
import vn.vericlue.app.ui.components.CameraXPreview
import vn.vericlue.app.ui.components.LocalCameraFeed
import vn.vericlue.app.flow.DemoOutcome
import vn.vericlue.app.flow.FlowRules
import vn.vericlue.app.flow.Purpose
import vn.vericlue.app.flow.Routes
import vn.vericlue.app.flow.TurnDir
import vn.vericlue.app.ui.components.VcScreen
import vn.vericlue.app.ui.screens.AuthScreen
import vn.vericlue.app.ui.screens.BankOpenedScreen
import vn.vericlue.app.ui.screens.BankStartScreen
import vn.vericlue.app.ui.screens.CheckingScreen
import vn.vericlue.app.ui.screens.ConfirmInfoScreen
import vn.vericlue.app.ui.screens.ConsentScreen
import vn.vericlue.app.ui.screens.EditInfoScreen
import vn.vericlue.app.ui.screens.FaceReadyScreen
import vn.vericlue.app.ui.screens.FramingScreen
import vn.vericlue.app.ui.screens.HoldStillScreen
import vn.vericlue.app.ui.screens.IdCaptureScreen
import vn.vericlue.app.ui.screens.IdReviewScreen
import vn.vericlue.app.ui.screens.IntroScreen
import vn.vericlue.app.ui.screens.Messages
import vn.vericlue.app.ui.screens.OtpScreen
import vn.vericlue.app.ui.screens.PermissionScreen
import vn.vericlue.app.ui.screens.PhoneScreen
import vn.vericlue.app.ui.screens.RetryChallengeScreen
import vn.vericlue.app.ui.screens.RetryQualityScreen
import vn.vericlue.app.ui.screens.ReviewScreen
import vn.vericlue.app.ui.screens.SplashScreen
import vn.vericlue.app.ui.screens.SuccessScreen
import vn.vericlue.app.ui.screens.TermsScreen
import vn.vericlue.app.ui.screens.TurnHeadScreen
import vn.vericlue.app.ui.screens.VoiceScreen
import vn.vericlue.app.ui.theme.Vc
import vn.vericlue.app.ui.theme.VcType

/** State shared across the flow. In-memory only; the API client replaces the fake parts (APP-01). */
class FlowState {
    var purpose by mutableStateOf(Purpose.Onboarding)
    var outcome by mutableStateOf(DemoOutcome.Pass)
    var turnOrder by mutableStateOf(newTurnOrder())
        private set

    /** Debug switch: talk to the real API instead of the offline demo (set in "Xem tất cả màn"). */
    var live by mutableStateOf(false)

    /** Mock scenario sent as X-Mock-Scenario when the API runs with USE_MOCK_MODELS=true. */
    var mockScenario by mutableStateOf("genuine")

    /** Each attempt at the face part gets a fresh challenge (ADR-0017 §2). */
    fun newChallenge() {
        turnOrder = newTurnOrder()
    }

    private fun newTurnOrder() = listOf(TurnDir.Left, TurnDir.Right).shuffled()
}

private fun NavHostController.go(route: String) = navigate(route) { launchSingleTop = true }

/** Leaves the VeriClue flow and returns to the mock bank app. */
private fun NavHostController.toBank() = navigate(Routes.BankStart) {
    popUpTo(Routes.BankStart) { inclusive = true }
}

private fun granted(context: Context, permission: String) =
    ContextCompat.checkSelfPermission(context, permission) == PackageManager.PERMISSION_GRANTED

@Composable
fun VeriClueApp() {
    val nav = rememberNavController()
    val flow = remember { FlowState() }
    val context = LocalContext.current
    val lifecycleOwner = LocalLifecycleOwner.current
    val scope = rememberCoroutineScope()
    val camera = remember { CameraSession(context.applicationContext) }
    val live = remember { LiveFlow(SessionApi(BuildConfig.API_BASE_URL)) }
    val recorder = remember { WavRecorder() }
    var hasCamera by remember { mutableStateOf(granted(context, Manifest.permission.CAMERA)) }
    var hasMic by remember { mutableStateOf(granted(context, Manifest.permission.RECORD_AUDIO)) }
    val askPermissions = rememberLauncherForActivityResult(ActivityResultContracts.RequestMultiplePermissions()) { result ->
        hasCamera = result[Manifest.permission.CAMERA] ?: hasCamera
        hasMic = result[Manifest.permission.RECORD_AUDIO] ?: hasMic
        if (!hasCamera) nav.go(Routes.ErrorCamera)
    }
    val exit = { nav.go(Routes.ExitConfirm) }

    // ID card photos and QR data stay on the phone: no API endpoint for them yet (FLOW-03).
    var idFront by remember { mutableStateOf<Pair<ByteArray, IdQuality>?>(null) }
    var idBack by remember { mutableStateOf<Pair<ByteArray, IdQuality>?>(null) }
    var cccd by remember { mutableStateOf<CccdInfo?>(null) }

    @Composable
    fun IdCaptureRoute(back: Boolean, onCaptured: () -> Unit) {
        LaunchedEffect(Unit) {
            if (!hasCamera) askPermissions.launch(arrayOf(Manifest.permission.CAMERA, Manifest.permission.RECORD_AUDIO))
        }
        LaunchedEffect(hasCamera) {
            if (hasCamera && !camera.start(lifecycleOwner, back = true)) nav.go(Routes.ErrorDevice)
        }
        IdCaptureScreen(back = back, glare = false, onBack = { nav.popBackStack() }, onCapture = {
            if (!hasCamera) {
                onCaptured()
            } else {
                scope.launch {
                    val shot = withTimeoutOrNull(3000) { camera.captureId() }
                    if (back) {
                        idBack = shot
                        cccd = CccdQr.parse(shot?.second?.qr)
                    } else {
                        idFront = shot
                    }
                    onCaptured()
                }
            }
        })
    }

    fun startFace() {
        flow.newChallenge()
        live.frontalJpeg = null
        nav.go(Routes.Framing)
    }

    /** Leaves the flow: camera off, session data dropped. */
    fun leave() {
        camera.unbind()
        recorder.stop()
        live.reset()
        nav.toBank()
    }

    fun follow(next: Next) {
        val route = when (next) {
            is Next.To -> next.route
            is Next.Fail -> errorRoute(next.error)
        }
        if (route == Routes.Success || route == Routes.Review) camera.unbind()
        nav.navigate(route) { popUpTo(Routes.Uploading) { inclusive = true } }
    }

    @Composable
    fun VoiceRoute(again: Boolean) {
        val level by recorder.level.collectAsState()
        VoiceScreen(
            onBack = exit,
            again = again,
            sentence = if (flow.live) live.voicePrompt else null,
            level = level,
            onStartRecording = { if (hasMic) recorder.start(scope) },
            onFinished = {
                val wav = recorder.stop()
                if (flow.live) {
                    if (!hasMic) nav.go(Routes.ErrorMic) else {
                        live.pendingWav = wav
                        nav.go(Routes.Uploading)
                    }
                } else {
                    if (again) flow.outcome = DemoOutcome.Pass
                    nav.go(Routes.Uploading)
                }
            },
        )
    }

    // ADR-0017 §2: going to the background while the camera or mic runs interrupts the attempt.
    val backStack by nav.currentBackStackEntryAsState()
    val currentRoute = backStack?.destination?.route
    DisposableEffect(lifecycleOwner, currentRoute) {
        val observer = LifecycleEventObserver { _, event ->
            // Act on ON_STOP itself: the activity may be recreated before it starts again.
            if (event == Lifecycle.Event.ON_STOP && FlowRules.isInterruptedBy(currentRoute)) {
                camera.stopRecording()
                recorder.stop()
                live.dropFaceAttempt()
                nav.navigate(Routes.Interrupted) { launchSingleTop = true }
            }
        }
        lifecycleOwner.lifecycle.addObserver(observer)
        onDispose { lifecycleOwner.lifecycle.removeObserver(observer) }
    }

    val cameraFeed: (@Composable (Modifier) -> Unit)? =
        if (hasCamera) { m -> CameraXPreview(camera, m) } else null

    CompositionLocalProvider(LocalCameraFeed provides cameraFeed) {
    NavHost(
        navController = nav,
        startDestination = Routes.BankStart,
        enterTransition = { fadeIn(tween(220)) },
        exitTransition = { fadeOut(tween(180)) },
        popEnterTransition = { fadeIn(tween(220)) },
        popExitTransition = { fadeOut(tween(180)) },
    ) {
        composable(Routes.BankStart) {
            BankStartScreen(onOpenAccount = { nav.go(Routes.Splash) }, onGallery = { nav.go(Routes.Gallery) })
        }
        composable(Routes.BankOpened) { BankOpenedScreen(onDone = { leave() }) }
        composable(Routes.Gallery) { GalleryScreen(nav, flow) }

        // Start
        composable(Routes.Splash) {
            SplashScreen(onDone = {
                nav.navigate(Routes.Auth) { popUpTo(Routes.Splash) { inclusive = true } }
            })
        }
        composable(Routes.Auth) {
            AuthScreen(
                onRegister = { flow.purpose = Purpose.Onboarding; nav.go(Routes.Terms) },
                onLogin = { flow.purpose = Purpose.Reauth; nav.go(Routes.Phone) },
                onRecover = { flow.purpose = Purpose.Recovery; nav.go(Routes.Phone) },
            )
        }
        composable(Routes.Terms) { TermsScreen(onBack = { nav.popBackStack() }, onAccept = { nav.go(Routes.Consent) }) }
        composable(Routes.Consent) { ConsentScreen(onBack = { nav.popBackStack() }, onContinue = { nav.go(Routes.Intro) }) }

        // Stage A: identity
        composable(Routes.Intro) { IntroScreen(onBack = { nav.popBackStack() }, onStart = { nav.go(Routes.Permission) }) }
        composable(Routes.Permission) {
            PermissionScreen(onBack = { nav.popBackStack() }, onAllow = {
                askPermissions.launch(arrayOf(Manifest.permission.CAMERA, Manifest.permission.RECORD_AUDIO))
                nav.go(Routes.Phone)
            })
        }
        composable(Routes.Phone) { PhoneScreen(onBack = { nav.popBackStack() }, onSend = { nav.go(Routes.Otp) }) }
        composable(Routes.Otp) { OtpScreen(onBack = { nav.popBackStack() }, onVerified = { nav.go(FlowRules.afterOtp(flow.purpose)) }) }
        composable(Routes.OtpError) {
            OtpScreen(onBack = { nav.popBackStack() }, onVerified = { nav.go(FlowRules.afterOtp(flow.purpose)) }, startWithError = true)
        }
        composable(Routes.IdFront) { IdCaptureRoute(back = false) { nav.go(Routes.IdFrontReview) } }
        composable(Routes.IdFrontReview) {
            IdReviewScreen(
                back = false,
                onBack = { nav.popBackStack() },
                onRetake = { nav.popBackStack() },
                onConfirm = { nav.go(Routes.IdBack) },
                photo = idFront?.first,
                quality = idFront?.second,
            )
        }
        composable(Routes.IdFrontGlare) { IdCaptureScreen(back = false, glare = true, onBack = { nav.popBackStack() }, onCapture = { nav.go(Routes.IdFront) }) }
        composable(Routes.IdBack) { IdCaptureRoute(back = true) { nav.go(Routes.IdBackReview) } }
        composable(Routes.IdBackReview) {
            IdReviewScreen(
                back = true,
                onBack = { nav.popBackStack() },
                onRetake = { nav.popBackStack() },
                onConfirm = { nav.go(Routes.Confirm) },
                photo = idBack?.first,
                quality = idBack?.second,
            )
        }
        composable(Routes.Confirm) {
            ConfirmInfoScreen(
                onBack = { nav.popBackStack() },
                onCorrect = { nav.go(Routes.FaceReady) },
                onEdit = { nav.go(Routes.EditInfo) },
                fields = idFields(cccd),
            )
        }
        composable(Routes.EditInfo) {
            EditInfoScreen(
                onBack = { nav.popBackStack() },
                onSave = { nav.go(Routes.FaceReady) },
                onRetake = { nav.go(Routes.IdFront) },
                fields = idFields(cccd),
            )
        }

        // Stage B: face
        composable(Routes.FaceReady) {
            FaceReadyScreen(onBack = { nav.popBackStack() }, onReady = ::startFace, onSkipFlash = { nav.go(Routes.Voice) })
        }
        composable(Routes.Framing) {
            val face by camera.face.collectAsState()
            LaunchedEffect(Unit) {
                if (!hasCamera || !hasMic) askPermissions.launch(arrayOf(Manifest.permission.CAMERA, Manifest.permission.RECORD_AUDIO))
            }
            LaunchedEffect(hasCamera) {
                if (hasCamera && !camera.start(lifecycleOwner, back = false)) nav.go(Routes.ErrorDevice)
            }
            LaunchedEffect(flow.live) {
                if (flow.live) live.ensureSession(flow.mockScenario)?.let { nav.go(errorRoute(it)) }
            }
            val gate = if (hasCamera) QualityGate.evaluate(face) else null
            // Good for a moment → take the frontal still (on the grey screen, before the flash: ADR-0016).
            LaunchedEffect(gate == FramingState.Good) {
                if (gate != FramingState.Good) return@LaunchedEffect
                delay(QualityGate.GOOD_HOLD_MS)
                live.frontalJpeg = withTimeoutOrNull(3000) { camera.captureJpeg() }
                nav.go(Routes.HoldStill)
            }
            FramingScreen(
                onExit = exit,
                onCaptured = { nav.go(Routes.HoldStill) },
                live = gate,
                onDebugCapture = if (BuildConfig.DEBUG && hasCamera) {
                    {
                        scope.launch {
                            live.frontalJpeg = withTimeoutOrNull(3000) { camera.captureJpeg() }
                            nav.go(Routes.HoldStill)
                        }
                    }
                } else {
                    null
                },
            )
        }
        composable(Routes.HoldStill) {
            val challenge = live.challenge
            val slots = remember(challenge) {
                if (flow.live && challenge != null) ColorSchedule.from(challenge) else ColorSchedule.demo()
            }
            LaunchedEffect(slots) { if (flow.live && (challenge == null || !ColorSchedule.isSafe(slots))) nav.go(Routes.ErrorService) }
            HoldStillScreen(
                onStop = exit,
                onDone = { nav.go(Routes.TurnHead) },
                slots = slots,
                onColorsStart = {
                    live.colorEvents.clear()
                    if (hasCamera) camera.startRecording()
                },
                onPainted = { slot, t -> slot.index?.let { live.colorEvents += ColorEvent(it, slot.rgb, t) } },
                onBaselineDone = { camera.lockAeAwb(true) },
                onColorsDone = {
                    camera.stopRecording()
                    camera.lockAeAwb(false)
                },
            )
        }
        composable(Routes.TurnHead) {
            val face by camera.face.collectAsState()
            TurnHeadScreen(
                flow.turnOrder,
                onExit = exit,
                onDone = { nav.go(if (flow.live) Routes.Uploading else FlowRules.afterTurnHead(flow.purpose)) },
                yaw = if (hasCamera) face?.yaw else null,
                onDebugSkip = if (BuildConfig.DEBUG && hasCamera) {
                    { nav.go(if (flow.live) Routes.Uploading else FlowRules.afterTurnHead(flow.purpose)) }
                } else {
                    null
                },
            )
        }

        // Stage C: voice
        composable(Routes.Voice) { VoiceRoute(again = false) }
        composable(Routes.VoiceAgain) { VoiceRoute(again = true) }

        // Stage D: checking and results
        composable(Routes.Uploading) {
            if (flow.live) {
                LaunchedEffect(Unit) {
                    val wav = live.pendingWav
                    follow(
                        if (wav != null) {
                            live.pendingWav = null
                            live.submitVoice(wav)
                        } else {
                            val probe = withContext(Dispatchers.IO) { camera.camProbe() }
                            live.submitFace(
                                camera.recordedVideo(),
                                camera.frameTimes(),
                                camera.clientQuality(),
                                probe,
                                camera.regionMeans().ifEmpty { null },
                            )
                        },
                    )
                }
            }
            Messages.Uploading(onStop = exit, onDone = { nav.go(Routes.Checking) }, auto = !flow.live)
        }
        composable(Routes.Checking) {
            CheckingScreen(flow.purpose, onDone = {
                nav.navigate(FlowRules.afterChecking(flow.outcome)) { popUpTo(Routes.Checking) { inclusive = true } }
            })
        }
        composable(Routes.Success) {
            SuccessScreen(flow.purpose, onContinue = {
                if (flow.purpose == Purpose.Onboarding) nav.go(Routes.BankOpened) else leave()
            })
        }
        composable(Routes.Review) { ReviewScreen(onBackToBank = { leave() }) }
        composable(Routes.RetryQuality) {
            RetryQualityScreen(
                onBack = exit,
                onRetake = { flow.outcome = DemoOutcome.Pass; startFace() },
                hint = if (flow.live) FlowRules.retryHintText(live.retryHint) else null,
                attemptsLeft = if (flow.live) live.attemptsLeft else 1,
                hintCode = if (flow.live) live.retryHint else null,
            )
        }
        composable(Routes.RetryChallenge) {
            RetryChallengeScreen(
                onBack = exit,
                onRetry = { flow.outcome = DemoOutcome.Pass; startFace() },
                attemptsLeft = if (flow.live) live.attemptsLeft else 1,
            )
        }

        // Errors and interruptions
        composable(Routes.ErrorCamera) { Messages.CameraDenied(onRetry = { nav.go(Routes.FaceReady) }, onBack = { nav.popBackStack() }) }
        composable(Routes.ErrorMic) { Messages.MicDenied(onRetry = { nav.go(Routes.Voice) }, onBack = { nav.popBackStack() }) }
        composable(Routes.ErrorNetwork) { Messages.Network(onRetry = { nav.go(Routes.Checking) }, onBack = { nav.popBackStack() }) }
        composable(Routes.ErrorSession) { Messages.SessionExpired(onBank = { leave() }) }
        composable(Routes.ErrorService) { Messages.ServiceDown(onBank = { leave() }) }
        composable(Routes.ErrorDevice) {
            Messages.DeviceNotReady(onCheck = { nav.go(Routes.Permission) }, onBank = { leave() }, onBack = exit)
        }
        composable(Routes.Interrupted) { Messages.Interrupted(onRedo = { nav.go(Routes.FaceReady) }, onStop = { nav.go(Routes.Stopped) }) }
        composable(Routes.NoVoice) { Messages.NoVoice(onRetry = { nav.go(Routes.Voice) }, onStop = exit) }
        composable(Routes.UploadFailed) { Messages.UploadFailed(onResend = { nav.go(Routes.Uploading) }, onStop = exit) }
        composable(Routes.Slow) { Messages.Slow(onWait = { nav.go(Routes.Checking) }, onStop = exit) }
        composable(Routes.ExitConfirm) {
            Messages.ExitConfirm(
                onResume = {
                    camera.stopRecording()
                    recorder.stop()
                    live.dropFaceAttempt()
                    nav.go(Routes.FaceReady)
                },
                onStop = { nav.go(Routes.Stopped) },
            )
        }
        composable(Routes.Stopped) { Messages.Stopped(onBank = { leave() }) }
    }
    }
}

/** Debug-only index of every screen, like the "Flows" list in Figma Present. */
@OptIn(ExperimentalLayoutApi::class)
@Composable
private fun GalleryScreen(nav: NavHostController, flow: FlowState) {
    val c = Vc.colors
    val groups = listOf(
        "Bắt đầu" to listOf("Màn chào" to Routes.Splash, "Đăng nhập / Đăng ký" to Routes.Auth, "Điều khoản" to Routes.Terms, "Đồng ý từng mục" to Routes.Consent),
        "Danh tính" to listOf(
            "Giới thiệu" to Routes.Intro, "Quyền camera, micro" to Routes.Permission, "Số điện thoại" to Routes.Phone,
            "OTP" to Routes.Otp, "OTP nhập sai" to Routes.OtpError, "CCCD mặt trước" to Routes.IdFront,
            "CCCD bị lóa" to Routes.IdFrontGlare, "Xem lại ảnh mặt trước" to Routes.IdFrontReview,
            "CCCD mặt sau" to Routes.IdBack, "Xem lại ảnh mặt sau" to Routes.IdBackReview, "Kiểm tra thông tin" to Routes.Confirm,
            "Sửa thông tin" to Routes.EditInfo,
        ),
        "Khuôn mặt" to listOf("Chuẩn bị" to Routes.FaceReady, "Căn mặt" to Routes.Framing, "Giữ yên + nháy màu + chấm sáng" to Routes.HoldStill, "Quay đầu" to Routes.TurnHead),
        "Giọng nói" to listOf("Đọc câu" to Routes.Voice, "Đọc lại câu mới" to Routes.VoiceAgain),
        "Kết quả" to listOf(
            "Đang gửi" to Routes.Uploading, "Đang kiểm tra" to Routes.Checking, "Thành công" to Routes.Success,
            "Chờ duyệt" to Routes.Review, "Chụp lại" to Routes.RetryQuality, "Làm lại thử thách" to Routes.RetryChallenge,
        ),
        "Lỗi và gián đoạn" to listOf(
            "Chưa cho camera" to Routes.ErrorCamera, "Chưa cho micro" to Routes.ErrorMic, "Mất mạng" to Routes.ErrorNetwork,
            "Hết phiên" to Routes.ErrorSession, "Dịch vụ không đáp ứng" to Routes.ErrorService, "Thiết bị chưa đáp ứng" to Routes.ErrorDevice,
            "Bị gián đoạn" to Routes.Interrupted, "Không thu được giọng" to Routes.NoVoice, "Gửi thất bại" to Routes.UploadFailed,
            "Kiểm tra lâu" to Routes.Slow, "Xác nhận dừng" to Routes.ExitConfirm, "Đã dừng" to Routes.Stopped,
        ),
        "App ngân hàng (mô phỏng)" to listOf("Mở tài khoản thành công" to Routes.BankOpened),
    )
    VcScreen(onBack = { nav.popBackStack() }) {
        Text("Tất cả màn (bản demo giao diện)", style = VcType.titleMedium, color = c.ink)
        Text("Luồng", style = VcType.label, color = c.muted)
        FlowRow(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            Purpose.entries.forEach { p ->
                FilterChip(selected = flow.purpose == p, onClick = { flow.purpose = p }, label = {
                    Text(when (p) { Purpose.Onboarding -> "Đăng ký"; Purpose.Reauth -> "Đăng nhập lại"; Purpose.Recovery -> "Khôi phục" })
                })
            }
        }
        Text("Nguồn kết quả", style = VcType.label, color = c.muted)
        FlowRow(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            FilterChip(selected = !flow.live, onClick = { flow.live = false }, label = { Text("Giả lập trên máy") })
            FilterChip(selected = flow.live, onClick = { flow.live = true }, label = { Text("API thật") })
        }
        if (flow.live) {
            Text("API: ${BuildConfig.API_BASE_URL} · kịch bản mock (USE_MOCK_MODELS=true)", style = VcType.caption, color = c.muted)
            FlowRow(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                listOf("genuine", "low_quality", "print", "replay", "virtual_cam", "faceswap", "voice_clone", "error").forEach { sc ->
                    FilterChip(selected = flow.mockScenario == sc, onClick = { flow.mockScenario = sc }, label = { Text(sc) })
                }
            }
        }
        Text("Kết quả mô phỏng sau bước kiểm tra (chỉ khi giả lập)", style = VcType.label, color = c.muted)
        FlowRow(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            DemoOutcome.entries.forEach { o ->
                FilterChip(selected = flow.outcome == o, onClick = { flow.outcome = o }, label = { Text(o.label) })
            }
        }
        groups.forEach { (title, items) ->
            Text(title, style = VcType.section, color = c.ink)
            Column(Modifier.fillMaxWidth(), verticalArrangement = Arrangement.spacedBy(6.dp)) {
                items.forEach { (label, route) ->
                    Text(
                        label,
                        style = VcType.bodySmall,
                        color = c.accent,
                        modifier = Modifier.fillMaxWidth().clip(RoundedCornerShape(10.dp)).background(c.surfaceSubtle)
                            .clickable { nav.go(route) }.padding(horizontal = 14.dp, vertical = 12.dp),
                    )
                }
            }
        }
    }
}
