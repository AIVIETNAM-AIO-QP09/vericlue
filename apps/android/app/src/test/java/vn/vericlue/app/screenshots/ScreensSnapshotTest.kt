package vn.vericlue.app.screenshots

import app.cash.paparazzi.DeviceConfig
import app.cash.paparazzi.Paparazzi
import androidx.compose.runtime.Composable
import org.junit.Rule
import org.junit.Test
import vn.vericlue.app.flow.Purpose
import vn.vericlue.app.flow.TurnDir
import vn.vericlue.app.ui.screens.AuthScreen
import vn.vericlue.app.ui.screens.BankOpenedScreen
import vn.vericlue.app.ui.screens.BankStartScreen
import vn.vericlue.app.ui.screens.CheckingScreen
import vn.vericlue.app.ui.screens.ConfirmInfoScreen
import vn.vericlue.app.ui.screens.EditInfoScreen
import vn.vericlue.app.ui.screens.FaceReadyScreen
import vn.vericlue.app.ui.screens.FramingScreen
import vn.vericlue.app.flow.FramingState
import vn.vericlue.app.ui.screens.HoldStillScreen
import vn.vericlue.app.ui.screens.IdCaptureScreen
import vn.vericlue.app.ui.screens.IdReviewScreen
import vn.vericlue.app.ui.screens.Messages
import vn.vericlue.app.ui.screens.OtpScreen
import vn.vericlue.app.ui.screens.PhoneScreen
import vn.vericlue.app.ui.screens.RetryChallengeScreen
import vn.vericlue.app.ui.screens.RetryQualityScreen
import vn.vericlue.app.ui.screens.ReviewScreen
import vn.vericlue.app.ui.screens.SuccessScreen
import vn.vericlue.app.ui.screens.TermsScreen
import vn.vericlue.app.ui.screens.TurnHeadScreen
import vn.vericlue.app.ui.screens.VoiceScreen
import vn.vericlue.app.ui.theme.VcTheme

/**
 * Renders every screen to PNG on the JVM (no emulator). Run:
 *   ./gradlew recordPaparazziDebug
 * Images land in app/src/test/snapshots/images (not committed).
 */
class ScreensSnapshotTest {
    @get:Rule
    val paparazzi = Paparazzi(deviceConfig = DeviceConfig.PIXEL_5, maxPercentDifference = 0.1)

    private fun shot(name: String, dark: Boolean = false, content: @Composable () -> Unit) =
        paparazzi.snapshot(name) { VcTheme(dark = dark, motionEnabled = false) { content() } }

    private val n: () -> Unit = {}

    @Test fun polishDarkScreens() {
        shot("12_phone_dark", dark = true) { PhoneScreen(n) {} }
        shot("13_otp_dark", dark = true) { OtpScreen(n, n) }
        shot("14_id_front_dark", dark = true) { IdCaptureScreen(false, false, n, n) }
        shot("14_id_front_captured_dark", dark = true) { IdCaptureScreen(false, false, n, n, captured = true) }
        shot("15_id_review_dark", dark = true) { IdReviewScreen(n, n, n, n) }
        shot("16_confirm_after_face_dark", dark = true) { ConfirmInfoScreen(n, n, n, afterFace = true) }
        shot("42_success_dark", dark = true) { SuccessScreen(Purpose.Onboarding, n, auto = false) }
        shot("17_edit_dark", dark = true) { EditInfoScreen(n, {}, n) }
    }

    @Test fun start() {
        shot("00_bank_start") { BankStartScreen(n, n) }
        shot("01_auth") { AuthScreen(n, n, n) }
        shot("02_terms") { TermsScreen(n, n) }
        shot("02_terms_dark", dark = true) { TermsScreen(n, n) }
    }

    @Test fun identity() {
        shot("12_phone") { PhoneScreen(n) {} }
        shot("13_otp") { OtpScreen(n, n) }
        shot("13_otp_error") { OtpScreen(n, n, startWithError = true) }
        shot("13_otp_filled") { OtpScreen(n, n, sms = "Mã xác nhận VeriClue của bạn là 482910.", autoCode = "482910") }
        shot("14_id_front") { IdCaptureScreen(back = false, glare = false, onBack = n, onCapture = n) }
        shot("14_id_glare") { IdCaptureScreen(back = false, glare = true, onBack = n, onCapture = n) }
        shot("14_id_front_captured") { IdCaptureScreen(back = false, glare = false, onBack = n, onCapture = n, captured = true) }
        shot("15_id_back") { IdCaptureScreen(back = true, glare = false, onBack = n, onCapture = n) }
        shot("15_id_review") { IdReviewScreen(onBack = n, onRetakeFront = n, onRetakeBack = n, onContinue = n) }
        shot("16_confirm") { ConfirmInfoScreen(n, n, n) }
        shot("16_confirm_after_face") { ConfirmInfoScreen(n, n, n, afterFace = true) }
        shot("16_confirm_dark", dark = true) { ConfirmInfoScreen(n, n, n) }
        shot("17_edit") { EditInfoScreen(n, {}, n) }
    }

    @Test fun face() {
        shot("20_face_ready") { FaceReadyScreen(n, n, n) }
        shot("21_framing_low") { FramingScreen(n, n, FramingState.LowLight, auto = false) }
        shot("21_framing_far") { FramingScreen(n, n, FramingState.TooFar, auto = false) }
        shot("21_framing_ok") { FramingScreen(n, n, FramingState.Good, auto = false) }
        shot("22_hold_grey") { HoldStillScreen(n, n, startPhase = 0, auto = false) }
        shot("22_hold_flash") { HoldStillScreen(n, n, startPhase = 2, auto = false) }
        shot("22_hold_dot") { HoldStillScreen(n, n, startPhase = 5, auto = false) }
        shot("23_turn_left") { TurnHeadScreen(listOf(TurnDir.Left, TurnDir.Right), n, n, auto = false) }
    }

    @Test fun voiceAndResults() {
        shot("30_voice") { VoiceScreen(n, n) }
        shot("30_voice_recording") { VoiceScreen(n, n, startRecording = true) }
        shot("31_voice_again") { VoiceScreen(n, n, again = true) }
        shot("40_uploading") { Messages.Uploading(n, n, auto = false) }
        shot("41_checking") { CheckingScreen(Purpose.Onboarding, n, auto = false) }
        shot("42_success") { SuccessScreen(Purpose.Onboarding, n, auto = false) }
        shot("42_success_reauth") { SuccessScreen(Purpose.Reauth, n, auto = false) }
        shot("43_review") { ReviewScreen(n) }
        shot("43_review_dark", dark = true) { ReviewScreen(n) }
        shot("44_retry_quality") { RetryQualityScreen(n, n) }
        shot("45_retry_challenge") { RetryChallengeScreen(n, n) }
        shot("46_bank_opened") { BankOpenedScreen(n) }
    }

    @Test fun errors() {
        shot("50_camera") { Messages.CameraDenied(n, n) }
        shot("51_mic") { Messages.MicDenied(n, n) }
        shot("52_network") { Messages.Network(n, n) }
        shot("53_session") { Messages.SessionExpired(n) }
        shot("54_exit") { Messages.ExitConfirm(n, n) }
        shot("55_stopped") { Messages.Stopped(n) }
        shot("56_upload_failed") { Messages.UploadFailed(n, n) }
        shot("57_slow") { Messages.Slow(n, n) }
        shot("58_service") { Messages.ServiceDown(n) }
        shot("59_device") { Messages.DeviceNotReady(n, n, n) }
        shot("60_interrupted") { Messages.Interrupted(n, n) }
        shot("61_no_voice") { Messages.NoVoice(n, n) }
    }
}
