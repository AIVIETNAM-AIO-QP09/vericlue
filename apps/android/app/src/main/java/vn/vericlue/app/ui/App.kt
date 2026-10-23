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

@Composable
fun VeriClueApp() {
    val nav = rememberNavController()
    val flow = remember { FlowState() }
    val exit = { nav.go(Routes.ExitConfirm) }

    fun startFace() {
        flow.newChallenge()
        nav.go(Routes.Framing)
    }

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
        composable(Routes.BankOpened) { BankOpenedScreen(onDone = { nav.toBank() }) }
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
        composable(Routes.Permission) { PermissionScreen(onBack = { nav.popBackStack() }, onAllow = { nav.go(Routes.Phone) }) }
        composable(Routes.Phone) { PhoneScreen(onBack = { nav.popBackStack() }, onSend = { nav.go(Routes.Otp) }) }
        composable(Routes.Otp) { OtpScreen(onBack = { nav.popBackStack() }, onVerified = { nav.go(FlowRules.afterOtp(flow.purpose)) }) }
        composable(Routes.OtpError) {
            OtpScreen(onBack = { nav.popBackStack() }, onVerified = { nav.go(FlowRules.afterOtp(flow.purpose)) }, startWithError = true)
        }
        composable(Routes.IdFront) { IdCaptureScreen(back = false, glare = false, onBack = { nav.popBackStack() }, onCapture = { nav.go(Routes.IdFrontReview) }) }
        composable(Routes.IdFrontReview) {
            IdReviewScreen(back = false, onBack = { nav.popBackStack() }, onRetake = { nav.popBackStack() }, onConfirm = { nav.go(Routes.IdBack) })
        }
        composable(Routes.IdFrontGlare) { IdCaptureScreen(back = false, glare = true, onBack = { nav.popBackStack() }, onCapture = { nav.go(Routes.IdFront) }) }
        composable(Routes.IdBack) { IdCaptureScreen(back = true, glare = false, onBack = { nav.popBackStack() }, onCapture = { nav.go(Routes.IdBackReview) }) }
        composable(Routes.IdBackReview) {
            IdReviewScreen(back = true, onBack = { nav.popBackStack() }, onRetake = { nav.popBackStack() }, onConfirm = { nav.go(Routes.Confirm) })
        }
        composable(Routes.Confirm) {
            ConfirmInfoScreen(onBack = { nav.popBackStack() }, onCorrect = { nav.go(Routes.FaceReady) }, onEdit = { nav.go(Routes.EditInfo) })
        }
        composable(Routes.EditInfo) {
            EditInfoScreen(onBack = { nav.popBackStack() }, onSave = { nav.go(Routes.FaceReady) }, onRetake = { nav.go(Routes.IdFront) })
        }

        // Stage B: face
        composable(Routes.FaceReady) {
            FaceReadyScreen(onBack = { nav.popBackStack() }, onReady = ::startFace, onSkipFlash = { nav.go(Routes.Voice) })
        }
        composable(Routes.Framing) { FramingScreen(onExit = exit, onCaptured = { nav.go(Routes.HoldStill) }) }
        composable(Routes.HoldStill) { HoldStillScreen(onStop = exit, onDone = { nav.go(Routes.TurnHead) }) }
        composable(Routes.TurnHead) {
            TurnHeadScreen(flow.turnOrder, onExit = exit, onDone = { nav.go(FlowRules.afterTurnHead(flow.purpose)) })
        }

        // Stage C: voice
        composable(Routes.Voice) { VoiceScreen(onBack = exit, onFinished = { nav.go(Routes.Uploading) }) }
        composable(Routes.VoiceAgain) {
            VoiceScreen(onBack = exit, onFinished = { flow.outcome = DemoOutcome.Pass; nav.go(Routes.Uploading) }, again = true)
        }

        // Stage D: checking and results
        composable(Routes.Uploading) { Messages.Uploading(onStop = exit, onDone = { nav.go(Routes.Checking) }) }
        composable(Routes.Checking) {
            CheckingScreen(flow.purpose, onDone = {
                nav.navigate(FlowRules.afterChecking(flow.outcome)) { popUpTo(Routes.Checking) { inclusive = true } }
            })
        }
        composable(Routes.Success) {
            SuccessScreen(flow.purpose, onContinue = {
                if (flow.purpose == Purpose.Onboarding) nav.go(Routes.BankOpened) else nav.toBank()
            })
        }
        composable(Routes.Review) { ReviewScreen(onBackToBank = { nav.toBank() }) }
        composable(Routes.RetryQuality) {
            RetryQualityScreen(onBack = exit, onRetake = { flow.outcome = DemoOutcome.Pass; startFace() })
        }
        composable(Routes.RetryChallenge) {
            RetryChallengeScreen(onBack = exit, onRetry = { flow.outcome = DemoOutcome.Pass; startFace() })
        }

        // Errors and interruptions
        composable(Routes.ErrorCamera) { Messages.CameraDenied(onRetry = { nav.go(Routes.FaceReady) }, onBack = { nav.popBackStack() }) }
        composable(Routes.ErrorMic) { Messages.MicDenied(onRetry = { nav.go(Routes.Voice) }, onBack = { nav.popBackStack() }) }
        composable(Routes.ErrorNetwork) { Messages.Network(onRetry = { nav.go(Routes.Checking) }, onBack = { nav.popBackStack() }) }
        composable(Routes.ErrorSession) { Messages.SessionExpired(onBank = { nav.toBank() }) }
        composable(Routes.ErrorService) { Messages.ServiceDown(onBank = { nav.toBank() }) }
        composable(Routes.ErrorDevice) {
            Messages.DeviceNotReady(onCheck = { nav.go(Routes.Permission) }, onBank = { nav.toBank() }, onBack = exit)
        }
        composable(Routes.Interrupted) { Messages.Interrupted(onRedo = { nav.go(Routes.FaceReady) }, onStop = { nav.go(Routes.Stopped) }) }
        composable(Routes.NoVoice) { Messages.NoVoice(onRetry = { nav.go(Routes.Voice) }, onStop = exit) }
        composable(Routes.UploadFailed) { Messages.UploadFailed(onResend = { nav.go(Routes.Uploading) }, onStop = exit) }
        composable(Routes.Slow) { Messages.Slow(onWait = { nav.go(Routes.Checking) }, onStop = exit) }
        composable(Routes.ExitConfirm) {
            Messages.ExitConfirm(onResume = { nav.go(Routes.FaceReady) }, onStop = { nav.go(Routes.Stopped) })
        }
        composable(Routes.Stopped) { Messages.Stopped(onBank = { nav.toBank() }) }
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
        Text("Kết quả mô phỏng sau bước kiểm tra", style = VcType.label, color = c.muted)
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
