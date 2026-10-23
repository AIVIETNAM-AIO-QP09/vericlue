package vn.vericlue.app.flow

/**
 * Flow rules for the UI-only build. Pure Kotlin so it can be unit-tested.
 * There is no camera or API yet (APP-01..04): results come from [DemoOutcome].
 */

/** The three eKYC flows (ADR-0013). Recovery is UI-only for now (ADR-0014, 21/10 update). */
enum class Purpose { Onboarding, Reauth, Recovery }

enum class TurnDir { Left, Right }

/** One quality hint on the framing screen (ADR-0017 §1: one sentence about quality). */
enum class FramingState { NoFace, LowLight, TooFar, OffCenter, Good }

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
    const val IdFrontReview = "id_front_review"
    const val IdBack = "id_back"
    const val IdBackReview = "id_back_review"
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

    /**
     * Server status → next screen. Only "pass" leads to success; an unknown status returns null,
     * which the caller must treat as an error (AGENTS.md §6 rule 4).
     */
    fun routeForStatus(status: String, retryHint: String?, inVoiceStep: Boolean): String? = when (status) {
        "pass" -> Routes.Success
        "review" -> Routes.Review
        "retry" -> if (retryHint != null) Routes.RetryQuality else Routes.RetryChallenge
        "voice_challenge" -> if (inVoiceStep) Routes.VoiceAgain else Routes.Voice
        else -> null
    }

    /** Quality hints from the server, same wording as the web (apps/web/src/i18n/vi.ts). */
    fun retryHintText(hint: String?): String = when (hint) {
        "MORE_LIGHT" -> "Ra chỗ sáng hơn"
        "MOVE_CLOSER" -> "Lại gần hơn"
        "MOVE_BACK" -> "Lùi ra xa hơn một chút"
        "FACE_CENTER" -> "Đưa khuôn mặt vào giữa khung hình"
        "HOLD_STILL" -> "Giữ yên điện thoại và khuôn mặt"
        "QUIET_PLACE" -> "Chuyển đến nơi yên tĩnh hơn"
        "BRIGHTNESS_UP" -> "Tăng độ sáng màn hình"
        else -> "Hãy ra chỗ sáng hơn và giữ điện thoại ngang tầm mặt."
    }

    /**
     * Screens where the front camera (or mic) is running. Leaving the app here interrupts the
     * attempt: its face data is dropped and the face part restarts (ADR-0017 §2).
     */
    val capturingRoutes = setOf(Routes.Framing, Routes.HoldStill, Routes.TurnHead, Routes.Voice, Routes.VoiceAgain)

    fun isInterruptedBy(route: String?): Boolean = route in capturingRoutes

    fun stepOf(route: String): Int? = when (route) {
        Routes.Intro, Routes.Permission, Routes.Phone, Routes.Otp, Routes.OtpError,
        Routes.IdFront, Routes.IdFrontGlare, Routes.IdFrontReview, Routes.IdBack, Routes.IdBackReview,
        Routes.Confirm, Routes.EditInfo -> 1
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

/**
 * Terms must be scrolled to the end before the box can be ticked. Immutable so it can sit in
 * a single Compose state: every change recomposes the button too.
 */
data class Agreement(val readToEnd: Boolean = false, val accepted: Boolean = false) {
    fun reachedEnd(): Agreement = copy(readToEnd = true)

    fun toggle(): Agreement = if (readToEnd) copy(accepted = !accepted) else this

    val canContinue: Boolean get() = readToEnd && accepted
}
