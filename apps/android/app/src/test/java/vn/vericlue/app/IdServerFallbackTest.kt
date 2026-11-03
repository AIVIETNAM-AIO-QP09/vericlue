package vn.vericlue.app

import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test
import vn.vericlue.app.capture.*

class IdServerFallbackTest {
    private val qr = "001095012345||Test Person|01011995|Nam|Test Address|15072021"
    private val clear = IdQuality(500.0, 0.0, null, frameTimeNs = 1)

    @Test fun qrCandidateWithoutPortraitCanTriggerStillButNeverOfflineConfirmation() {
        val candidate = clear.copy(qrCandidatePresent = true)
        val auto = IdAutoCapture()
        assertFalse(auto.offer(candidate))
        assertFalse(auto.offer(candidate)) // stale frame is not another observation
        assertTrue(auto.offer(candidate.copy(frameTimeNs = 2)))
        assertTrue(idCaptureCanSubmit(candidate, serverAvailable = true))
        assertFalse(idCaptureCanSubmit(candidate, serverAvailable = false))
        assertFalse(idCaptureUsable(candidate, false, false))
    }

    @Test fun serverMayRecoverEitherMissingExtractionFromAFreshClearStill() {
        val portrait = clear.copy(portraitPresent = true, portraitCount = 1)
        val qrOnly = clear.copy(qr = qr)
        listOf(portrait, qrOnly).forEach {
            assertTrue(idCaptureCanSubmit(it, true))
            assertFalse(idCaptureCanSubmit(it, false))
        }
    }

    @Test fun backgroundRetainedQrPoorQualityAndAmbiguousCardsNeverSubmit() {
        val candidate = clear.copy(qrCandidatePresent = true)
        listOf(clear, clear.copy(qrRecentlySeen = true), candidate.copy(sharpness = 0.0),
            candidate.copy(glareFraction = 0.5, portraitPresent = true, portraitCount = 1), candidate.copy(brightness = 20.0),
            candidate.copy(qrConflicting = true), candidate.copy(portraitCount = 2)).forEach {
            assertFalse(idCaptureCanSubmit(it, true))
        }
        val auto = IdAutoCapture()
        repeat(6) { assertFalse(auto.offer(candidate.copy(qrConflicting = true, frameTimeNs = it + 1L))) }
    }

    @Test fun whiteCardBackgroundCannotVetoServerPortraitRecovery() {
        val whiteCard = clear.copy(qr = qr, glareFraction = 0.5)
        assertTrue(idCaptureCanSubmit(whiteCard, true))
        assertFalse(idCaptureCanSubmit(whiteCard, false))
        assertFalse(idCaptureCanSubmit(whiteCard.copy(portraitPresent = true, portraitCount = 1), true))
    }

    @Test fun conflictingDecodedCardsAreNotDisguisedAsAnUndecodedCandidate() {
        assertFalse(conflictingCardQr(listOf(qr, qr)))
        assertTrue(conflictingCardQr(listOf(qr, qr.replace("001095012345", "001095012346"))))
    }
}
