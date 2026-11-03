package vn.vericlue.app

import java.io.ByteArrayInputStream
import org.junit.Assert.assertArrayEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test
import vn.vericlue.app.capture.DocumentCaptureAttempt
import vn.vericlue.app.capture.DocumentImageLimits

class DocumentCaptureTest {
    @Test fun repeatedTapsAndDuplicateResultsCannotStartMultipleUploads() {
        val gate = DocumentCaptureAttempt()
        val ticket = gate.begin()!!
        assertNull(gate.begin())
        assertNull(gate.result())
        assertTrue(gate.opened(ticket))
        assertFalse(gate.opened(ticket))
        assertTrue(gate.result() == ticket)
        assertNull(gate.result())
        assertNull(gate.begin())
        gate.finish(ticket)
        assertFalse(gate.current(ticket))
        assertNull(gate.begin())
    }

    @Test fun leavingInvalidatesDelayedScannerAndUploadCallbacks() {
        for (opened in listOf(false, true)) {
            val gate = DocumentCaptureAttempt()
            val ticket = gate.begin()!!
            if (opened) gate.opened(ticket)
            gate.close()
            assertFalse(gate.opened(ticket))
            assertFalse(gate.current(ticket))
            assertNull(gate.result())
            gate.retry(ticket)
            assertNull(gate.begin())
        }
    }

    @Test fun cancelledOrFailedScanCanRetryWithoutRevivingThePreviousAttempt() {
        val gate = DocumentCaptureAttempt()
        val first = gate.begin()!!
        gate.opened(first)
        gate.result()
        gate.retry(first)
        val second = gate.begin()!!
        assertFalse(gate.opened(first))
        gate.retry(first)
        assertTrue(gate.opened(second))
        assertTrue(gate.result() == second)
    }

    @Test fun pixelLimitUsesLongMathAndDoesNotRejectNormalCameraPhotos() {
        assertTrue(DocumentImageLimits.dimensionsAllowed(4000, 3000))
        assertTrue(DocumentImageLimits.dimensionsAllowed(4000, 4000))
        assertFalse(DocumentImageLimits.dimensionsAllowed(8000, 6000))
        assertFalse(DocumentImageLimits.dimensionsAllowed(65536, 65536))
        assertFalse(DocumentImageLimits.dimensionsAllowed(0, 100))
    }

    @Test fun boundedReadPreservesAllOriginalBytesAtTheLimit() {
        val bytes = ByteArray(20) { it.toByte() }
        assertArrayEquals(bytes, DocumentImageLimits.readBounded(ByteArrayInputStream(bytes), 20))
    }

    @Test(expected = IllegalArgumentException::class)
    fun oversizedImageIsRejectedBeforeUploading() {
        DocumentImageLimits.readBounded(ByteArrayInputStream(ByteArray(21)), 20)
    }

    @Test(expected = IllegalArgumentException::class)
    fun emptyImageIsRejectedBeforeUploading() {
        DocumentImageLimits.readBounded(ByteArrayInputStream(byteArrayOf()), 20)
    }
}
