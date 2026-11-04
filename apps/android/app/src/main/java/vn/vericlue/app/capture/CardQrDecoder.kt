package vn.vericlue.app.capture

import com.google.zxing.BinaryBitmap
import com.google.zxing.DecodeHintType
import com.google.zxing.NotFoundException
import com.google.zxing.RGBLuminanceSource
import com.google.zxing.common.GlobalHistogramBinarizer
import com.google.zxing.common.HybridBinarizer
import com.google.zxing.multi.qrcode.QRCodeMultiReader

/** An independent still-image decoder; never merges evidence from different photos. */
object CardQrDecoder {
    fun decode(width: Int, height: Int, pixels: IntArray): List<String> {
        require(width > 0 && height > 0 && width.toLong() * height == pixels.size.toLong())
        require(pixels.size <= 16_000_000)
        val source = RGBLuminanceSource(width, height, pixels)
        val hints = mapOf(DecodeHintType.TRY_HARDER to true)
        val reads = linkedSetOf<String>()
        // Local contrast and global contrast can recover different codes; retain conflicts.
        for (binarizer in listOf(HybridBinarizer(source), GlobalHistogramBinarizer(source))) {
            try {
                QRCodeMultiReader().decodeMultiple(BinaryBitmap(binarizer), hints)
                    .mapTo(reads) { it.text }
            } catch (_: NotFoundException) { /* No readable code is a normal capture result. */ }
        }
        return reads.toList()
    }
}
