package vn.vericlue.app

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Test
import vn.vericlue.app.capture.IdQuality
import vn.vericlue.app.capture.idScanDisplayHint

class IdScanHintTest {
    private val readable = IdQuality(500.0, 0.0,
        "001095012345||Nguyễn Văn A|01011995|Nam|Địa chỉ minh họa|15072021", portraitPresent = true)

    @Test fun elapsedScanNeverAsksForAShutterPress() {
        val message = idScanDisplayHint(readable, back = true, timedOut = true)
        assertEquals("Giữ yên, ứng dụng đang tự chụp", message)
        assertFalse(message.contains("Bấm"))
    }

    @Test fun elapsedScanKeepsAutomaticCaptureInstruction() {
        assertEquals("Giữ yên, ứng dụng đang tự chụp",
            idScanDisplayHint(readable, back = true, timedOut = true,
                hint = "Giữ yên, ứng dụng đang tự chụp"))
    }

    @Test fun activeReadableQrKeepsTheAutoCaptureInstruction() {
        assertEquals("Giữ yên, ứng dụng đang tự chụp",
            idScanDisplayHint(readable, back = true, timedOut = false))
    }

    @Test fun readablePortraitAndQrDoNotAskForAnUnnecessaryAngleCorrection() {
        assertEquals("Giữ yên, ứng dụng đang tự chụp",
            idScanDisplayHint(readable.copy(tilted = true), back = false, timedOut = false))
    }

    @Test fun elapsedScanKeepsQualityAdviceWithoutAManualAction() {
        val message = idScanDisplayHint(readable, back = true, timedOut = true,
            hint = "Nghiêng nhẹ thẻ để tránh lóa")
        assertEquals("Nghiêng nhẹ thẻ để tránh lóa", message)
    }

    @Test fun activeScanKeepsQualityAndStillHints() {
        assertEquals("Đưa thẻ đến nơi sáng hơn",
            idScanDisplayHint(readable.copy(qr = null, brightness = 20.0), back = true, timedOut = false))
        assertEquals("Nghiêng nhẹ thẻ để tránh lóa",
            idScanDisplayHint(readable, back = true, timedOut = false, hint = "Nghiêng nhẹ thẻ để tránh lóa"))
        assertEquals("Đưa mặt có ảnh chân dung và mã QR vào khung",
            idScanDisplayHint(null, back = false, timedOut = false))
    }
}
