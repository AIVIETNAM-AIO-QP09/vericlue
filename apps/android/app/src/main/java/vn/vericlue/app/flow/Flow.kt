package vn.vericlue.app.flow

/**
 * Flow rules for the UI-only build. Pure Kotlin so it can be unit-tested.
 * There is no camera or API yet (APP-01..04): results come from [DemoOutcome].
 */

/** The three eKYC flows (ADR-0013). Recovery is UI-only for now (ADR-0014, 21/10 update). */
enum class Purpose { Onboarding, Reauth, Recovery }

enum class TurnDir { Left, Right }

/**
 * What the fake server answers after the checking screen. Mirrors the citizen-facing
 * statuses in packages/contracts (pass | retry | review | voice_challenge). Never a score.
 */
enum class DemoOutcome(val label: String) {
    Pass("Đạt"),
    Review("Chờ duyệt"),
    RetryQuality("Chụp lại (chất lượng)"),
    RetryChallenge("Làm lại thử thách"),
    VoiceAgain("Đọc lại câu"),
}

object Routes {
    const val BankStart = "bank_start"
    const val BankOpened = "bank_opened"
    const val Gallery = "gallery"

    const val Splash = "splash"
    const val Auth = "auth"
    const val Terms = "terms"
    const val Consent = "consent"

    const val Intro = "intro"
    const val Permission = "permission"
    const val Phone = "phone"
    const val Otp = "otp"
    const val OtpError = "otp_error"
    const val IdFront = "id_front"
    const val IdFrontGlare = "id_front_glare"
    const val IdBack = "id_back"
    const val Confirm = "confirm"
    const val EditInfo = "edit_info"

    const val FaceReady = "face_ready"
    const val Framing = "framing"
    const val HoldStill = "hold_still"
    const val TurnHead = "turn_head"

    const val Voice = "voice"
    const val VoiceAgain = "voice_again"

    const val Uploading = "uploading"
    const val UploadFailed = "upload_failed"
    const val Checking = "checking"
    const val Slow = "slow"
    const val Success = "success"
    const val Review = "review"
    const val RetryQuality = "retry_quality"
    const val RetryChallenge = "retry_challenge"

    const val ErrorCamera = "error_camera"
    const val ErrorMic = "error_mic"
    const val ErrorNetwork = "error_network"
    const val ErrorSession = "error_session"
    const val ErrorService = "error_service"
    const val ErrorDevice = "error_device"
    const val Interrupted = "interrupted"
    const val NoVoice = "no_voice"
    const val ExitConfirm = "exit_confirm"
    const val Stopped = "stopped"
}

object FlowRules {
    /** After OTP: re-auth skips the ID card (ADR-0013). */
    fun afterOtp(purpose: Purpose): String =
        if (purpose == Purpose.Reauth) Routes.FaceReady else Routes.IdFront

    /** After the head turn: re-auth has no voice step unless escalated (ADR-0013, L3). */
    fun afterTurnHead(purpose: Purpose): String =
        if (purpose == Purpose.Reauth) Routes.Checking else Routes.Voice

    fun afterChecking(outcome: DemoOutcome): String = when (outcome) {
        DemoOutcome.Pass -> Routes.Success
        DemoOutcome.Review -> Routes.Review
        DemoOutcome.RetryQuality -> Routes.RetryQuality
        DemoOutcome.RetryChallenge -> Routes.RetryChallenge
        DemoOutcome.VoiceAgain -> Routes.VoiceAgain
    }

    fun stepOf(route: String): Int? = when (route) {
        Routes.Intro, Routes.Permission, Routes.Phone, Routes.Otp, Routes.OtpError,
        Routes.IdFront, Routes.IdFrontGlare, Routes.IdBack, Routes.Confirm, Routes.EditInfo -> 1
        Routes.FaceReady, Routes.Framing, Routes.HoldStill, Routes.TurnHead,
        Routes.RetryQuality, Routes.RetryChallenge -> 2
        Routes.Voice, Routes.VoiceAgain -> 3
        else -> null
    }
}

object PhoneRules {
    const val LENGTH = 10

    fun append(current: String, digit: Char): String =
        if (digit.isDigit() && current.length < LENGTH) current + digit else current

    fun isValid(phone: String): Boolean = phone.length == LENGTH && phone.startsWith("0")

    /** "0900000000" -> "0900 000 000". */
    fun format(phone: String): String = buildString {
        phone.forEachIndexed { i, ch ->
            if (i == 4 || i == 7) append(' ')
            append(ch)
        }
    }
}

object OtpRules {
    const val LENGTH = 6

    fun append(current: String, digit: Char): String =
        if (digit.isDigit() && current.length < LENGTH) current + digit else current

    fun isComplete(code: String): Boolean = code.length == LENGTH
}

/** Terms must be scrolled to the end before the box can be ticked. */
class AgreementGate {
    var readToEnd: Boolean = false
        private set
    var accepted: Boolean = false
        private set

    fun reachedEnd() {
        readToEnd = true
    }

    fun toggle() {
        if (readToEnd) accepted = !accepted
    }

    val canContinue: Boolean get() = readToEnd && accepted
}
