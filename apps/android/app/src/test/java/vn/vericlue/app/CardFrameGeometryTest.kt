package vn.vericlue.app

import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Test
import vn.vericlue.app.capture.CardFrameRect
import vn.vericlue.app.capture.cardFrameRect
import vn.vericlue.app.capture.uniqueCardQr

class CardFrameGeometryTest {
    @Test fun sensorCropIsRespectedBeforePreviewFill() {
        assertEquals(CardFrameRect(100, 200, 1900, 1400),
            cardFrameRect(2000, 1600, CardFrameRect(100, 200, 1900, 1400), 0, 1.5f))
    }

    @Test fun rotatedOffCenterViewportStaysAtItsActualPosition() {
        val sensorCrop = CardFrameRect(100, 200, 1700, 1200)
        assertEquals(CardFrameRect(200, 100, 1200, 1700),
            cardFrameRect(2000, 1400, sensorCrop, 90, 0.625f))
        assertEquals(CardFrameRect(300, 200, 1900, 1200),
            cardFrameRect(2000, 1400, sensorCrop, 180, 1.6f))
        assertEquals(CardFrameRect(200, 300, 1200, 1900),
            cardFrameRect(2000, 1400, sensorCrop, 270, 0.625f))
    }

    @Test fun fillCenterMatchesTheVisiblePreviewInsteadOfTheFullSensor() {
        assertEquals(CardFrameRect(100, 350, 1900, 1250),
            cardFrameRect(2000, 1600, CardFrameRect(100, 200, 1900, 1400), 0, 2f))
        assertEquals(CardFrameRect(400, 200, 1600, 1400),
            cardFrameRect(2000, 1600, CardFrameRect(100, 200, 1900, 1400), 0, 1f))
    }

    @Test fun differentQrPayloadsOnTheSameImageCannotBeSilentlyCombined() {
        val first = "001095012345||Nguyễn Văn A|01011995|Nam|Hà Nội|15072021"
        val other = first.replace("001095012345", "001095012346")
        assertEquals(first, uniqueCardQr(listOf(first, first)))
        assertNull(uniqueCardQr(listOf(first, other)))
        assertNull(uniqueCardQr(listOf("https://example.com")))
    }
}
