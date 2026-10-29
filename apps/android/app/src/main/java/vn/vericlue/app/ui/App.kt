package vn.vericlue.app.ui

import androidx.compose.animation.fadeIn
import androidx.compose.animation.fadeOut
import androidx.compose.animation.EnterTransition
import androidx.compose.animation.ExitTransition
import androidx.compose.animation.slideInHorizontally
import androidx.compose.animation.slideOutHorizontally
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
import android.util.Log
import android.widget.Toast
import androidx.activity.compose.BackHandler
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
import vn.vericlue.app.capture.IdAutoCapture
import vn.vericlue.app.capture.IdQuality
import vn.vericlue.app.ui.screens.idFields
import vn.vericlue.app.capture.CaptureClock
import vn.vericlue.app.capture.ColorSchedule
import vn.vericlue.app.capture.QualityGate
import vn.vericlue.app.capture.WavRecorder
import vn.vericlue.app.data.AccountStore
import vn.vericlue.app.data.PrefsStore
import vn.vericlue.app.flow.AccountEntry
import vn.vericlue.app.flow.AccountFlow
import vn.vericlue.app.security.AndroidAccountKeys
import vn.vericlue.app.data.api.ColorEvent
import vn.vericlue.app.capture.FaceTimeline
import vn.vericlue.app.data.api.SessionApi
import vn.vericlue.app.flow.FramingState
import vn.vericlue.app.flow.OtpRules
import vn.vericlue.app.flow.LiveFlow
import vn.vericlue.app.flow.submitWithVideo
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
import vn.vericlue.app.ui.screens.FaceTimelineScreen
import vn.vericlue.app.ui.screens.ConfirmInfoScreen
import vn.vericlue.app.ui.screens.EditInfoScreen
import vn.vericlue.app.ui.screens.FaceReadyScreen
import vn.vericlue.app.ui.screens.FramingScreen
import vn.vericlue.app.ui.screens.HoldStillScreen
import vn.vericlue.app.ui.screens.IdCaptureScreen
import vn.vericlue.app.ui.screens.IdReviewScreen
import vn.vericlue.app.ui.screens.IdScanScreen
import vn.vericlue.app.ui.screens.IdProcessingScreen
import vn.vericlue.app.capture.idScanHint
import vn.vericlue.app.capture.idScanErrorText
import vn.vericlue.app.ui.screens.Messages
import vn.vericlue.app.ui.screens.OtpScreen
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

    /**
     * Real API or offline demo. Release builds always use the API; debug builds start in demo
     * mode and switch in "Xem tất cả màn".
     */
    var live by mutableStateOf(!BuildConfig.DEBUG)

    /** Mock scenario sent as X-Mock-Scenario when the API runs with USE_MOCK_MODELS=true. */
    var mockScenario by mutableStateOf("genuine")

    /** Each attempt at the face part gets a fresh challenge (ADR-0017 §2). */
    fun newChallenge() {
        turnOrder = newTurnOrder()
    }

    private fun newTurnOrder() = listOf(TurnDir.Left, TurnDir.Right).shuffled()
}

/** Made-up card data in the CCCD QR layout (same as IdCardTest); debug builds only, for the emulator. */
private const val DEBUG_SAMPLE_QR = "001095012345|123456789|Nguyễn Văn A|01011995|Nam|Số 1 Đại Cồ Việt, Hai Bà Trưng, Hà Nội|15072021"

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
    val api = remember { SessionApi(BuildConfig.API_BASE_URL) }
    var live by remember { mutableStateOf(LiveFlow(api)) }
    val accounts = remember {
        AccountStore(PrefsStore(context.applicationContext.getSharedPreferences("vericlue.account", Context.MODE_PRIVATE)))
    }
    val accountFlow = remember {
        AccountFlow(accounts, AndroidAccountKeys(), BuildConfig.SIGNED_MEDIA,
            warn = { Log.w("VeriClue", it) })
    }
    var accountEntry by remember { mutableStateOf<AccountEntry?>(null) }
    val recorder = remember { WavRecorder() }
    var hasCamera by remember { mutableStateOf(granted(context, Manifest.permission.CAMERA)) }
    var hasMic by remember { mutableStateOf(granted(context, Manifest.permission.RECORD_AUDIO)) }
    // Asked when first needed (short flow): the camera when it opens, the mic at the reading step.
    val askPermissions = rememberLauncherForActivityResult(ActivityResultContracts.RequestMultiplePermissions()) { result ->
        result[Manifest.permission.CAMERA]?.let { hasCamera = it; if (!it) nav.go(Routes.ErrorCamera) }
        result[Manifest.permission.RECORD_AUDIO]?.let { hasMic = it; if (!it) nav.go(Routes.ErrorMic) }
    }
    val exit = { nav.go(Routes.ExitConfirm) }

    // ID card photos and QR text; in live mode they go to the server at the back-side review (FLOW-03).
    var idFront by remember { mutableStateOf<Pair<ByteArray, IdQuality>?>(null) }
    var idBack by remember { mutableStateOf<Pair<ByteArray, IdQuality>?>(null) }
    var cccd by remember { mutableStateOf<CccdInfo?>(null) }
    val voiceStart = remember { mutableStateOf<kotlinx.coroutines.Job?>(null) }
    var phone by remember { mutableStateOf("") }
    var otpError by remember { mutableStateOf<String?>(null) }
    var busy by remember { mutableStateOf(false) }

    // Short flow: the confirm screen comes after the face recording. Nothing of the face part is sent
    // before the confirm: the server refuses a confirm or a new card once it has media (FLOW-05 runbook).
    var faceCaptured by remember { mutableStateOf(false) }
    // Why the server asked for the card again; shown on the camera until the next shot.
    var idHint by remember { mutableStateOf<String?>(null) }
    // Why the server refused the confirmed fields; shown on the edit screen.
    var editHint by remember { mutableStateOf<String?>(null) }

    /** A refused confirm: missing fields go back to the edit screen, anything else to an error screen. */
    fun confirmFailed(e: vn.vericlue.app.data.api.ApiResult.Err) {
        FlowRules.confirmErrorText(e.code)?.let {
            editHint = it
            nav.go(Routes.EditInfo)
        } ?: nav.go(errorRoute(e.error))
    }
    var idConfirmed by remember { mutableStateOf(false) }

    /** Runs one server call at a time from a button; a second tap while it runs is ignored. */
    fun once(block: suspend () -> Unit) {
        if (busy) return
        busy = true
        scope.launch {
            try {
                block()
            } finally {
                busy = false
            }
        }
    }

    /** Every auth choice starts a fresh session, including when returning from OTP with Back. */
    fun enterAccount(requested: Purpose) = once {
        camera.unbind()
        camera.deleteVideo()
        recorder.stop()
        live.reset()
        idFront = null
        idBack = null
        cccd = null
        faceCaptured = false
        idConfirmed = false
        phone = ""
        otpError = null
        accountEntry = null
        val entry = if (flow.live) withContext(Dispatchers.IO) {
            runCatching { accountFlow.begin(requested) }.getOrNull()
        } else null
        if (flow.live && entry == null) {
            nav.go(Routes.ErrorService)
            return@once
        }
        flow.purpose = entry?.purpose ?: requested
        live = LiveFlow(api, mediaSigner = entry?.signer).apply { boundAccount = entry?.account }
        accountEntry = entry
        entry?.hint?.let { Toast.makeText(context, it, Toast.LENGTH_LONG).show() }
        nav.go(entry?.route ?: if (requested == Purpose.Onboarding) Routes.Terms else Routes.Phone)
    }

    /** Back to the one review screen, replacing an older copy of it in the back stack. */
    fun toIdReview() = nav.navigate(Routes.IdReview) {
        popUpTo(Routes.IdReview) { inclusive = true }
        launchSingleTop = true
    }

    /**
     * One side of the card: the app takes the photo when it is sharp and glare-free (the shutter
     * stays), keeps it on screen for one beat with "Chụp lại", then calls [onDone].
     */
    @Composable
    fun IdCaptureRoute(back: Boolean, onDone: () -> Unit) {
        val observation by camera.idQuality.collectAsState()
        var captured by remember { mutableStateOf(false) }
        var taking by remember { mutableStateOf(false) }
        var timedOut by remember { mutableStateOf(false) }
        var attempts by remember { mutableStateOf(0) }
        var captureJob by remember { mutableStateOf<kotlinx.coroutines.Job?>(null) }
        DisposableEffect(Unit) {
            onDispose { captureJob?.cancel() }
        }
        LaunchedEffect(Unit) {
            camera.clearQr()
            idHint = null
            if (!hasCamera) askPermissions.launch(arrayOf(Manifest.permission.CAMERA))
        }
        LaunchedEffect(hasCamera) {
            if (hasCamera && !camera.start(lifecycleOwner, back = true)) nav.go(Routes.ErrorDevice)
        }
        fun capture(manual: Boolean) {
            if (taking || captured) return
            taking = true
            attempts++
            captureJob = scope.launch {
                try {
                    val shot = withTimeoutOrNull(8000) { camera.captureId() }
                    if (shot == null) { timedOut = true; return@launch }
                    val q = shot.second
                    if (!q.good || q.brightness < 45 || (!manual && !back && !q.portraitPresent)) {
                        idHint = idScanHint(q, back)
                        if (attempts >= 3) timedOut = true
                        return@launch
                    }
                    if (back) idBack = shot else { idFront = shot; idBack = null }
                    cccd = CccdQr.parse(FlowRules.cardQr(idFront?.second?.qr, idBack?.second?.qr))
                    idConfirmed = false
                    faceCaptured = false
                    captured = true
                    delay(450)
                    if (back || CccdQr.parse(q.qr) != null) camera.unbind()
                    onDone()
                } catch (cancelled: kotlinx.coroutines.CancellationException) {
                    throw cancelled
                } catch (_: Exception) {
                    timedOut = true
                } finally { taking = false }
            }
        }
        LaunchedEffect(Unit) { delay(20_000); timedOut = true }
        LaunchedEffect(hasCamera, captured) {
            if (!hasCamera || captured) return@LaunchedEffect
            val auto = IdAutoCapture(back = back)
            delay(IdAutoCapture.START_DELAY_MS)
            while (!captured) {
                val q = camera.idQuality.value
                if (!timedOut && !taking && q != null && auto.offer(q)) capture(manual = false)
                delay(250)
            }
        }
        IdScanScreen(back, observation,
            onBack = { camera.clearQr(); nav.popBackStack() }, onStop = exit,
            onManual = { capture(manual = true) }, timedOut = timedOut,
            taking = taking || captured, hint = idHint)
    }

    fun startFace() {
        flow.newChallenge()
        live.frontalJpeg = null
        nav.go(Routes.Framing)
    }

    /** Leaves the flow: camera off, session data dropped. */
    fun leave() {
        camera.unbind()
        camera.deleteVideo()
        recorder.stop()
        live.reset()
        accountEntry = null
        idFront = null
        idBack = null
        cccd = null
        faceCaptured = false
        idConfirmed = false
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
        LaunchedEffect(Unit) {
            if (!hasMic) askPermissions.launch(arrayOf(Manifest.permission.RECORD_AUDIO))
        }
        VoiceScreen(
            onBack = exit,
            again = again,
            sentence = if (flow.live) live.voicePrompt else null,
            level = level,
            onStartRecording = {
                if (hasMic) {
                    // Video and WAV start together so the server can line up lips and voice (VOICE-05):
                    // the WAV waits for the camera, which is the slower one to start.
                    voiceStart.value = scope.launch {
                        live.audioOffsetMs = null
                        if (flow.live && hasCamera) {
                            camera.startRecording(voice = true)
                            camera.awaitRecordingStarted()
                        }
                        live.audioOffsetMs = camera.videoElapsedMs()
                        recorder.start(scope)
                    }
                }
            },
            onFinished = {
                voiceStart.value?.cancel() // finished before the mic even started: nothing recorded
                val wav = recorder.stop()
                camera.stopRecording()
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
                camera.deleteVideo()
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
    val motion = Vc.motion

    CompositionLocalProvider(LocalCameraFeed provides cameraFeed) {
    NavHost(
        navController = nav,
        startDestination = Routes.BankStart,
        enterTransition = {
            if (motion.screenTransition(initialState.destination.route, targetState.destination.route))
                fadeIn(motion.tween(250)) + slideInHorizontally(motion.tween(250)) { it / 16 }
            else EnterTransition.None
        },
        exitTransition = {
            if (motion.screenTransition(initialState.destination.route, targetState.destination.route))
                fadeOut(motion.tween(250)) + slideOutHorizontally(motion.tween(250)) { -it / 24 }
            else ExitTransition.None
        },
        popEnterTransition = {
            if (motion.screenTransition(initialState.destination.route, targetState.destination.route))
                fadeIn(motion.tween(250)) + slideInHorizontally(motion.tween(250)) { -it / 16 }
            else EnterTransition.None
        },
        popExitTransition = {
            if (motion.screenTransition(initialState.destination.route, targetState.destination.route))
                fadeOut(motion.tween(250)) + slideOutHorizontally(motion.tween(250)) { it / 24 }
            else ExitTransition.None
        },
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
                onRegister = { enterAccount(Purpose.Onboarding) },
                onLogin = { enterAccount(Purpose.Reauth) },
                onRecover = { enterAccount(Purpose.Recovery) },
            )
        }
        // Terms and consent on one screen; no intro or permission screen (short flow, 24/10).
        composable(Routes.Terms) { TermsScreen(onBack = { nav.popBackStack() }, onAccept = { nav.go(Routes.Phone) }) }

        // Stage A: identity
        composable(Routes.Phone) {
            PhoneScreen(onBack = { nav.popBackStack() }, onSend = { number ->
                phone = number
                otpError = null
                if (!flow.live) {
                    nav.go(Routes.Otp)
                } else {
                    // The session starts here: OTP and ID card belong to it (can-chot.md Q4).
                    once { live.sendOtp(number, flow.mockScenario, FlowRules.purposeCode(flow.purpose))?.let { nav.go(errorRoute(it)) } ?: nav.go(Routes.Otp) }
                }
            })
        }
        composable(Routes.Otp) {
            if (!flow.live) {
                OtpScreen(onBack = { nav.popBackStack() }, onVerified = { nav.go(FlowRules.afterOtp(flow.purpose)) })
            } else {
                // The code fills itself from the simulated SMS, or from a real one the user lets the app read.
                var smsCode by remember { mutableStateOf(OtpRules.codeIn(live.otpSms)) }
                SmsCodeListener(enabled = true) { smsCode = it }
                OtpScreen(
                    onBack = { nav.popBackStack() },
                    onVerified = {},
                    autoCode = smsCode,
                    sms = live.otpSms,
                    serverError = otpError,
                    onCode = { code ->
                        once {
                            when (val r = live.verifyOtp(code)) {
                                LiveFlow.OtpResult.Pass -> nav.go(FlowRules.afterOtp(flow.purpose))
                                is LiveFlow.OtpResult.Wrong -> otpError = FlowRules.otpWrongText(r.attemptsLeft)
                                is LiveFlow.OtpResult.Fail -> FlowRules.otpErrorText(r.code)?.let { otpError = it } ?: nav.go(errorRoute(r.error))
                            }
                        }
                    },
                    onResend = {
                        otpError = null
                        once {
                            live.sendOtp(phone, flow.mockScenario, FlowRules.purposeCode(flow.purpose))?.let { nav.go(errorRoute(it)) }
                                ?: run { smsCode = OtpRules.codeIn(live.otpSms) }
                        }
                    },
                )
            }
        }
        composable(Routes.OtpError) {
            OtpScreen(onBack = { nav.popBackStack() }, onVerified = { nav.go(FlowRules.afterOtp(flow.purpose)) }, startWithError = true)
        }
        // A retake from the review screen goes back to it; the first pass goes front → back → review.
        composable(Routes.IdFront) { IdCaptureRoute(back = false) { if (CccdQr.parse(idFront?.second?.qr) != null) toIdReview() else nav.go(Routes.IdBack) } }
        composable(Routes.IdFrontGlare) { IdCaptureScreen(back = false, glare = true, onBack = { nav.popBackStack() }, onCapture = { nav.go(Routes.IdFront) }) }
        composable(Routes.IdBack) { IdCaptureRoute(back = true) { toIdReview() } }
        composable(Routes.IdReview) {
            var failure by remember { mutableStateOf<String?>(null) }
            LaunchedEffect(Unit) {
                if (!flow.live) {
                    delay(500)
                    nav.go(Routes.Confirm)
                    return@LaunchedEffect
                }
                val front = idFront?.first
                if (front == null) { nav.go(Routes.IdFront); return@LaunchedEffect }
                val qr = FlowRules.cardQr(idFront?.second?.qr, idBack?.second?.qr)
                val (hint, error) = live.sendIdCard(front, idBack?.first, qr)
                when {
                    error != null -> nav.go(errorRoute(error))
                    hint != null -> failure = idScanErrorText(hint)
                    else -> {
                        live.idFields?.let { cccd = FlowRules.cccdFrom(it) }
                        idConfirmed = false
                        nav.go(Routes.Confirm)
                    }
                }
            }
            IdProcessingScreen(onStop = exit, onRetake = {
                idFront = null; idBack = null; cccd = null
                idConfirmed = false; faceCaptured = false
                nav.navigate(Routes.IdFront) { popUpTo(Routes.IdFront) { inclusive = true } }
            }, error = failure)
        }
        composable(Routes.Confirm) {
            // After the face part, going back would restart the recording: ask whether to stop instead.
            BackHandler(enabled = faceCaptured, onBack = exit)
            ConfirmInfoScreen(
                onBack = { if (faceCaptured) exit() else nav.popBackStack() },
                onCorrect = {
                    val fields = live.idFields
                    if (!flow.live) {
                        idConfirmed = true
                        nav.go(FlowRules.afterConfirm(flow.purpose, flow.live, faceCaptured))
                    } else if (fields == null) {
                        nav.go(Routes.IdFront)
                    } else {
                        once {
                            live.confirmIdCard(fields)?.let(::confirmFailed) ?: run {
                                idConfirmed = true
                                nav.go(FlowRules.afterConfirm(flow.purpose, flow.live, faceCaptured))
                            }
                        }
                    }
                },
                onEdit = { nav.go(Routes.EditInfo) },
                fields = idFields(cccd),
                afterFace = faceCaptured,
            )
        }
        composable(Routes.EditInfo) {
            EditInfoScreen(
                onBack = { nav.popBackStack() },
                onSave = { edited ->
                    val fields = live.idFields
                    if (!flow.live) {
                        idConfirmed = true
                        nav.go(FlowRules.afterConfirm(flow.purpose, flow.live, faceCaptured))
                    } else if (fields == null) {
                        nav.go(Routes.IdFront)
                    } else {
                        // Fields left as shown keep the QR value; edited ones are noted for the reviewer.
                        val confirmed = FlowRules.confirmedFields(fields, idFields(cccd).map { it.second }, edited)
                        once {
                            live.confirmIdCard(confirmed)?.let(::confirmFailed) ?: run {
                                idConfirmed = true
                                nav.go(FlowRules.afterConfirm(flow.purpose, flow.live, faceCaptured))
                            }
                        }
                    }
                },
                onRetake = {
                    idFront = null
                    idBack = null
                    nav.go(Routes.IdFront)
                },
                hint = editHint,
                fields = idFields(cccd),
            )
        }

        // Stage B: face
        composable(Routes.FaceReady) {
            // Skipping the flash must not skip the face part: stop here. Nothing reaches the server yet,
            // so the screen promises no review (question 14 in docs/can-chot.md).
            FaceReadyScreen(onBack = { nav.popBackStack() }, onReady = ::startFace, onSkipFlash = {
                camera.unbind()
                nav.go(Routes.FlashSkipped)
            })
        }
        composable(Routes.Framing) {
            val face by camera.face.collectAsState()
            LaunchedEffect(Unit) {
                if (!hasCamera) askPermissions.launch(arrayOf(Manifest.permission.CAMERA))
            }
            LaunchedEffect(hasCamera) {
                if (hasCamera && !camera.start(lifecycleOwner, back = false)) nav.go(Routes.ErrorDevice)
            }
            // Live: a fresh challenge for this attempt (new session, or refresh after stage A / retry / redo).
            var prepared by remember { mutableStateOf(!flow.live) }
            LaunchedEffect(flow.live) {
                if (flow.live) {
                    live.prepareFace(flow.mockScenario, FlowRules.purposeCode(flow.purpose))?.let { nav.go(errorRoute(it)) } ?: run { prepared = true }
                }
            }
            val gate = if (hasCamera) QualityGate.evaluate(face) else null
            // Good for a moment → take the frontal still (on the grey screen, before the flash: ADR-0016).
            LaunchedEffect(gate == FramingState.Good && prepared) {
                if (gate != FramingState.Good || !prepared) return@LaunchedEffect
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
            // One presentation in both modes. Only API mode consumes a server challenge;
            // a missing/invalid server schedule must never fall back to the offline demo.
            val timeline = remember(challenge, flow.live, flow.purpose, flow.turnOrder) {
                if (!flow.live) {
                    if (flow.purpose == Purpose.Reauth) FaceTimeline.passive() else FaceTimeline.demo(flow.turnOrder)
                } else {
                    challenge?.let { FaceTimeline.from(it) }
                        ?: if (flow.purpose == Purpose.Reauth) FaceTimeline.passive() else null
                }
            }
            var demoStart by remember { mutableStateOf<Double?>(null) }
            LaunchedEffect(timeline) {
                if (timeline == null || !ColorSchedule.isSafe(timeline.slots)) nav.go(Routes.ErrorService)
            }
            if (timeline != null) {
                FaceTimelineScreen(
                    timeline,
                    onStop = exit,
                    onStart = {
                        live.colorEvents.clear()
                        if (hasCamera) camera.startRecording() else if (!flow.live) demoStart = CaptureClock.nowMs()
                    },
                    recordingStartMs = { if (hasCamera || flow.live) camera.recordingStartMs() else demoStart },
                    onPainted = { slot, t -> slot.index?.let { live.colorEvents += ColorEvent(it, slot.rgb, t) } },
                    onFrontal = { if (hasCamera) scope.launch { withTimeoutOrNull(1500) { camera.captureJpeg() }?.let { live.frontalJpeg = it } } },
                    onBaselineDone = { camera.lockAeAwb(true) },
                    onColorsDone = { camera.lockAeAwb(false) },
                    onDone = {
                        camera.stopRecording()
                        faceCaptured = true
                        val next = FlowRules.afterFace(flow.purpose, idConfirmed, live = flow.live)
                        nav.navigate(next) { if (next == Routes.Confirm) popUpTo(Routes.FaceReady) { inclusive = true } }
                    },
                    onNoRecording = { nav.go(Routes.ErrorDevice) },
                )
            }
        }
        composable(Routes.TurnHead) {
            val face by camera.face.collectAsState()
            // Gallery preview only: both full flows run the turns inside FaceTimelineScreen.
            TurnHeadScreen(
                flow.turnOrder,
                onExit = exit,
                onDone = { faceCaptured = true; nav.go(FlowRules.afterFace(flow.purpose, idConfirmed, flow.live)) },
                yaw = if (hasCamera) face?.yaw else null,
                onDebugSkip = if (BuildConfig.DEBUG && hasCamera) {
                    { faceCaptured = true; nav.go(FlowRules.afterFace(flow.purpose, idConfirmed, flow.live)) }
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
                    // A retry comes back here; LiveFlow resends only what the server has not received.
                    val next = submitWithVideo(camera.finishedVideo()) { video ->
                        if (wav != null) {
                            live.submitVoice(wav, video, live.audioOffsetMs, onAccepted = camera::deleteVideo)
                        } else {
                            val probe = withContext(Dispatchers.IO) { camera.camProbe() }
                            live.submitFace(
                                video,
                                camera.frameTimes(),
                                camera.clientQuality(video),
                                probe,
                                camera.regionMeans().ifEmpty { null },
                                onMediaAcked = camera::deleteVideo,
                            )
                        }
                    }
                    // Finish account persistence while Uploading still owns the coroutine.
                    // Success automatically advances; its destination must not own this work.
                    follow(accountEntry?.let { accountFlow.finish(it, live, next) } ?: next)
                }
            }
            Messages.Uploading(onStop = exit, onDone = { nav.go(Routes.Checking) }, auto = !flow.live)
        }
        composable(Routes.Checking) {
            // Demo only: the result comes from DemoOutcome. A live run never decides here.
            if (flow.live) LaunchedEffect(Unit) { nav.navigate(Routes.Uploading) { popUpTo(Routes.Checking) { inclusive = true } } }
            CheckingScreen(flow.purpose, auto = !flow.live, onDone = {
                nav.navigate(FlowRules.afterChecking(flow.outcome)) { popUpTo(Routes.Checking) { inclusive = true } }
            })
        }
        composable(Routes.Success) {
            SuccessScreen(
                flow.purpose,
                onContinue = { if (flow.purpose == Purpose.Onboarding) nav.go(Routes.BankOpened) else leave() },
                checked = if (flow.live) FlowRules.checkedByServer(live.voiceChecked) else null,
            )
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
        composable(Routes.ErrorNetwork) {
            Messages.Network(onRetry = {
                nav.navigate(FlowRules.afterNetworkRetry(flow.live)) { popUpTo(Routes.ErrorNetwork) { inclusive = true } }
            }, onBack = { nav.popBackStack() })
        }
        composable(Routes.ErrorSession) { Messages.SessionExpired(onBank = { leave() }) }
        composable(Routes.ErrorService) { Messages.ServiceDown(onBank = { leave() }) }
        composable(Routes.ErrorDevice) {
            Messages.DeviceNotReady(onCheck = {
                askPermissions.launch(arrayOf(Manifest.permission.CAMERA))
                nav.popBackStack()
            }, onBank = { leave() }, onBack = exit)
        }
        composable(Routes.FaceExpired) {
            Messages.FaceExpired(onRedo = {
                camera.deleteVideo()
                live.dropFaceAttempt()
                nav.go(Routes.FaceReady)
            }, onStop = { nav.go(Routes.Stopped) })
        }
        composable(Routes.Interrupted) { Messages.Interrupted(onRedo = { nav.go(Routes.FaceReady) }, onStop = { nav.go(Routes.Stopped) }) }
        composable(Routes.NoVoice) { Messages.NoVoice(onRetry = { nav.go(Routes.Voice) }, onStop = exit) }
        composable(Routes.UploadFailed) { Messages.UploadFailed(onResend = { nav.go(Routes.Uploading) }, onStop = exit) }
        composable(Routes.Slow) {
            Messages.Slow(onWait = {
                nav.navigate(FlowRules.afterNetworkRetry(flow.live)) { popUpTo(Routes.Slow) { inclusive = true } }
            }, onStop = exit)
        }
        composable(Routes.ExitConfirm) {
            val redoesFace = remember { FlowRules.resumeRedoesFace(nav.previousBackStackEntry?.destination?.route) }
            Messages.ExitConfirm(
                redoesFace = redoesFace,
                onResume = {
                    if (redoesFace) {
                        camera.stopRecording()
                        camera.deleteVideo()
                        recorder.stop()
                        live.dropFaceAttempt()
                        nav.go(Routes.FaceReady)
                    } else {
                        nav.popBackStack()
                    }
                },
                onStop = {
                    // Stop capturing now, not when the user leaves the "stopped" screen.
                    camera.stopRecording()
                    camera.deleteVideo()
                    recorder.stop()
                    nav.go(Routes.Stopped)
                },
            )
        }
        composable(Routes.Stopped) { Messages.Stopped(onBank = { leave() }) }
        composable(Routes.FlashSkipped) { Messages.FlashSkipped(onBank = { leave() }) }
        composable(Routes.Deny) { Messages.Denied(onBank = { leave() }) }
        composable(Routes.RecoveryRequired) { Messages.RecoveryRequired(onBank = { leave() }) }
    }
    }
}

/** Debug-only index of every screen, like the "Flows" list in Figma Present. */
@OptIn(ExperimentalLayoutApi::class)
@Composable
private fun GalleryScreen(nav: NavHostController, flow: FlowState) {
    val c = Vc.colors
    val groups = listOf(
        "Bắt đầu" to listOf("Màn chào" to Routes.Splash, "Đăng nhập / Đăng ký" to Routes.Auth, "Điều khoản và đồng ý" to Routes.Terms),
        "Danh tính" to listOf(
            "Số điện thoại" to Routes.Phone, "OTP" to Routes.Otp, "OTP nhập sai" to Routes.OtpError,
            "CCCD mặt trước" to Routes.IdFront, "CCCD bị lóa" to Routes.IdFrontGlare, "CCCD mặt sau" to Routes.IdBack,
            "Xem lại 2 mặt CCCD" to Routes.IdReview, "Kiểm tra thông tin" to Routes.Confirm, "Sửa thông tin" to Routes.EditInfo,
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
            "Bị gián đoạn" to Routes.Interrupted, "Lượt quay hết hạn" to Routes.FaceExpired, "Không thu được giọng" to Routes.NoVoice, "Video chưa sẵn sàng" to Routes.UploadFailed,
            "Kiểm tra lâu" to Routes.Slow, "Xác nhận dừng" to Routes.ExitConfirm, "Đã dừng" to Routes.Stopped,
            "Bỏ qua nháy màu" to Routes.FlashSkipped, "Không thành công" to Routes.Deny,
            "Cần khôi phục" to Routes.RecoveryRequired,
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
