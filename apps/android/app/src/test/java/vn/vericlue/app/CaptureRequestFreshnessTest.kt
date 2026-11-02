package vn.vericlue.app

import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test
import vn.vericlue.app.capture.FaceSignal
import vn.vericlue.app.capture.QualityGate

class CaptureRequestFreshnessTest {
    private fun signal(capturedMs: Long, deliveredMs: Long) =
        FaceSignal(1, .45f, .5f, .45f, 0f, 120f, capturedMs * 1_000_000L,
            observedAtMs = deliveredMs)

    private fun freshForRequest(face: FaceSignal, nowMs: Long, requestMs: Long): Boolean =
        QualityGate.isFresh(face, nowMs, capturedAfterMs = requestMs)

    @Test fun preRequestCaptureDeliveredAfterRequestCannotSupplyJpeg() {
        val buffered = signal(capturedMs = 950L, deliveredMs = 1050L)
        assertTrue(QualityGate.isFresh(buffered, 1100L))
        assertFalse(freshForRequest(buffered, 1100L, requestMs = 1000L))
    }

    @Test fun captureAtOrAfterRequestMustStillBeFreshOnBothClocks() {
        assertTrue(freshForRequest(signal(1000L, 1050L), 1100L, requestMs = 1000L))
        assertTrue(freshForRequest(signal(1020L, 1050L), 1100L, requestMs = 1000L))
        assertFalse(freshForRequest(signal(1000L, 1590L), 1600L, requestMs = 1000L))
        assertFalse(freshForRequest(signal(1200L, 1050L), 1100L, requestMs = 1000L))
    }
}
