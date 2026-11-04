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
import android.os.SystemClock
import androidx.compose.ui.geometry.Rect
import vn.vericlue.app.capture.FramingAlignmentGate
import vn.vericlue.app.capture.FaceAttemptIssue
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
import kotlinx.coroutines.async
import kotlinx.coroutines.delay
import kotlinx.coroutines.withContext
import kotlinx.coroutines.launch
import kotlinx.coroutines.withTimeoutOrNull
import kotlinx.coroutines.currentCoroutineContext
import kotlinx.coroutines.ensureActive
import java.util.concurrent.atomic.AtomicReference
import vn.vericlue.app.BuildConfig
import vn.vericlue.app.capture.CameraSession
import vn.vericlue.app.capture.MuxedVoiceCapture
import vn.vericlue.app.capture.MuxedVoiceDecodedAudio
import vn.vericlue.app.capture.MUXED_VOICE_LIMIT_MS
import vn.vericlue.app.capture.av.MuxedVoiceAudioDecoder
import vn.vericlue.app.capture.av.MuxedVoiceAudioException
import vn.vericlue.app.capture.CccdInfo
import vn.vericlue.app.capture.CccdQr
import vn.vericlue.app.capture.IdAutoCapture
import vn.vericlue.app.capture.IdAutoCaptureScheduler
import vn.vericlue.app.capture.IdQuality
import vn.vericlue.app.ui.screens.idFields
import vn.vericlue.app.capture.CaptureClock
import vn.vericlue.app.capture.ColorSchedule
import vn.vericlue.app.capture.WavRecorder
import vn.vericlue.app.capture.AudioCaptureState
import vn.vericlue.app.capture.VoiceCapture
import vn.vericlue.app.capture.VoiceCaptureFailure
import vn.vericlue.app.data.AccountStore
import vn.vericlue.app.data.PrefsStore
import vn.vericlue.app.flow.AccountEntry
import vn.vericlue.app.flow.AccountFlow
import vn.vericlue.app.security.AndroidAccountKeys
import vn.vericlue.app.data.api.ColorEvent
import vn.vericlue.app.capture.FaceTimeline
import vn.vericlue.app.data.api.SessionApi
import vn.vericlue.app.data.api.AccountAccessSession
import vn.vericlue.app.data.api.AccountAccessSetupRequest
import vn.vericlue.app.data.api.ApiResult
import vn.vericlue.app.flow.AccountAccessRules
import vn.vericlue.app.ui.screens.LoginScreen
import vn.vericlue.app.ui.screens.CredentialSetupScreen
import vn.vericlue.app.ui.screens.AccountHomeScreen
import vn.vericlue.app.ui.screens.AccountHomeData
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
import vn.vericlue.app.ui.screens.PrivacyStopScreen
import vn.vericlue.app.flow.PrivacyNotice
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
     * Release always uses API. Debug may opt in at build time; gallery remains an explicit preview.
     */
    var live by mutableStateOf(BuildConfig.LIVE_API_DEFAULT)

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

/** Clear protected destinations so Back never reopens an authenticated profile. */
private fun NavHostController.toBank() = navigate(Routes.Login) {
    popUpTo(graph.id) { inclusive = true }
    launchSingleTop = true
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
    var live by remember { mutableStateOf(LiveFlow(api, enforcePrivacy = true)) }
    val accounts = remember {
        AccountStore(PrefsStore(context.applicationContext.getSharedPreferences("vericlue.account", Context.MODE_PRIVATE)))
    }
    val loginHint = remember {
        context.applicationContext.getSharedPreferences("vericlue.login", Context.MODE_PRIVATE)
            .edit().remove(vn.vericlue.app.data.LoginHint.KEY).apply()
        vn.vericlue.app.data.LoginHint(vn.vericlue.app.data.EncryptedStore(
            PrefsStore(context.applicationContext.getSharedPreferences("vericlue.login.secure", Context.MODE_PRIVATE)),
            { vn.vericlue.app.security.loginHintKey() },
        ))
    }
    var rememberedUsername by remember { mutableStateOf<String?>(null) }
    var rememberedFullName by remember { mutableStateOf<String?>(null) }
    var rememberedAccountId by remember { mutableStateOf<String?>(null) }
    val accountFlow = remember {
        AccountFlow(accounts, AndroidAccountKeys(), BuildConfig.SIGNED_MEDIA,
            warn = { Log.w("VeriClue", it) })
    }
    var accountEntry by remember { mutableStateOf<AccountEntry?>(null) }
    var restoredAccount by remember { mutableStateOf<vn.vericlue.app.data.StoredAccount?>(null) }
    // Credentials, profile and access bearer are memory-only; never rememberSaveable or log them.
    var access by remember { mutableStateOf<AccountAccessSession?>(null) }
    var accessGeneration by remember { mutableStateOf(0L) }
    var loginUsername by remember { mutableStateOf("") }
    var loginPassword by remember { mutableStateOf("") }
    var setupUsername by remember { mutableStateOf("") }
    var setupPassword by remember { mutableStateOf("") }
    var setupConfirmation by remember { mutableStateOf("") }
    var profileConsent by remember { mutableStateOf(false) }
    var accessError by remember { mutableStateOf<String?>(null) }
    var loginNotice by remember { mutableStateOf<String?>(null) }
    var credentialsReady by remember { mutableStateOf(false) }
    var quickFaceLoginOpen by remember { mutableStateOf(false) }
    val recorder = remember { WavRecorder() }
    val activeMuxedCapture = remember { AtomicReference<MuxedVoiceCapture?>(null) }
    var hasCamera by remember { mutableStateOf(granted(context, Manifest.permission.CAMERA)) }
    var hasMic by remember { mutableStateOf(granted(context, Manifest.permission.RECORD_AUDIO)) }
    // Asked when first needed (short flow): the camera when it opens, the mic at the reading step.
    val askPermissions = rememberLauncherForActivityResult(ActivityResultContracts.RequestMultiplePermissions()) { result ->
        result[Manifest.permission.CAMERA]?.let { hasCamera = it; if (!it) nav.go(Routes.ErrorCamera) }
        result[Manifest.permission.RECORD_AUDIO]?.let { hasMic = it; if (!it) nav.go(Routes.ErrorMic) }
    }
    val exit = {
        camera.stopRecording()
        camera.lockAeAwb(false)
        recorder.stop()
        nav.go(Routes.ExitConfirm)
    }

    // A single fresh card image binds portrait and QR; the server independently verifies it.
    var idFront by remember { mutableStateOf<Pair<ByteArray, IdQuality>?>(null) }
    var idBack by remember { mutableStateOf<Pair<ByteArray, IdQuality>?>(null) }
    var cccd by remember { mutableStateOf<CccdInfo?>(null) }
    var phone by remember { mutableStateOf("") }
    var otpError by remember { mutableStateOf<String?>(null) }
    var busy by remember { mutableStateOf(false) }

    // Short flow: the confirm screen comes after the face recording. Nothing of the face part is sent
    // before the confirm: the server refuses a confirm or a new card once it has media (FLOW-05 runbook).
    var faceCaptured by remember { mutableStateOf(false) }
    var localFaceIssue by remember { mutableStateOf<String?>(null) }
    var localVoiceAgain by remember { mutableStateOf(false) }
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
        val generation = ++accessGeneration
        loginPassword = ""
        setupPassword = ""
        setupConfirmation = ""
        profileConsent = false
        accessError = null
        credentialsReady = false
        activeMuxedCapture.get()?.cancel()
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
        if (requested == Purpose.Reauth && (!flow.live || !BuildConfig.SIGNED_MEDIA ||
                withContext(Dispatchers.IO) { accounts.load() } == null)) {
            if (generation == accessGeneration) {
                loginNotice = "Hãy đăng ký tài khoản trên điện thoại này trước khi dùng đăng nhập khuôn mặt."
                nav.toBank()
            }
            return@once
        }
        val entry = if (flow.live) withContext(Dispatchers.IO) {
            runCatching { accountFlow.begin(requested) }.getOrNull()
        } else null
        if (generation != accessGeneration) return@once
        if (flow.live && entry == null) {
            nav.go(Routes.ErrorService)
            return@once
        }
        if (requested == Purpose.Reauth && entry?.route == Routes.RecoveryRequired) {
            nav.go(Routes.RecoveryRequired)
            return@once
        }
        if (requested == Purpose.Reauth && (!flow.live || entry?.purpose != Purpose.Reauth || entry?.previous == null)) {
            loginNotice = "Hãy đăng ký tài khoản trên điện thoại này trước khi dùng đăng nhập khuôn mặt."
            nav.toBank()
            return@once
        }
        flow.purpose = entry?.purpose ?: requested
        live = LiveFlow(api, mediaSigner = entry?.signer, enforcePrivacy = true).apply { bindAccount(entry?.previous) }
        accountEntry = entry
        entry?.hint?.let { Toast.makeText(context, it, Toast.LENGTH_LONG).show() }
        if (requested == Purpose.Reauth && entry?.route == Routes.Terms) {
            quickFaceLoginOpen = true
            return@once
        }
        nav.go(if (requested == Purpose.Reauth && entry?.route == Routes.Terms) Routes.FaceLogin
            else entry?.route ?: if (requested == Purpose.Onboarding) Routes.Terms else Routes.Phone)
    }

    /** One continuous card scan. A retry never joins evidence from different photos/cards. */
    @Composable
    fun IdCaptureRoute() {
        val observation by camera.idQuality.collectAsState()
        val captureScope = rememberCoroutineScope()
        val scheduler = remember { IdAutoCaptureScheduler() }
        var scanActive by remember { mutableStateOf(true) }
        var captured by remember { mutableStateOf(false) }
        var taking by remember { mutableStateOf(false) }
        var extracted by remember { mutableStateOf<IdQuality?>(null) }
        var hintExpiresMs by remember { mutableStateOf(0L) }
        var captureJob by remember { mutableStateOf<kotlinx.coroutines.Job?>(null) }
        DisposableEffect(Unit) {
            onDispose {
                scanActive = false
                scheduler.cancel()
                captureJob?.cancel()
                camera.clearQr()
                camera.unbind()
            }
        }
        LaunchedEffect(Unit) {
            camera.clearQr()
            idHint = null
            if (!hasCamera) askPermissions.launch(arrayOf(Manifest.permission.CAMERA))
        }
        LaunchedEffect(hasCamera) {
            if (hasCamera && !camera.start(lifecycleOwner, back = true)) {
                scanActive = false
                scheduler.cancel()
                nav.go(Routes.ErrorDevice)
            }
        }
        fun showCaptureHint(message: String) {
            idHint = message
            hintExpiresMs = SystemClock.elapsedRealtime() + 3000L
        }
        fun cancelCapture() {
            scanActive = false
            scheduler.cancel()
            captureJob?.cancel()
            camera.clearQr()
        }
        BackHandler {
            cancelCapture()
            nav.popBackStack()
        }
        fun capture(attempt: Long) {
            if (!scanActive || taking || captured || !scheduler.isCurrent(attempt)) return
            taking = true
            extracted = null
            idHint = null
            val sessionId = live.session?.sessionId
            camera.clearQr()
            captureJob = captureScope.launch {
                var serverRetry = false
                try {
                    val shot = withTimeoutOrNull(8000) { camera.captureId() }
                    currentCoroutineContext().ensureActive()
                    if (!scheduler.isCurrent(attempt)) return@launch
                    if (flow.live && live.session?.sessionId != sessionId) {
                        scanActive = false
                        scheduler.cancel()
                        nav.go(Routes.ErrorSession)
                        return@launch
                    }
                    if (shot == null) {
                        showCaptureHint("Chưa chụp được ảnh rõ. Giữ yên thẻ, ứng dụng sẽ tự thử lại.")
                        return@launch
                    }
                    val q = shot.second
                    if (!vn.vericlue.app.capture.idCaptureCanSubmit(q, serverAvailable = flow.live)) {
                        showCaptureHint(idScanHint(q, back = false))
                        return@launch
                    }
                    extracted = q
                    if (flow.live) {
                        serverRetry = true
                        // An incomplete local extraction cannot be accepted by a client-QR mock server.
                        val localComplete = vn.vericlue.app.capture.idCaptureUsable(q, false, false)
                        val (hint, error) = live.sendIdCard(shot.first, null, q.qr.takeIf { localComplete })
                        currentCoroutineContext().ensureActive()
                        if (!scheduler.isCurrent(attempt)) return@launch
                        if (live.session?.sessionId != sessionId) {
                            scanActive = false
                            scheduler.cancel()
                            nav.go(Routes.ErrorSession)
                            return@launch
                        }
                        if (error != null) {
                            scanActive = false
                            scheduler.cancel()
                            nav.go(errorRoute(error))
                            return@launch
                        }
                        if (hint != null || live.idFields == null) {
                            showCaptureHint(idScanErrorText(hint))
                            extracted = null
                            return@launch
                        }
                        cccd = FlowRules.cccdFrom(live.idFields!!)
                    } else {
                        cccd = CccdQr.parse(q.qr)
                    }
                    idFront = shot
                    idBack = null
                    idConfirmed = false
                    faceCaptured = false
                    captured = true
                    delay(450)
                    camera.unbind()
                    nav.go(Routes.Confirm)
                } catch (cancelled: kotlinx.coroutines.CancellationException) {
                    throw cancelled
                } catch (_: Exception) {
                    showCaptureHint("Chưa trích xuất được thông tin. Giữ đủ thẻ trong khung, ứng dụng sẽ tự thử lại.")
                    extracted = null
                } finally {
                    if (scheduler.isCurrent(attempt)) {
                        taking = false
                        camera.clearQr()
                        if (captured) scheduler.cancel()
                        else scheduler.retry(attempt, SystemClock.elapsedRealtime(), serverRetry)
                    }
                }
            }
        }
        LaunchedEffect(hasCamera, captured) {
            if (!hasCamera || captured) return@LaunchedEffect
            delay(IdAutoCapture.START_DELAY_MS)
            while (!captured && scanActive) {
                val q = camera.idQuality.value
                val nowMs = SystemClock.elapsedRealtime()
                if (idHint != null && nowMs >= hintExpiresMs) idHint = null
                if (q != null) scheduler.offer(q, nowMs)?.let(::capture)
                delay(250)
            }
        }
        IdScanScreen(false, observation,
            onBack = { cancelCapture(); nav.popBackStack() }, onStop = { cancelCapture(); exit() },
            taking = taking || captured, hint = idHint, extracted = extracted)
    }

    fun startFace() {
        flow.newChallenge()
        camera.stopRecording()
        camera.deleteVideo()
        camera.lockAeAwb(false)
        localFaceIssue = null
        faceCaptured = false
        live.dropFaceAttempt()
        nav.go(Routes.Framing)
    }

    /** Leaves the flow: camera off, session data dropped. */
    fun leave() {
        accessGeneration++
        quickFaceLoginOpen = false
        val retiringToken = access?.accessToken
        access = null
        loginPassword = ""
        setupPassword = ""
        setupConfirmation = ""
        setupUsername = ""
        profileConsent = false
        accessError = null
        credentialsReady = false
        if (retiringToken != null) scope.launch { api.logoutAccount(retiringToken) }
        activeMuxedCapture.get()?.cancel()
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

    suspend fun rememberProfile(profile: vn.vericlue.app.data.api.AccountProfile): Boolean {
        val generation = accessGeneration
        withContext(Dispatchers.IO) { loginHint.save(profile) }
        if (generation != accessGeneration) return false
        rememberedUsername = profile.username
        rememberedFullName = profile.fullName
        rememberedAccountId = profile.accountId
        return true
    }

    suspend fun showAccount(value: AccountAccessSession) {
        if (!rememberProfile(value.profile)) { api.logoutAccount(value.accessToken); return }
        quickFaceLoginOpen = false
        camera.unbind()
        camera.deleteVideo()
        recorder.stop()
        live.reset()
        accountEntry = null
        idFront = null
        idBack = null
        cccd = null
        phone = ""
        loginPassword = ""
        setupPassword = ""
        setupConfirmation = ""
        accessError = null
        loginNotice = null
        access = value
        nav.navigate(Routes.AccountHome) { popUpTo(nav.graph.id) { inclusive = true }; launchSingleTop = true }
    }

    fun loginPasswordAccount() = once {
        accessError = null
        val username = AccountAccessRules.username(loginUsername)
        val password = loginPassword
        if (!AccountAccessRules.validUsername(username) || !AccountAccessRules.validPassword(password)) {
            accessError = "Vui lòng nhập tên đăng nhập và mật khẩu đã thiết lập."
            return@once
        }
        val generation = ++accessGeneration
        val result = api.loginWithPassword(username, password)
        if (generation != accessGeneration) {
            if (result is ApiResult.Ok) api.logoutAccount(result.value.accessToken)
            return@once
        }
        loginPassword = ""
        when (result) {
            is ApiResult.Err -> accessError = AccountAccessRules.error(result)
            is ApiResult.Ok -> if (AccountAccessRules.sessionValid(result.value, "password", username)) {
                showAccount(result.value)
            } else {
                api.logoutAccount(result.value.accessToken)
                accessError = "Phản hồi đăng nhập chưa hợp lệ. Vui lòng thử lại."
            }
        }
    }

    fun refreshAccount() = once {
        val current = access ?: return@once
        val generation = accessGeneration
        when (val result = api.accountProfile(current.accessToken)) {
            is ApiResult.Err -> if (generation == accessGeneration && access?.accessToken == current.accessToken) {
                if (result.error in setOf(vn.vericlue.app.data.api.ApiError.Unauthorized, vn.vericlue.app.data.api.ApiError.Expired)) {
                    leave(); loginNotice = "Phiên đăng nhập đã kết thúc. Vui lòng đăng nhập lại."
                } else accessError = AccountAccessRules.error(result)
            }
            is ApiResult.Ok -> if (generation == accessGeneration && access?.accessToken == current.accessToken) {
                if (AccountAccessRules.profileValid(result.value) && AccountAccessRules.sameProfile(current.profile, result.value)) {
                    access = current.copy(profile = result.value); accessError = null
                } else { leave(); loginNotice = "Không thể tiếp tục phiên đăng nhập này." }
            }
        }
    }

    fun saveCredentials() = once {
        val current = live.session
        val expectedAccount = live.accountReceipt ?: live.boundAccount
        val username = AccountAccessRules.username(setupUsername)
        accessError = null
        if (current == null || expectedAccount == null || !flow.live) {
            accessError = "Vui lòng xác minh tài khoản trước khi thiết lập đăng nhập."; return@once
        }
        if (!Regex("0[0-9]{9}").matches(username)) {
            accessError = "Vui lòng sử dụng số điện thoại 10 chữ số đã xác minh."; return@once
        }
        if (!AccountAccessRules.validPassword(setupPassword) || setupPassword != setupConfirmation) {
            accessError = "Mật khẩu cần 12–128 ký tự và hai lần nhập phải khớp nhau."; return@once
        }
        if (!profileConsent) { accessError = "Vui lòng xác nhận lựa chọn lưu hồ sơ để tiếp tục."; return@once }
        val generation = accessGeneration
        when (val result = api.setupAccountAccess(current.sessionId, current.token,
            AccountAccessSetupRequest(username, setupPassword, profileConsent, "account-profile-v1"))) {
            is ApiResult.Err -> if (generation == accessGeneration) {
                if (result.code in setOf("account_setup_conflict", "account_already_configured")) {
                    leave(); loginUsername = username
                    loginNotice = "Tài khoản đã có thông tin đăng nhập. Hãy dùng mật khẩu đã chọn hoặc đăng nhập khuôn mặt."
                } else accessError = AccountAccessRules.error(result)
            }
            is ApiResult.Ok -> if (generation == accessGeneration) {
                if (!AccountAccessRules.profileValid(result.value) || result.value.accountId != expectedAccount.accountId ||
                    result.value.username != username || result.value.evaluationMode != current.evaluationMode ||
                    result.value.demoPolicyId != current.demoPolicyId) {
                    accessError = "Thông tin tài khoản chưa khớp. Vui lòng thử lại."
                } else {
                    if (!rememberProfile(result.value)) return@once
                    loginUsername = username
                    setupPassword = ""; setupConfirmation = ""
                    credentialsReady = true
                    nav.navigate(Routes.BankOpened) { popUpTo(Routes.CredentialSetup) { inclusive = true } }
                }
            }
        }
    }

    fun follow(next: Next) {
        if (live.privacy.stopping) return
        if (flow.live && live.session == null) return
        val route = when (next) {
            is Next.To -> next.route
            is Next.Fail -> errorRoute(next.error)
        }
        if (FlowRules.closesCameraOnResult(route)) camera.unbind()
        nav.navigate(route) { popUpTo(Routes.Uploading) { inclusive = true } }
    }

    suspend fun completeAccountSubmission(next: Next, generation: Long) {
        if (generation != accessGeneration) return
        val finished = accountEntry?.let { accountFlow.finish(it, live, next) } ?: next
        if (generation != accessGeneration) return
        if (finished == Next.To(Routes.Success) && flow.purpose == Purpose.Reauth) {
            camera.unbind()
            val current = live.session
            val generation = accessGeneration
            if (current == null) follow(Next.Fail(vn.vericlue.app.data.api.ApiError.BadResponse))
            else when (val result = api.loginAfterFace(current.sessionId, current.token)) {
                is ApiResult.Err -> if (generation == accessGeneration) {
                    if (result.code == "account_setup_required") {
                        accessError = null
                        setupUsername = ""; setupPassword = ""; setupConfirmation = ""; profileConsent = false
                        nav.navigate(Routes.CredentialSetup) { popUpTo(Routes.Uploading) { inclusive = true } }
                    } else {
                        leave(); accessError = AccountAccessRules.error(result)
                    }
                }
                is ApiResult.Ok -> if (generation == accessGeneration) {
                    if (AccountAccessRules.sessionValid(result.value, "face", binding = live.accountBinding)) showAccount(result.value)
                    else {
                        api.logoutAccount(result.value.accessToken)
                        leave(); accessError = "Phản hồi đăng nhập chưa hợp lệ. Vui lòng thử lại."
                    }
                } else api.logoutAccount(result.value.accessToken)
            }
        } else follow(finished)
    }

    /** Retry only unsubmitted local media; retain the server's current phrase and challenge id. */
    fun retryLocalVoice() {
        activeMuxedCapture.get()?.cancel()
        camera.stopRecording()
        camera.deleteVideo()
        recorder.stop()
        live.pendingWav = null
        live.audioOffsetMs = null
        val target = FlowRules.voiceLocalRetryRoute(localVoiceAgain)
        nav.navigate(target) {
            popUpTo(target) { inclusive = true }
            launchSingleTop = true
        }
    }

    @Composable
    fun VoiceRoute(again: Boolean) {
        val legacyLevel by recorder.level.collectAsState()
        val muxedLevel by camera.voiceLevel.collectAsState()
        val nativeDurationMs by camera.voiceRecordedDurationMs.collectAsState()
        val audioState by recorder.state.collectAsState()
        val voiceScope = rememberCoroutineScope()
        val isLive = flow.live
        val capture = remember(again, isLive) {
            VoiceCapture(
                scope = voiceScope,
                prepareVideo = { !isLive },
                startAudio = { hasMic && recorder.start(voiceScope) },
                stopAudio = { recorder.stop() },
                stopVideo = { camera.stopRecording() },
                onFinished = { wav ->
                    if (again) flow.outcome = DemoOutcome.Pass
                    nav.go(Routes.Uploading)
                },
                onFailure = { failure ->
                    localVoiceAgain = again
                    nav.go(FlowRules.voiceCaptureFailureRoute(
                        failure,
                        cameraGranted = granted(context, Manifest.permission.CAMERA),
                        micGranted = granted(context, Manifest.permission.RECORD_AUDIO),
                    ))
                },
            )
        }
        val sharedCapture = remember(again, isLive, live) {
            MuxedVoiceCapture(
                scope = voiceScope,
                startRecording = {
                    live.audioOffsetMs = null
                    live.pendingWav = null
                    isLive && hasCamera && hasMic && live.privacy.permits("voice_biometrics") &&
                        !live.privacy.stopping && camera.startMuxedVoiceRecording()
                },
                awaitReady = { camera.awaitMuxedVoiceReady() },
                awaitVideo = { camera.finishedVideo(MUXED_VOICE_LIMIT_MS + 5000) },
                stopRecording = { camera.stopRecording() },
                decode = { file ->
                    withContext(Dispatchers.IO) {
                        val decoding = currentCoroutineContext()
                        val audio = try {
                            MuxedVoiceAudioDecoder.decode(file, checkCancelled = { decoding.ensureActive() })
                        } catch (error: MuxedVoiceAudioException) {
                            // Fixed technical code only; no media path, samples, transcript or identifiers.
                            if (BuildConfig.DEBUG) Log.w("VeriClueVoiceCapture", "decode_failed code=${error.code}")
                            throw error
                        }
                        MuxedVoiceDecodedAudio(audio.wav, audio.audioOffsetMs, audio.source)
                    }
                },
                onFinished = { submission ->
                    if (!camera.isCurrentVideo(submission.video) || live.privacy.stopping ||
                        !live.privacy.permits("voice_biometrics")) {
                        nav.go(Routes.ErrorService)
                    } else {
                        live.pendingWav = submission.audio.wav
                        live.audioOffsetMs = submission.audio.audioOffsetMs
                        nav.go(Routes.Uploading)
                    }
                },
                onFailure = { failure ->
                    localVoiceAgain = again
                    nav.go(FlowRules.voiceCaptureFailureRoute(
                        failure,
                        cameraGranted = granted(context, Manifest.permission.CAMERA),
                        micGranted = granted(context, Manifest.permission.RECORD_AUDIO),
                    ))
                },
                failureReason = { camera.muxedVoiceFailure ?: VoiceCaptureFailure.Camera },
            )
        }
        val legacyPhase by capture.phase.collectAsState()
        val sharedPhase by sharedCapture.phase.collectAsState()
        val capturePhase = if (isLive) sharedPhase else legacyPhase
        DisposableEffect(capture, sharedCapture, lifecycleOwner, isLive) {
            if (isLive) activeMuxedCapture.set(sharedCapture)
            val observer = LifecycleEventObserver { _, event ->
                if (event == Lifecycle.Event.ON_STOP) { sharedCapture.cancel(); capture.cancel() }
            }
            lifecycleOwner.lifecycle.addObserver(observer)
            onDispose {
                lifecycleOwner.lifecycle.removeObserver(observer)
                sharedCapture.cancel()
                activeMuxedCapture.compareAndSet(sharedCapture, null)
                capture.cancel()
            }
        }
        LaunchedEffect(audioState, isLive) {
            if (isLive) return@LaunchedEffect
            when (audioState) {
                AudioCaptureState.Completed -> capture.finish()
                AudioCaptureState.Failed -> capture.fail(VoiceCaptureFailure.Audio)
                else -> Unit
            }
        }
        LaunchedEffect(Unit) {
            localVoiceAgain = again
            if (flow.live && !live.privacy.permits("voice_biometrics")) {
                nav.go(Routes.ErrorService)
                return@LaunchedEffect
            }
            if (!hasMic) askPermissions.launch(arrayOf(Manifest.permission.RECORD_AUDIO))
        }
        VoiceScreen(
            onBack = { sharedCapture.cancel(); capture.cancel(); exit() },
            again = again,
            sentence = if (flow.live) live.voicePrompt else null,
            level = if (isLive) muxedLevel else legacyLevel,
            capturePhase = capturePhase,
            recordedDurationMs = if (isLive) nativeDurationMs else null,
            recordingLimitMs = if (isLive) MUXED_VOICE_LIMIT_MS else 8_000L,
            onStartRecording = {
                if (hasMic) {
                    if (isLive) sharedCapture.start() else capture.start()
                } else askPermissions.launch(arrayOf(Manifest.permission.RECORD_AUDIO))
            },
            onFinished = { if (isLive) sharedCapture.finish() else capture.finish() },
        )
    }

    // ADR-0017 §2: going to the background while the camera or mic runs interrupts the attempt.
    val backStack by nav.currentBackStackEntryAsState()
    val currentRoute = backStack?.destination?.route
    LaunchedEffect(currentRoute) {
        if (currentRoute in setOf(Routes.BankStart, Routes.Auth, Routes.Login, Routes.FaceLogin)) {
            restoredAccount = withContext(Dispatchers.IO) { accounts.load() }
            val profile = withContext(Dispatchers.IO) { loginHint.profile() }
            val hint = withContext(Dispatchers.IO) { loginHint.load() }
            rememberedFullName = profile?.fullName
            rememberedAccountId = profile?.accountId
            if (hint != rememberedUsername) {
                rememberedUsername = hint
                if (hint != null && loginUsername.isEmpty()) loginUsername = hint
            }
        }
    }
    LaunchedEffect(access?.accessToken) {
        val current = access ?: return@LaunchedEffect
        val deadline = AccountAccessRules.instant(current.expiresAt)
        val remaining = deadline?.toEpochMilli()?.minus(System.currentTimeMillis()) ?: 0L
        if (remaining > 0) delay(remaining)
        if (access?.accessToken == current.accessToken) {
            leave(); loginNotice = "Phiên đăng nhập đã hết hạn. Vui lòng đăng nhập lại."
        }
    }
    DisposableEffect(lifecycleOwner, currentRoute) {
        val observer = LifecycleEventObserver { _, event ->
            if (event == Lifecycle.Event.ON_STOP) {
                if (quickFaceLoginOpen) {
                    leave(); loginNotice = "Lượt đăng nhập đã dừng. Vui lòng thử lại."
                    return@LifecycleEventObserver
                }
                // Invalidate in-flight access replies before clearing secrets or hiding the profile.
                if (currentRoute in setOf(Routes.Login, Routes.Auth, Routes.FaceLogin, Routes.CredentialSetup) || access != null)
                    accessGeneration++
                loginPassword = ""; setupPassword = ""; setupConfirmation = ""
                if (currentRoute == Routes.CredentialSetup && busy) {
                    leave()
                    loginNotice = "Thiết lập có thể đã hoàn tất. Hãy dùng mật khẩu đã chọn hoặc đăng nhập khuôn mặt."
                    return@LifecycleEventObserver
                }
                if (access != null) {
                    leave(); loginNotice = "Vui lòng đăng nhập lại để tiếp tục."
                    return@LifecycleEventObserver
                }
                if (flow.purpose == Purpose.Reauth && currentRoute == Routes.Uploading) {
                    leave(); loginNotice = "Lượt đăng nhập đã dừng. Vui lòng thử lại."
                    return@LifecycleEventObserver
                }
            }
            // Act on ON_STOP itself: the activity may be recreated before it starts again.
            if (event == Lifecycle.Event.ON_STOP && FlowRules.isInterruptedBy(currentRoute)) {
                activeMuxedCapture.get()?.cancel()
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
        startDestination = Routes.Splash,
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
            BankStartScreen(onOpenAccount = { nav.go(Routes.Splash) }, onGallery = { nav.go(Routes.Gallery) },
                manualFullDemo = restoredAccount?.manualFullDemo == true, preview = !flow.live)
        }
        composable(Routes.BankOpened) {
            BackHandler { leave() }
            if (flow.live && !credentialsReady) {
                LaunchedEffect(Unit) { leave() }
            } else BankOpenedScreen(onDone = {
                leave(); loginNotice = "Thiết lập hoàn tất. Bạn có thể đăng nhập ngay."
            }, manualFullDemo = flow.live && live.manualFullDemo, preview = !flow.live || live.session == null)
        }
        composable(Routes.Gallery) { GalleryScreen(nav, flow) }

        // Start
        composable(Routes.Splash) {
            SplashScreen(onDone = {
                nav.navigate(Routes.Login) { popUpTo(Routes.Splash) { inclusive = true } }
            })
        }
        composable(Routes.Login) {
            LoginScreen(
                username = loginUsername, password = loginPassword,
                onUsernameChange = { loginUsername = it.take(32); accessError = null },
                onPasswordChange = { loginPassword = it.take(256); accessError = null },
                onPasswordLogin = ::loginPasswordAccount,
                onFaceLogin = { loginUsername = ""; loginPassword = ""; enterAccount(Purpose.Reauth) },
                onRegister = { accessError = null; loginPassword = ""; nav.go(Routes.Auth) },
                onRecovery = { loginPassword = ""; enterAccount(Purpose.Recovery) },
                busy = busy, error = accessError, notice = loginNotice,
                rememberedUsername = rememberedUsername,
                rememberedFullName = rememberedFullName,
                faceAvailable = restoredAccount != null &&
                    (rememberedUsername == null || rememberedAccountId == restoredAccount?.receipt?.accountId),
                manualFullDemo = restoredAccount?.manualFullDemo == true,
            )
        }
        composable(Routes.FaceLogin) {
            // Legacy retry destinations re-enter the same inline login flow.
            LaunchedEffect(Unit) { nav.toBank(); enterAccount(Purpose.Reauth) }
        }
        composable(Routes.CredentialSetup) {
            BackHandler { if (!busy) leave() }
            if (!flow.live || live.session == null) {
                LaunchedEffect(Unit) { leave() }
            } else CredentialSetupScreen(
                username = setupUsername, password = setupPassword, confirmation = setupConfirmation,
                onUsernameChange = { setupUsername = it.filter { c -> c in '0'..'9' }.take(10); accessError = null },
                onPasswordChange = { setupPassword = it.take(256); accessError = null },
                onConfirmationChange = { setupConfirmation = it.take(256); accessError = null },
                profileConsent = profileConsent, onProfileConsentChange = { profileConsent = it },
                onSave = ::saveCredentials, onBack = { if (!busy) leave() },
                busy = busy, error = accessError, manualFullDemo = live.manualFullDemo,
                fullName = live.idFields?.fullName,
                phoneLocked = Regex("0[0-9]{9}").matches(phone),
                recovery = flow.purpose == Purpose.Recovery,
            )
        }
        composable(Routes.AccountHome) {
            BackHandler { leave() }
            val profile = access?.profile
            if (profile == null || !AccountAccessRules.profileValid(profile)) {
                LaunchedEffect(Unit) { leave() }
            } else AccountHomeScreen(
                profile = AccountHomeData(
                    fullName = profile.fullName, username = profile.username, accountId = profile.accountId,
                    maskedIdentityNumber = profile.maskedIdNumber,
                    createdAt = AccountAccessRules.displayDate(profile.createdAt),
                    expiresAt = AccountAccessRules.displayDate(profile.expiresAt),
                    manualFullDemo = profile.evaluationMode == "manual_full_demo",
                ),
                onLogout = { leave(); loginNotice = "Bạn đã đăng xuất." },
                onPrivacy = { nav.go(Routes.AccountPrivacy) },
                onRefresh = ::refreshAccount, busy = busy, error = accessError,
            )
        }
        composable(Routes.AccountPrivacy) {
            if (access == null) { LaunchedEffect(Unit) { leave() } }
            else vn.vericlue.app.ui.components.VcScreen(onBack = { nav.popBackStack() }, actions = {
                vn.vericlue.app.ui.components.PrimaryButton("Đã hiểu", { nav.popBackStack() })
            }) {
                vn.vericlue.app.ui.components.TitleBlock("Quyền riêng tư")
                vn.vericlue.app.ui.components.ContentCard {
                    Text("Hồ sơ tài khoản", style = VcType.section, color = Vc.colors.ink)
                    Text("Tên đăng nhập, họ tên và số căn cước đã che được lưu mã hóa trong thời hạn tài khoản demo. Mật khẩu được băm, không lưu dưới dạng có thể đọc lại.", style = VcType.body, color = Vc.colors.ink)
                    Text("Thời hạn", style = VcType.section, color = Vc.colors.ink)
                    Text("Tài khoản demo có hiệu lực tối đa 24 giờ từ khi tạo. Phiên đăng nhập kết thúc sau tối đa 15 phút hoặc khi bạn đăng xuất.", style = VcType.body, color = Vc.colors.ink)
                    Text("Đăng nhập khuôn mặt", style = VcType.section, color = Vc.colors.ink)
                    Text("Camera chỉ được mở sau khi bạn chọn và đồng ý. Dữ liệu xác minh không dùng để huấn luyện AI. Bạn có thể dừng phiên bất kỳ lúc nào.", style = VcType.body, color = Vc.colors.ink)
                }
            }
        }
        composable(Routes.Auth) {
            BackHandler { leave() }
            AuthScreen(
                onRegister = { enterAccount(Purpose.Onboarding) },
                onLogin = { leave() },
                onRecover = { enterAccount(Purpose.Recovery) },
                manualFullDemo = restoredAccount?.manualFullDemo == true,
                preview = !flow.live,
                onBack = { leave() },
            )
        }
        // Terms and consent on one screen; no intro or permission screen (short flow, 24/10).
        composable(Routes.Terms) {
            var consentError by remember { mutableStateOf<String?>(null) }
            TermsScreen(onBack = { if (!busy) nav.popBackStack() }, purpose = flow.purpose, busy = busy, error = consentError, onAccept = {
                if (!flow.live) nav.go(FlowRules.afterConsent(flow.purpose)) else once {
                    consentError = null
                    val error = live.ensureSession(flow.mockScenario, FlowRules.purposeCode(flow.purpose))
                        ?: live.privacy.grant(flow.purpose, PrivacyNotice.VERSION)
                    if (error != null) {
                        consentError = "Chưa ghi nhận được đồng ý. Hãy kiểm tra kết nối hoặc cập nhật ứng dụng rồi thử lại."
                    } else nav.go(FlowRules.afterConsent(flow.purpose))
                }
            })
        }

        // Stage A: identity
        composable(Routes.Phone) {
            PhoneScreen(onBack = { nav.popBackStack() }, busy = busy, onSend = { number ->
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
                    busy = busy,
                    sms = live.otpSms,
                    serverError = otpError,
                    onCode = { code ->
                        once {
                            when (val r = live.verifyOtp(code)) {
                                LiveFlow.OtpResult.Pass -> nav.go(FlowRules.afterOtp(flow.purpose, accountBound = live.boundAccount != null))
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
        composable(Routes.IdFront) { IdCaptureRoute() }
        composable(Routes.IdFrontGlare) { IdScanScreen(false, IdQuality(500.0, 0.5, null),
            onBack = { nav.popBackStack() }, onStop = exit) }
        // Old saved/debug routes rejoin the same scan; no QR-only fallback screen remains.
        composable(Routes.IdBack) { LaunchedEffect(Unit) { nav.navigate(Routes.IdFront) {
            popUpTo(Routes.IdBack) { inclusive = true }; launchSingleTop = true
        } } }
        composable(Routes.IdReview) {
            LaunchedEffect(Unit) {
                nav.navigate(Routes.IdFront) {
                    popUpTo(Routes.IdReview) { inclusive = true }; launchSingleTop = true
                }
            }
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
            if (flow.live && flow.purpose == Purpose.Reauth) {
                LaunchedEffect(Unit) {
                    nav.navigate(Routes.FaceLogin) { popUpTo(Routes.FaceReady) { inclusive = true }; launchSingleTop = true }
                }
            } else FaceReadyScreen(onBack = { nav.popBackStack() }, onReady = ::startFace,
                manualDemo = flow.live && (live.manualDemo || live.manualFullDemo),
                usesLightChallenge = flow.purpose != Purpose.Reauth, onSkipFlash = {
                camera.unbind()
                nav.go(Routes.FlashSkipped)
            })
        }
        composable(Routes.Framing) {
            var guide by remember { mutableStateOf<Rect?>(null) }
            var gate by remember { mutableStateOf(FramingState.NoFace) }
            var readiness by remember { mutableStateOf(0f) }
            var preparingCamera by remember { mutableStateOf(false) }
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
            // Poll freshness even if StateFlow stops emitting. A frozen Good frame cannot start capture.
            LaunchedEffect(hasCamera, prepared) {
                if (!hasCamera || !prepared) return@LaunchedEffect
                val alignment = FramingAlignmentGate()
                fun updateFraming(): Boolean {
                    val signal = camera.face.value
                    val bounds = camera.previewBounds(signal)?.let { Rect(it.left, it.top, it.right, it.bottom) }
                    val feedback = alignment.update(signal, SystemClock.elapsedRealtime(), bounds, guide)
                    gate = feedback.state
                    readiness = feedback.progress
                    preparingCamera = feedback.preparingCamera
                    return feedback.ready
                }
                fun stillReady(): Boolean {
                    val signal = camera.face.value
                    val bounds = camera.previewBounds(signal)?.let { Rect(it.left, it.top, it.right, it.bottom) }
                    return alignment.acceptsLatest(signal, SystemClock.elapsedRealtime(), bounds, guide)
                }
                while (true) {
                    if (updateFraming()) {
                        val pending = async {
                            try { withTimeoutOrNull(3000) { camera.captureJpeg() } }
                            catch (cancelled: kotlinx.coroutines.CancellationException) { throw cancelled }
                            catch (_: Exception) { null }
                        }
                        while (!pending.isCompleted) {
                            delay(50)
                            if (!stillReady()) {
                                pending.cancel()
                                updateFraming()
                                break
                            }
                        }
                        val shot = if (pending.isCancelled) null else pending.await()
                        if (shot != null && stillReady()) {
                            live.frontalJpeg = shot
                            nav.go(Routes.HoldStill)
                            return@LaunchedEffect
                        }
                        alignment.reset()
                        readiness = 0f
                    }
                    delay(50)
                }
            }
            FramingScreen(
                onExit = exit,
                onCaptured = { nav.go(Routes.HoldStill) },
                live = gate, auto = false, captureProgress = readiness,
                hintOverride = if (preparingCamera) "Đang chuẩn bị camera…" else null,
                onGuidePosition = { rect, _ -> guide = rect },
                reauth = flow.purpose == Purpose.Reauth,
            )
        }
        composable(Routes.HoldStill) {
            val captureScope = rememberCoroutineScope()
            var frontalJob by remember { mutableStateOf<kotlinx.coroutines.Job?>(null) }
            var frontalReady by remember { mutableStateOf(false) }
            var terminal by remember { mutableStateOf(false) }
            DisposableEffect(Unit) { onDispose { frontalJob?.cancel(); camera.lockAeAwb(false) } }
            fun rejectAttempt(issue: FaceAttemptIssue) {
                if (terminal) return
                terminal = true
                frontalJob?.cancel()
                camera.stopRecording()
                camera.lockAeAwb(false)
                camera.deleteVideo()
                live.dropFaceAttempt()
                faceCaptured = false
                localFaceIssue = when (issue) {
                    FaceAttemptIssue.FaceLost -> "Giữ toàn bộ khuôn mặt trong khung và giữ nguyên điện thoại."
                    FaceAttemptIssue.ActionIncomplete -> "Vui lòng quay đầu theo hướng dẫn và giữ tư thế trong giây lát."
                    FaceAttemptIssue.TimeLimit -> "Lượt thu đã hết thời gian. Vui lòng thử lại khi bạn sẵn sàng."
                }
                nav.navigate(Routes.RetryQuality) { popUpTo(Routes.HoldStill) { inclusive = true } }
            }
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
            LaunchedEffect(timeline) {
                if (timeline == null || !ColorSchedule.isSafe(timeline.slots)) nav.go(Routes.ErrorService)
            }
            if (timeline != null && ColorSchedule.isSafe(timeline.slots)) {
                FaceTimelineScreen(
                    timeline,
                    onStop = { terminal = true; frontalJob?.cancel(); exit() },
                    onStart = {
                        live.colorEvents.clear()
                        if (hasCamera) camera.startRecording() else nav.go(Routes.ErrorCamera)
                        camera.debugTrace.bindAttempt(challenge?.challengeId)
                    },
                    recordingStartMs = { camera.recordingStartMs() },
                    onPainted = { slot, t -> slot.index?.let { live.colorEvents += ColorEvent(it, slot.rgb, t) } },
                    onFrontal = { if (hasCamera) frontalJob = captureScope.launch {
                        val shot = try { withTimeoutOrNull(1500) { camera.captureJpeg() } }
                            catch (cancelled: kotlinx.coroutines.CancellationException) { throw cancelled }
                            catch (_: Exception) { null }
                        frontalJob = null
                        if (!terminal) {
                            if (shot != null) { live.frontalJpeg = shot; frontalReady = true }
                            else rejectAttempt(FaceAttemptIssue.FaceLost)
                        }
                    } },
                    onBaselineDone = { camera.lockAeAwb(true) },
                    onColorsDone = { camera.lockAeAwb(false) },
                    onDone = done@ {
                        if (terminal) return@done
                        if (!frontalReady || live.frontalJpeg == null) {
                            rejectAttempt(FaceAttemptIssue.FaceLost)
                            return@done
                        }
                        terminal = true
                        camera.savePresenceDebugTrace()
                        camera.stopRecording()
                        faceCaptured = true
                        val next = FlowRules.afterFace(flow.purpose, idConfirmed, live = flow.live, accountBound = live.boundAccount != null)
                        nav.navigate(next) { if (next == Routes.Confirm) popUpTo(Routes.FaceReady) { inclusive = true } }
                    },
                    onNoRecording = noRecording@ {
                        if (terminal) return@noRecording
                        terminal = true
                        camera.stopRecording(); camera.lockAeAwb(false); camera.deleteVideo()
                        live.dropFaceAttempt(); faceCaptured = false
                        nav.go(Routes.ErrorDevice)
                    },
                    faceSignal = { camera.face.value },
                    onIncomplete = ::rejectAttempt,
                    debugTrace = camera.debugTrace,
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
            )
        }

        // Stage C: voice
        composable(Routes.Voice) { VoiceRoute(again = false) }
        composable(Routes.VoiceAgain) { VoiceRoute(again = true) }

        // Stage D: checking and results
        composable(Routes.Uploading) {
            if (flow.live) {
                LaunchedEffect(Unit) {
                    val requestGeneration = accessGeneration
                    val wav = live.pendingWav
                    // A retry comes back here; LiveFlow resends only what the server has not received.
                    val next = submitWithVideo(camera.finishedVideo()) { video ->
                        if (wav != null) {
                            if (video == null) Next.To(Routes.UploadFailed) else
                                live.submitVoice(wav, video, live.audioOffsetMs, onAccepted = { camera.deleteVideo(preserveDiagnostics = true) })
                        } else {
                            val probe = withContext(Dispatchers.IO) { camera.camProbe() }
                            live.submitFace(
                                video,
                                camera.frameTimes(),
                                camera.clientQuality(video),
                                probe,
                                camera.regionMeans().ifEmpty { null },
                                onMediaAcked = { camera.deleteVideo(preserveDiagnostics = true) },
                            )
                        }
                    }
                    if (requestGeneration != accessGeneration) return@LaunchedEffect
                    completeAccountSubmission(next, requestGeneration)
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
            if (flow.live && flow.purpose != Purpose.Reauth && accountFlow.accountSaved) {
                // Verification is complete; registration finishes only after password setup.
                LaunchedEffect(live.session?.sessionId) {
                    setupUsername = phone.takeIf { Regex("0[0-9]{9}").matches(it) }.orEmpty()
                    setupPassword = ""; setupConfirmation = ""; profileConsent = false
                    accessError = null
                    nav.navigate(Routes.CredentialSetup) { popUpTo(Routes.Success) { inclusive = true } }
                }
            } else SuccessScreen(
                flow.purpose,
                onContinue = {
                    if (!flow.live) nav.go(Routes.BankOpened) else leave()
                },
                checked = if (flow.live) FlowRules.checkedByServer(live.voiceChecked) else null,
                accountReady = if (flow.live && flow.purpose != Purpose.Reauth) accountFlow.accountSaved else null,
                manualFullDemo = flow.live && live.manualFullDemo,
                preview = !flow.live || live.session == null,
            )
        }
        composable(Routes.ManualDemoComplete) {
            vn.vericlue.app.ui.screens.ManualDemoCompleteScreen(onDone = { leave() })
        }
        composable(Routes.Review) { ReviewScreen(onBackToBank = { leave() }) }
        composable(Routes.RetryQuality) {
            RetryQualityScreen(
                onBack = exit,
                onRetake = { flow.outcome = DemoOutcome.Pass; startFace() },
                hint = localFaceIssue ?: if (flow.live) FlowRules.retryHintText(live.retryHint) else null,
                attemptsLeft = if (localFaceIssue != null) null else if (flow.live) live.attemptsLeft else 1,
                hintCode = if (localFaceIssue == null && flow.live) live.retryHint else null,
                captureIncomplete = localFaceIssue != null,
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
        composable(Routes.ErrorMic) { Messages.MicDenied(onRetry = ::retryLocalVoice, onBack = { nav.popBackStack() }) }
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
        composable(Routes.NoVoice) { Messages.NoVoice(onRetry = ::retryLocalVoice, onStop = exit) }
        composable(Routes.VoiceTimeLimit) {
            androidx.activity.compose.BackHandler(onBack = ::retryLocalVoice)
            Messages.VoiceTimeLimit(onRetry = ::retryLocalVoice, onStop = exit)
        }
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
                    nav.go(if (flow.live && live.session != null) Routes.PrivacyStop else Routes.Stopped)
                },
            )
        }
        composable(Routes.PrivacyStop) {
            var requested by remember { mutableStateOf(false) }
            var sending by remember { mutableStateOf(false) }
            var failure by remember { mutableStateOf(false) }
            BackHandler(enabled = requested) { }
            PrivacyStopScreen(sending, requested, failure,
                onResume = { nav.popBackStack() },
                onWithdraw = {
                    if (!sending) {
                        requested = true
                        sending = true
                        camera.clearPresenceDebugTrace()
                        camera.unbind()
                        recorder.stop()
                        scope.launch {
                            try {
                                failure = live.privacy.withdraw() != null
                                if (!failure) {
                                    camera.deleteVideo()
                                    live.reset()
                                    idFront = null; idBack = null; cccd = null
                                    idConfirmed = false; faceCaptured = false
                                    nav.navigate(Routes.Stopped) {
                                        popUpTo(Routes.BankStart) { inclusive = false }
                                        launchSingleTop = true
                                    }
                                }
                            } finally { sending = false }
                        }
                    }
                }, onLeaveUnconfirmed = { leave() })
        }
        composable(Routes.Stopped) {
            BackHandler { leave() }
            Messages.Stopped(onBank = { leave() })
        }
        composable(Routes.FlashSkipped) { Messages.FlashSkipped(onBank = { leave() }) }
        composable(Routes.Deny) { Messages.Denied(onBank = { leave() }) }
        composable(Routes.RecoveryRequired) { Messages.RecoveryRequired(onBank = { leave() }) }
    }
    if (quickFaceLoginOpen) {
        val loginFlow = live
        val generation = accessGeneration
        vn.vericlue.app.ui.screens.QuickFaceLogin(camera, loginFlow, lifecycleOwner,
            onPrepare = {
                val error = if (generation != accessGeneration || loginFlow.boundAccount == null) vn.vericlue.app.data.api.ApiError.Expired
                else loginFlow.ensureSession(flow.mockScenario, "reauth")
                    ?: (if (loginFlow.privacy.permits("face_biometrics")) null
                        else loginFlow.privacy.grant(Purpose.Reauth, PrivacyNotice.VERSION))
                    ?: loginFlow.prepareFace(flow.mockScenario, "reauth")
                error ?: if (loginFlow.challenge == null || loginFlow.challenge?.dynamic != null)
                    vn.vericlue.app.data.api.ApiError.BadResponse else null
            },
            onSubmit = { onCaptureReleased ->
                val recording = camera.finishedVideo()
                val video = (recording as? vn.vericlue.app.capture.VideoResult.Ready)?.file
                // Snapshot camera metadata before unbinding; do not keep the camera active
                // while uploading or waiting for the server's authentication decision.
                val frameTimes = camera.frameTimes()
                val quality = camera.clientQuality(video)
                val regions = camera.regionMeans().ifEmpty { null }
                val probe = withContext(Dispatchers.IO) { camera.camProbe() }
                camera.unbind()
                onCaptureReleased()
                val next = submitWithVideo(recording) { readyVideo ->
                    loginFlow.submitFace(readyVideo, frameTimes, quality, probe,
                        regions,
                        onMediaAcked = { camera.deleteVideo(preserveDiagnostics = true) })
                }
                if (generation == accessGeneration) {
                    completeAccountSubmission(next, generation)
                    if (generation == accessGeneration) quickFaceLoginOpen = false
                }
            },
            onCancel = {
                // Keep the retiring session alive solely for withdrawal, including a pending refresh.
                val abandoned = live
                live = LiveFlow(api, enforcePrivacy = true)
                leave()
                scope.launch { if (abandoned.session != null) abandoned.privacy.withdraw() }
            },
        )
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
            "Quét thẻ căn cước" to Routes.IdFront, "CCCD bị lóa" to Routes.IdFrontGlare,
            "Kiểm tra thông tin" to Routes.Confirm, "Sửa thông tin" to Routes.EditInfo,
        ),
        "Khuôn mặt" to listOf("Chuẩn bị" to Routes.FaceReady, "Căn mặt" to Routes.Framing, "Giữ yên + nháy màu + chấm sáng" to Routes.HoldStill, "Quay đầu" to Routes.TurnHead),
        "Giọng nói" to listOf("Đọc câu" to Routes.Voice, "Đọc lại câu mới" to Routes.VoiceAgain),
        "Kết quả" to listOf(
            "Đang gửi" to Routes.Uploading, "Đang kiểm tra" to Routes.Checking, "Thành công" to Routes.Success,
            "Chưa hoàn tất xác minh" to Routes.Review, "Chụp lại" to Routes.RetryQuality, "Làm lại thử thách" to Routes.RetryChallenge,
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
            FilterChip(selected = !flow.live, onClick = { flow.live = false }, label = { Text("Xem trước · Không chạy AI") })
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
