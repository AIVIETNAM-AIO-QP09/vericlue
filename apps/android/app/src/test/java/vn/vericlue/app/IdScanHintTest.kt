package vn.vericlue.app

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Test
import vn.vericlue.app.capture.IdQuality
import vn.vericlue.app.capture.idScanDisplayHint

class IdScanHintTest {
    private val readable = IdQuality(500.0, 0.0,
        "001095012345||Nguyễn Văn A|01011995|Nam|Địa chỉ minh họa|15072021")

    @Test fun expiredAutoCaptureDirectsReadableQrToTheAvailableManualButton() {
        val message = idScanDisplayHint(readable, back = true, timedOut = true)
        assertEquals("Tự chụp đã dừng. Bấm “Chụp ảnh thẻ” để tiếp tục.", message)
        assertFalse(message.contains("đang tự chụp"))
    }

    @Test fun expiredAutoCaptureSuppressesThePreviousAutoCaptureHint() {
        assertEquals("Tự chụp đã dừng. Bấm “Chụp ảnh thẻ” để tiếp tục.",
            idScanDisplayHint(readable, back = true, timedOut = true,
                hint = "Giữ yên, ứng dụng đang tự chụp"))
    }

    @Test fun activeReadableQrKeepsTheAutoCaptureInstruction() {
        assertEquals("Giữ yên, ứng dụng đang tự chụp",
            idScanDisplayHint(readable, back = true, timedOut = false))
    }

    @Test fun expiredAutoCaptureKeepsTheFailedStillQualityReasonWithTheManualAction() {
        val message = idScanDisplayHint(readable, back = true, timedOut = true,
            hint = "Nghiêng nhẹ thẻ để tránh lóa")
        assertEquals("Nghiêng nhẹ thẻ để tránh lóa. Tự chụp đã dừng. Bấm “Chụp ảnh thẻ” để tiếp tục.", message)
    }

    @Test fun activeScanKeepsQualityAndStillHints() {
        assertEquals("Đưa thẻ đến nơi sáng hơn",
            idScanDisplayHint(readable.copy(qr = null, brightness = 20.0), back = true, timedOut = false))
        assertEquals("Nghiêng nhẹ thẻ để tránh lóa",
            idScanDisplayHint(readable, back = true, timedOut = false, hint = "Nghiêng nhẹ thẻ để tránh lóa"))
        assertEquals("Đưa mặt có ảnh chân dung vào khung",
            idScanDisplayHint(null, back = false, timedOut = false))
    }
}
