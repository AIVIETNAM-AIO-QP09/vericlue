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
    fun reauthSkipsIdCardAndVoice() {
        assertEquals(Routes.FaceReady, FlowRules.afterOtp(Purpose.Reauth))
        assertEquals(Routes.Checking, FlowRules.afterTurnHead(Purpose.Reauth))
        assertEquals(Routes.IdFront, FlowRules.afterOtp(Purpose.Onboarding))
        assertEquals(Routes.Voice, FlowRules.afterTurnHead(Purpose.Onboarding))
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
    fun termsCannotBeAcceptedBeforeReadingToTheEnd() {
        var a = Agreement().toggle()
        assertFalse(a.accepted)
        assertFalse(a.canContinue)
        a = a.reachedEnd().toggle()
        assertTrue(a.canContinue)
        assertFalse(a.toggle().canContinue)
    }
}
