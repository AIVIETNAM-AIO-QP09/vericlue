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
}
