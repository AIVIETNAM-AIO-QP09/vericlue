package vn.vericlue.app.flow

import vn.vericlue.app.capture.CccdInfo
import vn.vericlue.app.data.api.IdCardFields

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
    /** Terms and per-item consent on one screen (short flow, 24/10). */
    const val Terms = "terms"

    const val Phone = "phone"
    const val Otp = "otp"
    const val OtpError = "otp_error"
    const val IdFront = "id_front"
    const val IdFrontGlare = "id_front_glare"
    const val IdBack = "id_back"

    /** One review of both ID photos, after the back side. */
    const val IdReview = "id_review"
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
    const val FlashSkipped = "flash_skipped"
    const val Deny = "deny"
    const val RecoveryRequired = "recovery_required"
}

object FlowRules {
    /** After OTP: re-auth skips the ID card (ADR-0013). */
    fun afterOtp(purpose: Purpose): String =
        if (purpose == Purpose.Reauth) Routes.FaceReady else Routes.IdFront

    /** After the head turn: re-auth has no voice step unless escalated (ADR-0013, L3). */
    fun afterTurnHead(purpose: Purpose): String =
        if (purpose == Purpose.Reauth) Routes.Checking else Routes.Voice

    /**
     * After the ID review: the face part, or straight back to the confirm screen when the face was
     * already captured (the user retook the card from the edit screen).
     */
    fun afterIdReview(faceCaptured: Boolean): String = if (faceCaptured) Routes.Confirm else Routes.FaceReady

    /**
     * After the face recording. The confirm screen comes here, not in stage A, so the user reads the
     * card while the video uploads. Re-auth has no card; a retry skips what was already confirmed.
     */
    fun afterFace(purpose: Purpose, idConfirmed: Boolean, live: Boolean): String = when {
        purpose != Purpose.Reauth && !idConfirmed -> Routes.Confirm
        live -> Routes.Uploading
        else -> afterTurnHead(purpose)
    }

    /** After the confirm screen: live sends the rest (finalize must come after the confirm, see can-chot.md H30). */
    fun afterConfirm(purpose: Purpose, live: Boolean): String = if (live) Routes.Uploading else afterTurnHead(purpose)

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
        // FLOW-01 purpose flows: a clear failure, and re-auth without a verified device.
        "deny" -> Routes.Deny
        "recovery_required" -> Routes.RecoveryRequired
        else -> null
    }

    /** The FLOW-01 `purpose` sent when a live session starts. */
    fun purposeCode(purpose: Purpose): String = when (purpose) {
        Purpose.Onboarding -> "onboarding"
        Purpose.Reauth -> "reauth"
        Purpose.Recovery -> "recovery"
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

    // --- Stage A in live mode (FLOW-02, FLOW-03) ---------------------------------------------

    fun otpWrongText(attemptsLeft: Int): String =
        if (attemptsLeft > 0) "Mã chưa đúng. Bạn còn $attemptsLeft lần thử." else "Bạn đã nhập sai quá số lần. Hãy bấm \"Gửi lại mã\"."

    /** Server codes the edit screen explains itself (FLOW-05 identity bridge); null = generic error screen. */
    fun confirmErrorText(code: String?): String? = when (code) {
        "identity_incomplete" -> "Vui lòng điền đủ họ tên, số CCCD 12 số, ngày sinh, giới tính và nơi thường trú."
        else -> null
    }

    /** Server codes the OTP screen explains itself; null = show the generic error screen. */
    fun otpErrorText(code: String?): String? = when (code) {
        "otp_expired" -> "Mã đã hết hạn. Hãy bấm \"Gửi lại mã\"."
        "otp_locked" -> "Bạn đã nhập sai quá số lần. Hãy bấm \"Gửi lại mã\"."
        else -> null
    }

    /** "1995-01-01" ↔ "01/01/1995" (server dates vs what the screens show). */
    fun isoToDisplay(iso: String?): String =
        iso?.split("-")?.takeIf { it.size == 3 }?.let { (y, m, d) -> "$d/$m/$y" } ?: iso.orEmpty()

    fun displayToIso(shown: String): String? =
        shown.trim().split("/").takeIf { it.size == 3 && it.all { p -> p.all(Char::isDigit) } }
            ?.let { (d, m, y) -> "${y.padStart(4, '0')}-${m.padStart(2, '0')}-${d.padStart(2, '0')}" }

    fun cccdFrom(f: IdCardFields): CccdInfo = f.let {
        CccdInfo(
            idNumber = f.idNumber.orEmpty(),
            fullName = f.fullName.orEmpty(),
            dateOfBirth = isoToDisplay(f.dateOfBirth),
            gender = f.sex.orEmpty(),
            address = f.address.orEmpty(),
            issueDate = f.issuedOn?.let(::isoToDisplay),
        )
    }

    /**
     * What the user confirmed, as server fields. [shown] and [edited] follow the edit screen's rows
     * (name, ID number, date of birth, sex, address); a row left as shown keeps the server's value,
     * so only real edits differ from the QR. An edit the server cannot take (bad date, sex other
     * than Nam/Nữ) keeps the QR value.
     */
    fun confirmedFields(server: IdCardFields, shown: List<String>, edited: List<String>): IdCardFields {
        fun changed(i: Int) = edited.getOrNull(i)?.let { it != shown.getOrNull(i)?.trim() } == true
        return server.copy(
            fullName = if (changed(0)) edited[0] else server.fullName,
            idNumber = if (changed(1)) edited[1].filterNot(Char::isWhitespace) else server.idNumber,
            dateOfBirth = if (changed(2)) displayToIso(edited[2]) ?: server.dateOfBirth else server.dateOfBirth,
            sex = if (changed(3) && edited[3] in setOf("Nam", "Nữ")) edited[3] else server.sex,
            address = if (changed(4)) edited[4] else server.address,
        )
    }

    fun validIdentityValues(values: List<String>): Boolean {
        if (values.size != 5 || values.any { it.isBlank() }) return false
        if (!Regex("[0-9]{12}").matches(values[1].filterNot(Char::isWhitespace))) return false
        if (values[3].trim() !in setOf("Nam", "Nữ")) return false
        val iso = displayToIso(values[2]) ?: return false
        return runCatching { java.time.LocalDate.parse(iso) }.isSuccess
    }

    /**
     * "Thử lại" / "Tiếp tục chờ" after a network error or a slow answer. A live run sends again
     * (only the steps the server has not received); only the demo goes through the scripted check.
     */
    fun afterNetworkRetry(live: Boolean): String = if (live) Routes.Uploading else Routes.Checking

    /** "Tiếp tục" in the exit dialog redoes the face part only when it was opened during stage B or C. */
    fun resumeRedoesFace(previousRoute: String?): Boolean = previousRoute?.let(::stepOf) in setOf(2, 3)

    /**
     * What the success screen may tick in a live run: only what the server has checked. The ID card
     * is not sent yet (FLOW-03), and a pass straight from finalize skips the voice.
     */
    fun checkedByServer(voiceChecked: Boolean): List<String> =
        if (voiceChecked) listOf("Khuôn mặt", "Giọng nói") else listOf("Khuôn mặt")

    fun stepOf(route: String): Int? = when (route) {
        Routes.Phone, Routes.Otp, Routes.OtpError,
        Routes.IdFront, Routes.IdFrontGlare, Routes.IdBack, Routes.IdReview,
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

    /** The 6-digit code in an SMS text (simulated SMS, or one read with the user's consent). */
    fun codeIn(text: String?): String? =
        text?.let { Regex("(?<!\\d)\\d{$LENGTH}(?!\\d)").find(it)?.value }
}

/**
 * Terms must be scrolled to the end before the box can be ticked. Immutable so it can sit in
 * a single Compose state: every change recomposes the button too.
 */
data class Agreement(val readToEnd: Boolean = false, val accepted: Boolean = false) {
    fun reachedEnd(): Agreement = copy(readToEnd = true)

    fun toggle(): Agreement = if (readToEnd) copy(accepted = !accepted) else this

    val canContinue: Boolean get() = readToEnd && accepted

    /** Terms and consent share one screen: the button also needs every required consent item. */
    fun canContinueWith(consented: Set<Int>, required: Set<Int>): Boolean = canContinue && consented.containsAll(required)
}
