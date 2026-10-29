package vn.vericlue.app.capture

/**
 * ID card capture checks (APP-04). Local quality gate only: it helps the user retake a bad photo
 * before sending; it never judges whether the card is genuine.
 */
data class IdQuality(
    val sharpness: Double,
    val glareFraction: Double,
    val qr: String?,
    /** Card words read on the rear camera in the last moment ([CardText]); null = not checked. */
    val looksLikeCard: Boolean? = null,
    val portraitPresent: Boolean = false,
    val brightness: Double = 128.0,
    val tilted: Boolean = false,
    val frameTimeNs: Long = 0,
) {
    val sharp: Boolean get() = sharpness >= MIN_SHARPNESS
    val noGlare: Boolean get() = glareFraction <= MAX_GLARE
    val good: Boolean get() = sharp && noGlare

    companion object {
        // Starting values; tune on real phones and cards (plan, phase 9).
        const val MIN_SHARPNESS = 60.0
        const val MAX_GLARE = 0.02
    }
}

/**
 * Words printed on either side of a CCCD (chip card 2021 and the 2024 "Căn cước"), compared without
 * diacritics. Only used to hold auto-capture until a card is in view: a sharp room is not a card.
 * It never judges whether the card is genuine.
 */
object CardText {
    private val words = listOf(
        "CAN CUOC", "CONG DAN", "CITIZEN", "IDENTITY", "IDVNM", "CONG HOA", "SOCIALIST REPUBLIC",
        "QUOC TICH", "NATIONALITY", "DAC DIEM NHAN DANG", "PERSONAL IDENTIFICATION", "NGAY CAP", "DATE OF ISSUE",
    )

    fun looksLikeCard(text: String): Boolean {
        val plain = java.text.Normalizer.normalize(text.uppercase(), java.text.Normalizer.Form.NFD)
            .replace(Regex("\\p{M}+"), "").replace('Đ', 'D').replace(Regex("\\s+"), " ")
        return words.any { it in plain }
    }
}

/**
 * Requests a still photo after [needed] fresh frames show the portrait/QR with usable quality.
 * The captured still is checked again before upload; timeout/manual controls belong to the UI.
 */
class IdAutoCapture(private val needed: Int = 2, private val back: Boolean = false) {
    private var good = 0
    private var lastFrame = -1L
    private var lastQr: String? = null

    /** True when this frame completes the run: take it. */
    fun offer(q: IdQuality): Boolean {
        if (q.frameTimeNs > 0 && q.frameTimeNs <= lastFrame) return false
        lastFrame = q.frameTimeNs
        val qr = CccdQr.parse(q.qr)
        val visible = if (back) qr != null else q.portraitPresent
        val changed = back && lastQr != null && lastQr != q.qr
        lastQr = q.qr
        good = if (q.good && q.brightness >= 45 && !q.tilted && visible && !changed) good + 1 else 0
        return good >= needed
    }

    fun reset() {
        good = 0
        lastFrame = -1L
        lastQr = null
    }

    companion object {
        /** Time to bring the card into the frame before sampling starts, and between samples. */
        const val START_DELAY_MS = 1500L
        const val SAMPLE_MS = 500L

        /** The photo stays on screen this long before the next side (one beat to look at it). */
        const val PAUSE_MS = 1500L
    }
}

/** A single actionable message; detection is an input-quality check, never identity approval. */
fun idScanHint(q: IdQuality?, back: Boolean): String = when {
    q == null -> if (back) "Đưa mặt có mã QR vào khung" else "Đưa mặt có ảnh chân dung vào khung"
    q.brightness < 45 -> "Đưa thẻ đến nơi sáng hơn"
    !q.noGlare -> "Nghiêng nhẹ thẻ để tránh lóa"
    q.tilted -> "Giữ thẻ thẳng và song song với camera"
    !q.sharp -> "Giữ yên thẻ và điện thoại để lấy nét"
    !back && !q.portraitPresent -> "Đưa mặt có ảnh chân dung vào khung"
    back && CccdQr.parse(q.qr) == null -> "Đưa mã QR lại gần và giữ trong khung"
    else -> "Giữ yên, ứng dụng đang tự chụp"
}

fun idScanErrorText(hint: String?): String = when (hint) {
    "PORTRAIT_UNREADABLE" -> "Chưa thấy rõ chân dung trên thẻ. Hãy quét lại mặt có ảnh chân dung."
    "QR_INVALID" -> "Mã QR chưa có đủ thông tin phù hợp. Hãy quét lại đúng thẻ."
    else -> "Chưa đọc được mã QR từ ảnh. Hãy đưa thẻ gần hơn, tránh lóa rồi quét lại."
}

object ImageChecks {
    /**
     * Variance of a 4-neighbour Laplacian over a luma plane, sampled every [step] pixels.
     * Low variance = blurry.
     */
    fun laplacianVariance(luma: ByteArray, width: Int, height: Int, rowStride: Int = width, step: Int = 2): Double {
        var sum = 0.0
        var sumSq = 0.0
        var n = 0
        fun px(x: Int, y: Int) = luma[y * rowStride + x].toInt() and 0xFF
        var y = 1
        while (y < height - 1) {
            var x = 1
            while (x < width - 1) {
                val lap = px(x - 1, y) + px(x + 1, y) + px(x, y - 1) + px(x, y + 1) - 4 * px(x, y)
                sum += lap
                sumSq += lap.toDouble() * lap
                n++
                x += step
            }
            y += step
        }
        if (n == 0) return 0.0
        val mean = sum / n
        return sumSq / n - mean * mean
    }

    /** Share of near-white pixels: a large bright patch on a card is glare. */
    fun glareFraction(luma: ByteArray, width: Int, height: Int, rowStride: Int = width, step: Int = 4, threshold: Int = 250): Double {
        var bright = 0
        var n = 0
        var y = 0
        while (y < height) {
            var x = 0
            while (x < width) {
                if ((luma[y * rowStride + x].toInt() and 0xFF) >= threshold) bright++
                n++
                x += step
            }
            y += step
        }
        return if (n == 0) 0.0 else bright.toDouble() / n
    }
}

/** Fields read from the QR code on the back of a chip-based CCCD. */
data class CccdInfo(
    val idNumber: String,
    val fullName: String,
    val dateOfBirth: String,
    val gender: String,
    val address: String,
    val issueDate: String?,
)

object CccdQr {
    /**
     * Parses the CCCD QR text: fields separated by "|", commonly
     * `số CCCD|số CMND cũ|họ tên|ngày sinh ddMMyyyy|giới tính|nơi thường trú|ngày cấp ddMMyyyy`.
     * The order must be checked against real cards before relying on it (plan, phase 7).
     * Returns null when the text does not look like a CCCD QR.
     */
    fun parse(raw: String?): CccdInfo? {
        if (raw.isNullOrBlank()) return null
        val f = raw.split("|")
        if (f.size < 6) return null
        val id = f[0].trim()
        if (id.length != 12 || !id.all { it.isDigit() }) return null
        return CccdInfo(
            idNumber = id,
            fullName = f[2].trim(),
            dateOfBirth = formatDate(f[3].trim()),
            gender = f[4].trim(),
            address = f[5].trim(),
            issueDate = f.getOrNull(6)?.trim()?.takeIf { it.isNotEmpty() }?.let(::formatDate),
        )
    }

    /** "01011995" → "01/01/1995"; anything else is returned unchanged. */
    fun formatDate(d: String): String =
        if (d.length == 8 && d.all { it.isDigit() }) "${d.substring(0, 2)}/${d.substring(2, 4)}/${d.substring(4)}" else d

    /** "001095012345" → "001 095 012 345" for display. */
    fun groupId(id: String): String = id.chunked(3).joinToString(" ")
}
