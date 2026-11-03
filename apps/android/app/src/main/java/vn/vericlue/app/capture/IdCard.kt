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
    /** UI feedback only; never a replacement for a QR decoded from this frame/photo. */
    val qrRecentlySeen: Boolean = false,
    /** A region can trigger a higher-resolution photo, never approve its contents. */
    val qrCandidatePresent: Boolean = false,
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
 * Requests a still after [needed] portrait/QR observations, or a longer clear-portrait probe.
 * Preview heuristics only decide when to try; the fresh still must pass every upload check.
 */
@Suppress("UNUSED_PARAMETER") // Legacy preview callers still pass a side; capture is always unified.
class IdAutoCapture(private val needed: Int = 2, back: Boolean = false) {
    private var good = 0
    private var lastFrame = -1L
    private var lastQr: String? = null
    private var lastReadNs = 0L

    /** True when this frame completes the run: take it. */
    fun offer(q: IdQuality): Boolean {
        if (q.frameTimeNs > 0 && q.frameTimeNs <= lastFrame) return false
        lastFrame = q.frameTimeNs
        val expired = q.frameTimeNs > 0 && lastReadNs > 0 && q.frameTimeNs - lastReadNs > QR_HOLD_NS
        val qrEvidence = CccdQr.parse(q.qr) != null || q.qrCandidatePresent
        val readyForStill = q.portraitPresent && (qrEvidence || (q.good && q.brightness >= 45))
        if (!readyForStill) {
            good = 0
            lastQr = null
            return false
        }
        good = if (!expired && lastQr == q.qr) good + 1 else 1
        lastQr = q.qr
        lastReadNs = q.frameTimeNs
        return good >= (if (qrEvidence) needed else maxOf(4, needed))
    }

    fun reset() {
        good = 0
        lastFrame = -1L
        lastQr = null
        lastReadNs = 0L
    }

    companion object {
        /** Time to bring the card into the frame before sampling starts, and between samples. */
        const val START_DELAY_MS = 1500L
        const val SAMPLE_MS = 500L

        /** Legacy presentation timing; retry scheduling is owned by IdAutoCaptureScheduler. */
        const val PAUSE_MS = 1500L
        const val QR_HOLD_NS = 1_500_000_000L
    }
}

/** A single actionable message; detection is an input-quality check, never identity approval. */
@Suppress("UNUSED_PARAMETER")
fun idScanHint(q: IdQuality?, back: Boolean): String = when {
    q == null -> "Đưa mặt có ảnh chân dung và mã QR vào khung"
    q.brightness < 45 -> "Đưa thẻ đến nơi sáng hơn"
    !q.noGlare -> "Nghiêng nhẹ thẻ để tránh lóa"
    !q.sharp -> "Giữ yên thẻ và điện thoại để lấy nét"
    q.portraitPresent && CccdQr.parse(q.qr) != null -> "Giữ yên, ứng dụng đang tự chụp"
    q.tilted -> "Giữ thẻ thẳng và song song với camera"
    !q.portraitPresent -> "Đặt đủ bốn góc thẻ trong khung để thấy rõ chân dung"
    CccdQr.parse(q.qr) == null -> "Đưa thẻ gần hơn để mã QR rõ, giữ đủ bốn góc trong khung"
    else -> "Giữ yên, ứng dụng đang tự chụp"
}

/** Validate the fresh still, not the live scanner's retained state. Server checks it again. */
@Suppress("UNUSED_PARAMETER")
fun idCaptureUsable(q: IdQuality, back: Boolean, manual: Boolean): Boolean =
    q.good && q.brightness >= 45 && q.portraitPresent && CccdQr.parse(q.qr) != null

/** Elapsed time never changes the scan into a manual shutter step. */
@Suppress("UNUSED_PARAMETER")
fun idScanDisplayHint(q: IdQuality?, back: Boolean, timedOut: Boolean = false, hint: String? = null): String =
    hint ?: idScanHint(q, back)

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
        val name = f[2].trim()
        val birth = f[3].trim()
        val gender = f[4].trim()
        if (name.isEmpty() || !validDate(birth) || gender !in setOf("Nam", "Nữ")) return null
        return CccdInfo(
            idNumber = id,
            fullName = name,
            dateOfBirth = formatDate(birth),
            gender = gender,
            address = f[5].trim(),
            issueDate = f.getOrNull(6)?.trim()?.takeIf(::validDate)?.let(::formatDate),
        )
    }

    private fun validDate(value: String): Boolean {
        if (value.length != 8 || !value.all { it in '0'..'9' }) return false
        return runCatching {
            val year = value.substring(4).toInt()
            require(year > 0)
            java.time.LocalDate.of(year, value.substring(2, 4).toInt(), value.substring(0, 2).toInt())
        }.isSuccess
    }

    /** "01011995" → "01/01/1995"; anything else is returned unchanged. */
    fun formatDate(d: String): String =
        if (d.length == 8 && d.all { it.isDigit() }) "${d.substring(0, 2)}/${d.substring(2, 4)}/${d.substring(4)}" else d

    /** "001095012345" → "001 095 012 345" for display. */
    fun groupId(id: String): String = id.chunked(3).joinToString(" ")
}
