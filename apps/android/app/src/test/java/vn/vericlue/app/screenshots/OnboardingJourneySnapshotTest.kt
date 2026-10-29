package vn.vericlue.app.screenshots

import app.cash.paparazzi.DeviceConfig
import app.cash.paparazzi.Paparazzi
import androidx.compose.runtime.Composable
import com.android.resources.Density
import com.android.resources.ScreenOrientation
import org.junit.Rule
import org.junit.Test
import vn.vericlue.app.capture.FaceTimeline
import vn.vericlue.app.capture.IdQuality
import vn.vericlue.app.flow.FramingState
import vn.vericlue.app.flow.FlowRules
import vn.vericlue.app.flow.Purpose
import vn.vericlue.app.flow.TurnDir
import vn.vericlue.app.ui.screens.AuthScreen
import vn.vericlue.app.ui.screens.BankStartScreen
import vn.vericlue.app.ui.screens.CheckingScreen
import vn.vericlue.app.ui.screens.ConfirmInfoScreen
import vn.vericlue.app.ui.screens.EditInfoScreen
import vn.vericlue.app.ui.screens.FaceChallengeContent
import vn.vericlue.app.ui.screens.FaceReadyScreen
import vn.vericlue.app.ui.screens.FramingScreen
import vn.vericlue.app.ui.screens.IdProcessingScreen
import vn.vericlue.app.ui.screens.IdScanScreen
import vn.vericlue.app.ui.screens.Messages
import vn.vericlue.app.ui.screens.OtpScreen
import vn.vericlue.app.ui.screens.PhoneScreen
import vn.vericlue.app.ui.screens.ReviewScreen
import vn.vericlue.app.ui.screens.SplashScreen
import vn.vericlue.app.ui.screens.SuccessScreen
import vn.vericlue.app.ui.screens.TermsScreen
import vn.vericlue.app.ui.screens.VoiceScreen
import vn.vericlue.app.ui.theme.VcTheme

/** Actual Compose screens, ordered for review. Every field and camera image is synthetic. */
abstract class OnboardingJourneySnapshots(device: DeviceConfig, private val complete: Boolean = false) {
    @get:Rule val paparazzi = Paparazzi(deviceConfig = device)
    private val n: () -> Unit = {}
    private val timeline = FaceTimeline.demo(listOf(TurnDir.Left, TurnDir.Right))
    private val fields = listOf(
        "Họ và tên" to "NGƯỜI DÙNG MINH HỌA", "Số định danh cá nhân" to "000000000000",
        "Ngày sinh" to "01/01/1995", "Giới tính" to "Nam", "Nơi cư trú" to "Địa chỉ minh họa",
    )

    private fun shot(name: String, dark: Boolean, content: @Composable () -> Unit) {
        paparazzi.snapshot(name + if (dark) "_dark" else "_light") {
            VcTheme(dark = dark, motionEnabled = false) { content() }
        }
    }

    @Test fun orderedJourney() {
        for (dark in listOf(false, true)) {
            if (complete) {
                shot("00_host", dark) { BankStartScreen(n, n) }
                shot("01_splash", dark) { SplashScreen(n) }
                shot("02_auth", dark) { AuthScreen(n, n, n) }
            }
            shot("03_terms", dark) { TermsScreen(n, n) }
            shot("03b_terms_selected", dark) { TermsScreen(n, n, initialAccepted = true) }
            shot("04_phone", dark) { PhoneScreen(n) {} }
            shot("05_otp", dark) { OtpScreen(n, n, sms = "Mã dùng thử: 482910.") }
            shot("06_card_front", dark) { IdScanScreen(false, null, n, n, n) }
            if (complete) shot("07_card_processing", dark) { IdProcessingScreen(n, n) }
            shot("08_confirm", dark) { ConfirmInfoScreen(n, n, n, fields = fields) }
            shot("09_face_ready", dark) { FaceReadyScreen(n, n, n) }
            if (complete) {
                shot("10_face_framing", dark) { FramingScreen(n, n, live = FramingState.Good) }
                shot("11_face_still", dark) { FaceChallengeContent(timeline, FaceTimeline.Phase.Colour(0), n) }
                shot("12_face_colour", dark) { FaceChallengeContent(timeline, FaceTimeline.Phase.Colour(2), n) }
                shot("13_face_gaze", dark) { FaceChallengeContent(timeline, FaceTimeline.Phase.Gaze(0.25, 0.55), n) }
                shot("14_face_left", dark) { FaceChallengeContent(timeline, FaceTimeline.Phase.Head(0, TurnDir.Left), n) }
                shot("15_face_right", dark) { FaceChallengeContent(timeline, FaceTimeline.Phase.Head(1, TurnDir.Right), n) }
                shot("16_face_front", dark) { FaceChallengeContent(timeline, FaceTimeline.Phase.Head(2, null), n) }
                shot("17_checking", dark) { CheckingScreen(Purpose.Onboarding, n, auto = false) }
            }
            shot("18_success", dark) { SuccessScreen(Purpose.Onboarding, n, auto = false, checked = FlowRules.checkedByServer(false)) }
        }
    }

    @Test fun conditionalAndErrorStates() {
        for (dark in listOf(false, true)) {
            if (complete) shot("b01_terms_details", dark) { TermsScreen(n, n, initialAccepted = true, initialDetailsOpen = true) }
            shot("b02_card_back", dark) { IdScanScreen(true, null, n, n, n) }
            shot("b03_voice", dark) { VoiceScreen(n, n, sentence = "Tôi xác nhận danh tính, mã số tám ba năm một.") }
            if (complete) {
                shot("b04_voice_recording", dark) { VoiceScreen(n, n, startRecording = true, sentence = "Tôi xác nhận danh tính, mã số tám ba năm một.") }
                shot("b05_edit", dark) { EditInfoScreen(n, {}, n, fields = fields) }
                shot("b06_card_ready", dark) { IdScanScreen(false, IdQuality(500.0, 0.0,
                    "000000000000||NGUOI DUNG MINH HOA|01011995|Nam|Dia chi minh hoa|01012023",
                    portraitPresent = true), n, n, n) }
                shot("b07_success_voice", dark) { SuccessScreen(Purpose.Onboarding, n, auto = false, checked = FlowRules.checkedByServer(true)) }
                shot("e01_otp_error", dark) { OtpScreen(n, n, startWithError = true) }
                shot("e06_card_glare", dark) { IdScanScreen(false, IdQuality(500.0, 0.5, null), n, n, n) }
            }
            shot("e02_card_timeout", dark) { IdScanScreen(false, null, n, n, n, timedOut = true) }
            shot("e03_card_retry", dark) { IdProcessingScreen(n, n, error = "Chưa đọc được mã QR. Đưa mặt có mã QR vào khung rồi thử lại.") }
            shot("e04_review", dark) { ReviewScreen(n) }
            shot("e05_network", dark) { Messages.Network(n, n) }
        }
    }
}

class OnboardingJourneySnapshotTest : OnboardingJourneySnapshots(DeviceConfig.PIXEL_5, complete = true)
class CompactOnboardingJourneySnapshotTest : OnboardingJourneySnapshots(DeviceConfig(
    screenWidth = 375, screenHeight = 812, xdpi = 160, ydpi = 160, density = Density.MEDIUM,
))
class LargeTextOnboardingJourneySnapshotTest : OnboardingJourneySnapshots(DeviceConfig(
    screenWidth = 375, screenHeight = 812, xdpi = 160, ydpi = 160, density = Density.MEDIUM, fontScale = 2f,
))
class LandscapeOnboardingJourneySnapshotTest : OnboardingJourneySnapshots(DeviceConfig(
    screenWidth = 812, screenHeight = 375, xdpi = 160, ydpi = 160, density = Density.MEDIUM,
    orientation = ScreenOrientation.LANDSCAPE,
))
