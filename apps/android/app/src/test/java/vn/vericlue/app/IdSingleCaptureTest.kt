package vn.vericlue.app

import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test
import vn.vericlue.app.capture.IdAutoCapture
import vn.vericlue.app.capture.IdQuality
import vn.vericlue.app.capture.idCaptureUsable

class IdSingleCaptureTest {
    private val qr = "001095012345|123456789|Nguyễn Văn A|01011995|Nam|Hà Nội|15072021"
    private val full = IdQuality(500.0, 0.0, qr, portraitPresent = true, frameTimeNs = 1)

    @Test fun portraitAloneCannotCompleteEvenWithManualCaptureOrRetainedQr() {
        val portraitOnly = full.copy(qr = null, qrRecentlySeen = true)
        assertFalse(idCaptureUsable(portraitOnly, back = false, manual = true))
        val auto = IdAutoCapture()
        assertFalse(auto.offer(portraitOnly))
        assertFalse(auto.offer(portraitOnly.copy(frameTimeNs = 2)))
    }

    @Test fun qrAloneCannotCompleteEvenThroughTheOldBackMode() {
        val qrOnly = full.copy(portraitPresent = false)
        assertFalse(idCaptureUsable(qrOnly, back = true, manual = true))
        val auto = IdAutoCapture(back = true)
        assertFalse(auto.offer(qrOnly))
        assertFalse(auto.offer(qrOnly.copy(frameTimeNs = 2)))
    }

    @Test fun changedCardOrMissingEvidenceBreaksTheAutomaticRun() {
        val auto = IdAutoCapture()
        assertFalse(auto.offer(full))
        val another = full.copy(qr = qr.replace("001095012345", "001095012346"), frameTimeNs = 2)
        assertFalse(auto.offer(another))
        assertFalse(auto.offer(another.copy(qr = null, frameTimeNs = 3)))
        assertFalse(auto.offer(another.copy(frameTimeNs = 4)))
        assertTrue(auto.offer(another.copy(frameTimeNs = 5)))
    }

    @Test fun aFreshCompleteStillCanCompleteButAnOldLiveQrCannot() {
        assertTrue(idCaptureUsable(full, back = false, manual = false))
        assertFalse(idCaptureUsable(full.copy(qr = null), back = false, manual = false))
    }

    @Test fun observationsFromBeforeAPauseCannotCompleteANewRun() {
        val auto = IdAutoCapture()
        assertFalse(auto.offer(full))
        assertFalse(auto.offer(full.copy(frameTimeNs = 2_000_000_001)))
        assertTrue(auto.offer(full.copy(frameTimeNs = 2_000_000_002)))
    }

    @Test fun anUndecodedRegionMayRequestAStillButCannotApproveIt() {
        val candidate = full.copy(qr = null, qrCandidatePresent = true)
        val auto = IdAutoCapture()
        assertFalse(auto.offer(candidate))
        assertTrue(auto.offer(candidate.copy(frameTimeNs = 2)))
        assertFalse(idCaptureUsable(candidate, back = false, manual = false))
        assertFalse(idCaptureUsable(candidate, back = false, manual = true))
    }

    @Test fun readableTiltedPreviewCanRequestAStillWithoutAnAngleVeto() {
        val tilted = full.copy(tilted = true)
        val auto = IdAutoCapture()
        assertFalse(auto.offer(tilted))
        assertTrue(auto.offer(tilted.copy(frameTimeNs = 2)))
        assertTrue(idCaptureUsable(tilted, back = false, manual = false))
    }

    @Test fun coarsePreviewQualityCannotPreventCheckingAHigherResolutionStill() {
        val preview = full.copy(sharpness = 10.0, glareFraction = 0.5, brightness = 30.0)
        val auto = IdAutoCapture()
        assertFalse(auto.offer(preview))
        assertTrue(auto.offer(preview.copy(frameTimeNs = 2)))
        assertFalse(idCaptureUsable(preview, back = false, manual = false))
    }

    @Test fun fourStableClearPortraitFramesCanProbeAStillWhenQrHasNoCandidate() {
        val portraitOnly = full.copy(qr = null)
        val auto = IdAutoCapture()
        assertFalse(auto.offer(portraitOnly))
        assertFalse(auto.offer(portraitOnly.copy(frameTimeNs = 250_000_001)))
        assertFalse(auto.offer(portraitOnly.copy(frameTimeNs = 500_000_001)))
        assertTrue(auto.offer(portraitOnly.copy(frameTimeNs = 750_000_001)))
        assertFalse(idCaptureUsable(portraitOnly, back = false, manual = false))
    }

    @Test fun exploratoryStillRequiresClearPortraitWhenThereIsNoQrEvidence() {
        val blurred = full.copy(qr = null, sharpness = 1.0)
        val auto = IdAutoCapture()
        repeat(6) { assertFalse(auto.offer(blurred.copy(frameTimeNs = it * 250_000_000L + 1))) }
    }
}
