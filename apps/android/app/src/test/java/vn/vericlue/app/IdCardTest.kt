package vn.vericlue.app

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test
import vn.vericlue.app.capture.CardText
import vn.vericlue.app.capture.CccdQr
import vn.vericlue.app.capture.IdAutoCapture
import vn.vericlue.app.capture.IdQuality
import vn.vericlue.app.capture.ImageChecks
import vn.vericlue.app.capture.idCaptureUsable
import vn.vericlue.app.ui.screens.idRetakeHint

class IdCardTest {
    // Made-up values in the CCCD QR layout; not a real person.
    private val qr = "001095012345|123456789|Nguyễn Văn A|01011995|Nam|Số 1 Đại Cồ Việt, Hai Bà Trưng, Hà Nội|15072021"

    @Test
    fun parsesTheQrFields() {
        val info = CccdQr.parse(qr)!!
        assertEquals("001095012345", info.idNumber)
        assertEquals("Nguyễn Văn A", info.fullName)
        assertEquals("01/01/1995", info.dateOfBirth)
        assertEquals("Nam", info.gender)
        assertEquals("15/07/2021", info.issueDate)
        assertEquals("001 095 012 345", CccdQr.groupId(info.idNumber))
    }

    @Test
    fun rejectsTextThatIsNotACccdQr() {
        assertNull(CccdQr.parse(null))
        assertNull(CccdQr.parse("https://example.com"))
        assertNull(CccdQr.parse("12345|a|b|c|d|e"))
    }

    @Test
    fun flatImageIsBlurryAndEdgesAreSharp() {
        val w = 64
        val h = 64
        val flat = ByteArray(w * h) { 120 }
        val stripes = ByteArray(w * h) { i -> if ((i % w) % 2 == 0) 20 else 220.toByte() }
        assertTrue(ImageChecks.laplacianVariance(flat, w, h) < IdQuality.MIN_SHARPNESS)
        assertTrue(ImageChecks.laplacianVariance(stripes, w, h, step = 1) > IdQuality.MIN_SHARPNESS)
    }

    @Test
    fun brightPatchCountsAsGlare() {
        val w = 40
        val h = 40
        val img = ByteArray(w * h) { i -> if (i % w < 10 && i / w < 10) 255.toByte() else 100 }
        assertEquals(0.0625, ImageChecks.glareFraction(img, w, h, step = 1), 1e-9)
    }

    @Test
    fun retakeHintNamesTheFirstProblem() {
        assertEquals("Ảnh bị mờ, hãy giữ máy chắc tay rồi chụp lại.", idRetakeHint(false, IdQuality(1.0, 0.5, null)))
        assertEquals("Thẻ bị lóa, hãy nghiêng nhẹ thẻ rồi chụp lại.", idRetakeHint(false, IdQuality(500.0, 0.5, null)))
        assertTrue(idRetakeHint(true, IdQuality(500.0, 0.0, null))!!.contains("mã QR"))
        assertNull(idRetakeHint(true, IdQuality(500.0, 0.0, qr)))
        assertNull(idRetakeHint(false, null))
    }

    @Test
    fun autoCaptureNeedsTwoGoodFramesInARow() {
        val sharp = IdQuality(500.0, 0.0, null, looksLikeCard = true, portraitPresent = true)
        val auto = IdAutoCapture()
        assertFalse(auto.offer(sharp))
        assertFalse(auto.offer(IdQuality(10.0, 0.0, null, true))) // blurry frame breaks the run
        assertFalse(auto.offer(sharp))
        assertFalse(auto.offer(IdQuality(500.0, 0.5, null, true))) // glare too
        assertFalse(auto.offer(sharp))
        assertFalse(auto.offer(IdQuality(500.0, 0.0, null, looksLikeCard = false))) // a sharp room is not a card
        assertFalse(auto.offer(sharp))
        assertFalse(auto.offer(IdQuality(500.0, 0.0, null))) // text not read: no auto shot
        assertFalse(auto.offer(sharp))
        assertTrue(auto.offer(sharp))
        auto.reset()
        assertFalse(auto.offer(sharp))
    }

    @Test fun rearSideNeedsReadableQrAndDistinctFrames() {
        val auto = IdAutoCapture(back = true)
        assertFalse(auto.offer(IdQuality(500.0, 0.0, null)))
        val first = IdQuality(500.0, 0.0, qr, frameTimeNs = 1)
        assertFalse(auto.offer(first))
        assertFalse(auto.offer(first))
        assertTrue(auto.offer(first.copy(frameTimeNs = 2)))
        assertFalse(auto.offer(first)) // late asynchronous result cannot complete a new observation
    }

    @Test fun frontDoesNotCaptureAReadableQrWithoutAPortrait() {
        val auto = IdAutoCapture()
        repeat(3) { assertFalse(auto.offer(IdQuality(500.0, 0.0, qr))) }
    }

    @Test fun readableQrIsNotBlockedByWholeFrameQualityHeuristics() {
        val auto = IdAutoCapture(back = true)
        val read = IdQuality(1.0, 0.7, qr, brightness = 20.0, frameTimeNs = 1)
        assertFalse(auto.offer(read))
        assertTrue(auto.offer(read.copy(frameTimeNs = 2)))
        assertTrue(idCaptureUsable(read, back = true, manual = false))
        assertFalse(idCaptureUsable(read.copy(qr = null), back = true, manual = false))
    }

    @Test fun intermittentMatchingReadsCanCompleteWithinTheShortWindow() {
        val auto = IdAutoCapture(back = true)
        val read = IdQuality(500.0, 0.0, qr, frameTimeNs = 1)
        assertFalse(auto.offer(read))
        assertFalse(auto.offer(read.copy(qr = null, frameTimeNs = 100_000_001)))
        assertTrue(auto.offer(read.copy(frameTimeNs = 300_000_001)))
    }

    @Test fun expiredChangedOrResetQrCannotCompleteThePreviousRun() {
        val auto = IdAutoCapture(back = true)
        val read = IdQuality(500.0, 0.0, qr, frameTimeNs = 1)
        assertFalse(auto.offer(read))
        val later = read.copy(frameTimeNs = IdAutoCapture.QR_HOLD_NS + 2)
        assertFalse(auto.offer(later))
        val different = later.copy(qr = qr.replace("001095012345", "001095012346"), frameTimeNs = later.frameTimeNs + 1)
        assertFalse(auto.offer(different))
        auto.reset()
        assertFalse(auto.offer(different.copy(frameTimeNs = different.frameTimeNs + 1)))
    }

    @Test fun retainedQrFeedbackCannotApproveANewPhoto() {
        val noQr = IdQuality(500.0, 0.0, null, qrRecentlySeen = true)
        assertFalse(idCaptureUsable(noQr, back = true, manual = false))
        // Manual fallback may send a clear photo to the server's independent decoder.
        assertTrue(idCaptureUsable(noQr, back = true, manual = true))
        assertFalse(idCaptureUsable(noQr.copy(sharpness = 1.0), back = true, manual = true))
        assertFalse(idCaptureUsable(noQr, back = false, manual = false))
    }

    @Test
    fun cardWordsAreFoundWithOrWithoutDiacritics() {
        assertTrue(CardText.looksLikeCard("CỘNG HÒA XÃ HỘI CHỦ NGHĨA VIỆT NAM\nCĂN CƯỚC CÔNG DÂN"))
        assertTrue(CardText.looksLikeCard("Citizen Identity Card"))
        assertTrue(CardText.looksLikeCard("IDVNM0950123451001095012345<<5"))
        assertTrue(CardText.looksLikeCard("CAN  CUOC")) // OCR without diacritics, extra space
        assertFalse(CardText.looksLikeCard("BOOKS TV LIVING ROOM"))
        assertFalse(CardText.looksLikeCard(""))
    }
}
