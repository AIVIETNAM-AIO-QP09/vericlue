package vn.vericlue.app

import com.google.zxing.BarcodeFormat
import com.google.zxing.EncodeHintType
import com.google.zxing.qrcode.QRCodeWriter
import org.junit.Assert.*
import org.junit.Test
import vn.vericlue.app.capture.CardQrDecoder
import vn.vericlue.app.capture.conflictingCardQr
import vn.vericlue.app.capture.uniqueCardQr

class CardQrDecoderTest {
    private val payload = "001095012345||NGƯỜI DÙNG MINH HỌA|01011995|Nam|ĐỊA CHỈ MINH HỌA VIỆT NAM|01012023"
    private fun qr(text: String, side: Int = 360): IntArray {
        val bits = QRCodeWriter().encode(text, BarcodeFormat.QR_CODE, side, side,
            mapOf(EncodeHintType.CHARACTER_SET to "UTF-8", EncodeHintType.QR_VERSION to 10))
        return IntArray(side * side) { if (bits[it % side, it / side]) 0xff101010.toInt() else -1 }
    }

    @Test fun denseUtf8CardQrCanBeDecodedWithoutMlKitOrNetwork() {
        assertEquals(listOf(payload), CardQrDecoder.decode(360, 360, qr(payload)))
    }

    @Test fun smallQrInsideFullCardWithUnevenLightingKeepsNativePixels() {
        val width = 1400; val height = 880; val side = 240
        val card = IntArray(width * height) { val l = 180 + (it % width) * 75 / width; (0xff000000.toInt() or (l shl 16) or (l shl 8) or l) }
        val code = qr(payload, side)
        for (y in 0 until side) for (x in 0 until side) card[(y + 100) * width + x + 1050] = code[y * side + x]
        assertTrue(payload in CardQrDecoder.decode(width, height, card))
    }

    @Test fun rotatedCardQrIsReadable() {
        val side = 360; val original = qr(payload)
        val rotated = IntArray(side * side) { original[(side - 1 - it % side) * side + it / side] }
        assertTrue(payload in CardQrDecoder.decode(side, side, rotated))
    }

    @Test fun twoCardsKeepBothPayloadsInsteadOfApprovingTheFirst() {
        val side = 360; val width = 900; val other = payload.replace("001095012345", "001095012346")
        val pixels = IntArray(width * 500) { -1 }
        for ((offset, text) in listOf(30 to payload, 490 to other)) {
            val code = qr(text)
            for (y in 0 until side) for (x in 0 until side) pixels[(y + 60) * width + x + offset] = code[y * side + x]
        }
        val values = CardQrDecoder.decode(width, 500, pixels)
        assertEquals(setOf(payload, other), values.toSet())
        assertTrue(conflictingCardQr(values))
        assertNull(uniqueCardQr(values))
    }

    @Test fun blankCardDoesNotInventARead() {
        assertTrue(CardQrDecoder.decode(480, 300, IntArray(480 * 300) { -1 }).isEmpty())
    }

    @Test(expected = IllegalArgumentException::class)
    fun inconsistentBufferIsRejectedBeforeTheDecoder() {
        CardQrDecoder.decode(100, 100, IntArray(1))
    }
}
