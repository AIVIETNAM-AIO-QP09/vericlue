package vn.vericlue.app.capture

import java.io.ByteArrayOutputStream
import java.io.InputStream

/** Match API card image limits. Preserve JPEG pixels and EXIF rather than re-compressing the QR. */
object DocumentImageLimits {
    const val MAX_BYTES = 10 * 1024 * 1024
    const val MAX_PIXELS = 16_000_000L

    fun dimensionsAllowed(width: Int, height: Int): Boolean =
        width > 0 && height > 0 && width.toLong() * height <= MAX_PIXELS

    fun readBounded(input: InputStream, limit: Int = MAX_BYTES): ByteArray {
        require(limit > 0)
        val output = ByteArrayOutputStream()
        val buffer = ByteArray(8192)
        while (true) {
            val count = input.read(buffer, 0, minOf(buffer.size, limit - output.size() + 1))
            if (count < 0) break
            require(output.size().toLong() + count <= limit) { "Document image is too large" }
            output.write(buffer, 0, count)
        }
        require(output.size() > 0) { "Document image is empty" }
        return output.toByteArray()
    }
}
