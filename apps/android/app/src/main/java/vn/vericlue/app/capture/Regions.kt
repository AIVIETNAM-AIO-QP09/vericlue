package vn.vericlue.app.capture

import kotlinx.serialization.SerialName
import kotlinx.serialization.Serializable

/**
 * Colour per face region while the screen flashes (Signals.region_means, ADR-0016 layer 1).
 * Same statistics as the web (apps/web/src/lib/capture/chromapulse/regions.ts): per-channel
 * median over all pixels and after dropping too dark / too bright pixels.
 *
 * Difference from the web: regions are fixed fractions of the ML Kit face box, not MediaPipe
 * landmarks. The server only stores region_means for reference today; PRES-02 must agree on
 * the definition before it is used for a decision.
 */
@Serializable
data class RegionStat(
    @SerialName("rgb_all") val rgbAll: List<Int>?,
    @SerialName("rgb_trim") val rgbTrim: List<Int>?,
    @SerialName("excluded_fraction") val excludedFraction: Double,
    val pixels: Int,
)

@Serializable
data class RegionFrame(
    @SerialName("t_ms") val tMs: Double,
    val regions: Map<String, RegionStat>,
)

/** Axis-aligned box in pixels of the upright image. */
data class Box(val left: Float, val top: Float, val right: Float, val bottom: Float) {
    val width get() = right - left
    val height get() = bottom - top
    fun intersects(o: Box) = left < o.right && o.left < right && top < o.bottom && o.top < bottom
}

object Regions {
    const val LUMA_EXCLUDE_LOW = 55
    const val LUMA_EXCLUDE_HIGH = 200
    const val BACKGROUND_SIZE_FRACTION = 0.12f
    const val FACE_MARGIN_FRACTION = 0.1f

    /** Skin regions as fractions (left, top, right, bottom) of the face box. "Left/right" are as seen in the frame. */
    val SKIN = linkedMapOf(
        "forehead" to floatArrayOf(0.30f, 0.06f, 0.70f, 0.22f),
        "left_cheek" to floatArrayOf(0.14f, 0.50f, 0.36f, 0.68f),
        "right_cheek" to floatArrayOf(0.64f, 0.50f, 0.86f, 0.68f),
        "nose" to floatArrayOf(0.43f, 0.42f, 0.57f, 0.62f),
        "chin" to floatArrayOf(0.38f, 0.86f, 0.62f, 0.97f),
    )

    fun skinBoxes(face: Box): Map<String, Box> = SKIN.mapValues { (_, f) ->
        Box(face.left + f[0] * face.width, face.top + f[1] * face.height, face.left + f[2] * face.width, face.top + f[3] * face.height)
    }

    /** Two squares in the top corners of the frame; a square touching the face (plus margin) is dropped. */
    fun backgroundBoxes(face: Box, width: Int, height: Int): List<Box> {
        val side = BACKGROUND_SIZE_FRACTION * width
        val mx = FACE_MARGIN_FRACTION * face.width
        val my = FACE_MARGIN_FRACTION * face.height
        val guard = Box(face.left - mx, face.top - my, face.right + mx, face.bottom + my)
        return listOf(Box(0f, 0f, side, side), Box(width - side, 0f, width.toFloat(), side))
            .filter { it.bottom <= height && !it.intersects(guard) }
    }

    /**
     * Measures every region. [rgbAt] returns the colour at an upright pixel (x, y).
     * [step] samples every n-th pixel to keep this cheap on the analysis thread.
     */
    fun measure(face: Box, width: Int, height: Int, step: Int = 3, rgbAt: (Int, Int) -> Int): Map<String, RegionStat> {
        val out = LinkedHashMap<String, RegionStat>()
        skinBoxes(face).forEach { (name, box) -> out[name] = stat(listOf(box), width, height, step, rgbAt) }
        val bg = backgroundBoxes(face, width, height)
        if (bg.isNotEmpty()) out["background"] = stat(bg, width, height, step, rgbAt)
        return out
    }

    private fun stat(boxes: List<Box>, width: Int, height: Int, step: Int, rgbAt: (Int, Int) -> Int): RegionStat {
        val all = Array(3) { ArrayList<Int>() }
        val kept = Array(3) { ArrayList<Int>() }
        for (b in boxes) {
            val x0 = b.left.toInt().coerceIn(0, width - 1)
            val x1 = b.right.toInt().coerceIn(0, width)
            val y0 = b.top.toInt().coerceIn(0, height - 1)
            val y1 = b.bottom.toInt().coerceIn(0, height)
            var y = y0
            while (y < y1) {
                var x = x0
                while (x < x1) {
                    val c = rgbAt(x, y)
                    val r = (c shr 16) and 0xFF
                    val g = (c shr 8) and 0xFF
                    val bl = c and 0xFF
                    all[0] += r; all[1] += g; all[2] += bl
                    val luma = 0.299 * r + 0.587 * g + 0.114 * bl
                    if (luma > LUMA_EXCLUDE_LOW && luma < LUMA_EXCLUDE_HIGH) {
                        kept[0] += r; kept[1] += g; kept[2] += bl
                    }
                    x += step
                }
                y += step
            }
        }
        val n = all[0].size
        return RegionStat(
            rgbAll = if (n == 0) null else all.map(::median),
            rgbTrim = if (kept[0].isEmpty()) null else kept.map(::median),
            excludedFraction = if (n == 0) 0.0 else 1.0 - kept[0].size.toDouble() / n,
            pixels = n,
        )
    }

    private fun median(v: List<Int>): Int {
        val s = v.sorted()
        val mid = s.size / 2
        return if (s.size % 2 == 1) s[mid] else (s[mid - 1] + s[mid] + 1) / 2
    }

    /** YUV_420_888 pixel → packed RGB (BT.601 full range). */
    fun yuvToRgb(y: Int, u: Int, v: Int): Int {
        val c = y
        val d = u - 128
        val e = v - 128
        val r = (c + 1.402 * e).toInt().coerceIn(0, 255)
        val g = (c - 0.344136 * d - 0.714136 * e).toInt().coerceIn(0, 255)
        val b = (c + 1.772 * d).toInt().coerceIn(0, 255)
        return (r shl 16) or (g shl 8) or b
    }

    /**
     * Maps a pixel of the upright image back to the sensor buffer, for a frame that must be
     * rotated clockwise by [rotation] degrees to be upright. [w], [h] are the sensor buffer size.
     */
    fun sensorXY(u: Int, v: Int, rotation: Int, w: Int, h: Int): Pair<Int, Int> = when (rotation) {
        90 -> v to (h - 1 - u)
        180 -> (w - 1 - u) to (h - 1 - v)
        270 -> (w - 1 - v) to u
        else -> u to v
    }
}
