package vn.vericlue.app.capture

import kotlin.math.roundToInt

/** Pixel bounds, exclusive on the right/bottom, independent of Android for geometry tests. */
data class CardFrameRect(val left: Int, val top: Int, val right: Int, val bottom: Int) {
    val width: Int get() = right - left
    val height: Int get() = bottom - top
}

/** Rotate CameraX's actual viewport crop, then apply PreviewView's FILL_CENTER aspect. */
fun cardFrameRect(width: Int, height: Int, crop: CardFrameRect, rotation: Int, previewAspect: Float): CardFrameRect {
    require(width > 0 && height > 0 && previewAspect.isFinite() && previewAspect > 0)
    require(crop.left >= 0 && crop.top >= 0 && crop.right <= width && crop.bottom <= height && crop.width > 0 && crop.height > 0)
    val upright = when (rotation) {
        0 -> crop
        90 -> CardFrameRect(height - crop.bottom, crop.left, height - crop.top, crop.right)
        180 -> CardFrameRect(width - crop.right, height - crop.bottom, width - crop.left, height - crop.top)
        270 -> CardFrameRect(crop.top, width - crop.right, crop.bottom, width - crop.left)
        else -> error("Unsupported card rotation")
    }
    val targetWidth = minOf(upright.width, (upright.height * previewAspect).roundToInt()).coerceAtLeast(1)
    val targetHeight = minOf(upright.height, (upright.width / previewAspect).roundToInt()).coerceAtLeast(1)
    val left = upright.left + (upright.width - targetWidth) / 2
    val top = upright.top + (upright.height - targetHeight) / 2
    return CardFrameRect(left, top, left + targetWidth, top + targetHeight)
}

/** All decoded values on a single image must agree; never pick the first of conflicting cards. */
fun uniqueCardQr(values: List<String>): String? {
    val valid = values.filter { CccdQr.parse(it) != null }.distinct()
    return valid.singleOrNull()
}
