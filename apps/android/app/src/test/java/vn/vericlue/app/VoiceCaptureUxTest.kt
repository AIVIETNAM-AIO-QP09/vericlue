package vn.vericlue.app

import org.junit.Assert.*
import org.junit.Test
import vn.vericlue.app.capture.VoiceCaptureFailure
import vn.vericlue.app.flow.FlowRules
import vn.vericlue.app.flow.Routes

class VoiceCaptureUxTest {
    @Test fun nativeLimitHasItsOwnLocalRetryRouteRegardlessOfPermissions() {
        for (camera in listOf(false, true)) for (mic in listOf(false, true)) {
            assertEquals(Routes.VoiceTimeLimit, FlowRules.voiceCaptureFailureRoute(
                VoiceCaptureFailure.DurationLimit, camera, mic))
        }
    }

    @Test fun localRetryKeepsTheCurrentServerReadingInsteadOfReturningToTheFirstRoute() {
        assertEquals(Routes.Voice, FlowRules.voiceLocalRetryRoute(again = false))
        assertEquals(Routes.VoiceAgain, FlowRules.voiceLocalRetryRoute(again = true))
    }

    @Test fun nativePreparationTimeIsDeductedFromTheDisplayedBudget() {
        assertEquals(7_000L, FlowRules.voiceRemainingMs(recordedDurationMs = 3_000, limitMs = 10_000))
        assertEquals(1L, FlowRules.voiceRemainingMs(recordedDurationMs = 9_999, limitMs = 10_000))
    }

    @Test fun remainingTimeClampsInvalidOrFinalizedElapsedValuesWithoutOverflow() {
        assertEquals(10_000L, FlowRules.voiceRemainingMs(-1, 10_000))
        assertEquals(10_000L, FlowRules.voiceRemainingMs(0, 10_000))
        assertEquals(0L, FlowRules.voiceRemainingMs(10_000, 10_000))
        assertEquals(0L, FlowRules.voiceRemainingMs(Long.MAX_VALUE, 10_000))
    }

    @Test fun bothReadingRoutesStillInterruptOnBackgroundButAnEndedCaptureDoesNot() {
        assertTrue(FlowRules.isInterruptedBy(FlowRules.voiceLocalRetryRoute(false)))
        assertTrue(FlowRules.isInterruptedBy(FlowRules.voiceLocalRetryRoute(true)))
        assertFalse(FlowRules.isInterruptedBy(Routes.VoiceTimeLimit))
    }
}
