package vn.vericlue.app.capture

/** Bounded QR-only retry regions within the already cropped card bitmap. */
fun cardQrRetryRegions(width: Int, height: Int, candidates: List<CardFrameRect>): List<CardFrameRect> {
    require(width > 0 && height > 0)
    val detected = candidates.mapNotNull { box ->
        val left = box.left.coerceIn(0, width)
        val top = box.top.coerceIn(0, height)
        val right = box.right.coerceIn(0, width)
        val bottom = box.bottom.coerceIn(0, height)
        if (right <= left || bottom <= top) null else CardFrameRect(left, top, right, bottom)
    }.sortedByDescending { it.width.toLong() * it.height }.take(2).map { box ->
        val margin = maxOf(12, maxOf(box.width, box.height) / 5)
        CardFrameRect((box.left - margin).coerceAtLeast(0), (box.top - margin).coerceAtLeast(0),
            (box.right + margin).coerceAtMost(width), (box.bottom + margin).coerceAtMost(height))
    }.distinct()
    if (detected.isNotEmpty()) return detected
    // Detector misses get two overlapping native-pixel views. No printed QR position is assumed.
    val span = ((width * 65L + 99L) / 100L).toInt()
    return listOf(CardFrameRect(0, 0, span, height), CardFrameRect(width - span, 0, width, height)).distinct()
}
