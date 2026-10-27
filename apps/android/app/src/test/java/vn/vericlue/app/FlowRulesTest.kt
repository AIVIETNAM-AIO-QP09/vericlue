package vn.vericlue.app

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test
import vn.vericlue.app.flow.Agreement
import vn.vericlue.app.flow.DemoOutcome
import vn.vericlue.app.flow.FlowRules
import vn.vericlue.app.flow.OtpRules
import vn.vericlue.app.flow.PhoneRules
import vn.vericlue.app.flow.Purpose
import vn.vericlue.app.flow.Routes

class FlowRulesTest {
    @Test
    fun cardQrFallsBackToTheFront() {
        assertEquals("front", FlowRules.cardQr("front", null))
    }

    @Test
    fun cardQrUsesTheBackWhenItIsTheOnlyCode() {
        assertEquals("back", FlowRules.cardQr(null, "back"))
    }

    @Test
    fun cardQrPrefersTheBackWhenBothSidesHaveCodes() {
        assertEquals("back", FlowRules.cardQr("front", "back"))
    }

    @Test
    fun cardQrIsAbsentWhenNeitherSideHasACode() {
        assertEquals(null, FlowRules.cardQr(null, null))
        assertEquals(null, FlowRules.cardQr(" ", ""))
        assertEquals("front", FlowRules.cardQr("front", " "))
    }

    @Test
    fun retakenCardSideDoesNotKeepItsOldQr() {
        assertEquals("old-back", FlowRules.cardQr("front", "old-back"))
        assertEquals("front", FlowRules.cardQr("front", null))
        assertEquals(null, FlowRules.cardQr(null, null))
    }

    @Test
    fun reauthSkipsIdCardAndVoice() {
        assertEquals(Routes.FaceReady, FlowRules.afterOtp(Purpose.Reauth))
        assertEquals(Routes.Checking, FlowRules.afterTurnHead(Purpose.Reauth))
        assertEquals(Routes.IdFront, FlowRules.afterOtp(Purpose.Onboarding))
        assertEquals(Routes.Voice, FlowRules.afterTurnHead(Purpose.Onboarding))
    }

    @Test
    fun confirmComesAfterTheFaceAndOnlyOnce() {
        assertEquals(Routes.FaceReady, FlowRules.afterIdReview(faceCaptured = false))
        assertEquals(Routes.Confirm, FlowRules.afterIdReview(faceCaptured = true))
        assertEquals(Routes.Confirm, FlowRules.afterFace(Purpose.Onboarding, idConfirmed = false, live = true))
        assertEquals(Routes.Confirm, FlowRules.afterFace(Purpose.Recovery, idConfirmed = false, live = false))
        // A retry after the confirm goes straight on; re-auth has no card to confirm.
        assertEquals(Routes.Uploading, FlowRules.afterFace(Purpose.Onboarding, idConfirmed = true, live = true))
        assertEquals(Routes.Voice, FlowRules.afterFace(Purpose.Onboarding, idConfirmed = true, live = false))
        assertEquals(Routes.Uploading, FlowRules.afterFace(Purpose.Reauth, idConfirmed = false, live = true))
        assertEquals(Routes.Checking, FlowRules.afterFace(Purpose.Reauth, idConfirmed = false, live = false))
        assertEquals(Routes.Uploading, FlowRules.afterConfirm(Purpose.Onboarding, live = true))
        assertEquals(Routes.Voice, FlowRules.afterConfirm(Purpose.Onboarding, live = false))
    }

    @Test
    fun everyOutcomeHasAScreen() {
        val routes = DemoOutcome.entries.map(FlowRules::afterChecking)
        assertEquals(DemoOutcome.entries.size, routes.toSet().size)
    }

    @Test
    fun stepsFollowTheThreeStages() {
        assertEquals(1, FlowRules.stepOf(Routes.Otp))
        assertEquals(2, FlowRules.stepOf(Routes.HoldStill))
        assertEquals(3, FlowRules.stepOf(Routes.Voice))
        assertEquals(null, FlowRules.stepOf(Routes.Success))
    }

    @Test
    fun phoneInputIsDigitsOnlyAndCapped() {
        var p = ""
        "09a0000000099".forEach { p = PhoneRules.append(p, it) }
        assertEquals("0900000000", p)
        assertTrue(PhoneRules.isValid(p))
        assertFalse(PhoneRules.isValid("1900000000"))
        assertEquals("0900 000 000", PhoneRules.format(p))
    }

    @Test
    fun otpCompletesAtSixDigits() {
        var code = ""
        "1234567".forEach { code = OtpRules.append(code, it) }
        assertEquals("123456", code)
        assertTrue(OtpRules.isComplete(code))
    }

    @Test
    fun missingIdentityFieldsAreExplainedOtherErrorsAreNot() {
        assertTrue(FlowRules.confirmErrorText("identity_incomplete")!!.contains("số CCCD"))
        assertEquals(null, FlowRules.confirmErrorText("step_not_allowed"))
        assertEquals(null, FlowRules.confirmErrorText(null))
    }

    @Test
    fun otpCodeIsReadFromTheSmsText() {
        assertEquals("482910", OtpRules.codeIn("Mã xác nhận VeriClue của bạn là 482910. Không chia sẻ mã này."))
        assertEquals("000123", OtpRules.codeIn("<#> 000123 là mã của bạn"))
        assertEquals(null, OtpRules.codeIn("Gọi 19001234567 để được hỗ trợ")) // 11 digits: not a code
        assertEquals(null, OtpRules.codeIn("Mã 4829"))
        assertEquals(null, OtpRules.codeIn(null))
    }

    @Test
    fun termsCannotBeAcceptedBeforeReadingToTheEnd() {
        var a = Agreement().toggle()
        assertFalse(a.accepted)
        assertFalse(a.canContinue)
        a = a.reachedEnd().toggle()
        assertTrue(a.canContinue)
        assertFalse(a.toggle().canContinue)
    }

    @Test
    fun termsAndConsentShareOneButton() {
        val read = Agreement().reachedEnd().toggle()
        assertFalse(read.canContinueWith(consented = emptySet(), required = setOf(0)))
        assertFalse(read.canContinueWith(consented = setOf(1, 2), required = setOf(0)))
        assertTrue(read.canContinueWith(consented = setOf(0), required = setOf(0)))
        assertFalse(Agreement().canContinueWith(consented = setOf(0), required = setOf(0)))
    }

    @Test
    fun liveRetryResendsInsteadOfTheScriptedCheck() {
        assertEquals(Routes.Uploading, FlowRules.afterNetworkRetry(live = true))
        assertEquals(Routes.Checking, FlowRules.afterNetworkRetry(live = false))
    }

    @Test
    fun exitDialogRedoesFaceOnlyFromStageBOrC() {
        assertTrue(FlowRules.resumeRedoesFace(Routes.HoldStill))
        assertTrue(FlowRules.resumeRedoesFace(Routes.Voice))
        assertFalse(FlowRules.resumeRedoesFace(Routes.Uploading))
        assertFalse(FlowRules.resumeRedoesFace(Routes.IdFront))
        assertFalse(FlowRules.resumeRedoesFace(null))
    }

    @Test
    fun successTicksOnlyWhatTheServerChecked() {
        assertEquals(listOf("Khuôn mặt"), FlowRules.checkedByServer(voiceChecked = false))
        assertEquals(listOf("Khuôn mặt", "Giọng nói"), FlowRules.checkedByServer(voiceChecked = true))
    }
}
