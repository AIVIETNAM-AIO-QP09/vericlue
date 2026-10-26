package vn.vericlue.app

import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test
import vn.vericlue.app.flow.Routes
import vn.vericlue.app.ui.theme.VcMotion

class MotionPolicyTest {
    @Test fun cameraRoutesNeverSlideOrFadeInEitherDirection() {
        val motion = VcMotion(enabled = true)
        listOf(Routes.IdFront, Routes.IdFrontGlare, Routes.IdBack, Routes.Framing,
            Routes.HoldStill, Routes.TurnHead, Routes.Voice, Routes.VoiceAgain).forEach { route ->
            assertFalse(motion.screenTransition(Routes.Phone, route))
            assertFalse(motion.screenTransition(route, Routes.Success))
        }
        assertTrue(motion.screenTransition(Routes.Phone, Routes.Otp))
        assertTrue(motion.screenTransition(Routes.Success, Routes.BankOpened))
    }

    @Test fun reducedMotionDisablesNavigationAndStaggeredFeedback() {
        val motion = VcMotion(enabled = false)
        assertFalse(motion.screenTransition(Routes.Phone, Routes.Otp))
        assertTrue(motion.duration(250) == 0)
        assertTrue(motion.stagger(5) == 0)
    }
}
