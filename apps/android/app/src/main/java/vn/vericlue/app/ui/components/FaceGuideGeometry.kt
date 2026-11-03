package vn.vericlue.app.ui.components

import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.geometry.Rect

/** The established camera-coordinate source bounds, independent of display text size. */
fun faceSourceGuideRect(width: Float, height: Float, density: Float, topInset: Float, bottomInset: Float): Rect =
    layoutFaceGuide(width, height, density, 1f, topInset, bottomInset, compact = false)

/** Compact on-screen aperture. The preview must be transformed with this guide, never cropped alone. */
fun faceGuideRect(width: Float, height: Float, density: Float, fontScale: Float, topInset: Float, bottomInset: Float): Rect =
    layoutFaceGuide(width, height, density, fontScale, topInset, bottomInset, compact = true)

private fun layoutFaceGuide(
    width: Float, height: Float, density: Float, fontScale: Float,
    topInset: Float, bottomInset: Float, compact: Boolean,
): Rect {
    val top = topInset + (128f + 64f * fontScale) * density
    val bottom = bottomInset + (112f + 56f * fontScale) * density
    val available = (height - top - bottom).coerceAtLeast(24f * density)
    val maxWidth = if (compact) minOf(264f * density, width * 0.68f) else minOf(320f * density, width * 0.82f)
    val h = minOf(maxWidth * 1.32f, available * if (compact) 0.90f else 1f)
    val w = h / 1.32f
    val center = (height * 0.46f).coerceIn(top + h / 2, maxOf(top + h / 2, height - bottom - h / 2))
    return Rect((width - w) / 2, center - h / 2, (width + w) / 2, center + h / 2)
}

fun faceThumbnailRect(width: Float, density: Float, topInset: Float): Rect {
    val w = minOf(92f * density, width * 0.24f)
    val right = width - 20f * density
    val top = topInset + 112f * density
    return Rect(right - w, top, right, top + w * 1.32f)
}

/** Both endpoints show the same camera region; only its drawing scale and position change. */
fun faceCameraPresentation(source: Rect, aperture: Rect, thumbnail: Rect, progress: Float): CameraPresentation {
    val regular = cameraPresentation(source, aperture, 1f)
    val compact = cameraPresentation(source, thumbnail, 1f)
    val amount = progress.coerceIn(0f, 1f)
    return CameraPresentation(
        regular.scale + (compact.scale - regular.scale) * amount,
        regular.x + (compact.x - regular.x) * amount,
        regular.y + (compact.y - regular.y) * amount,
    )
}

/** Thumbnail bounds are in root coordinates; the stable native host draws in local coordinates. */
fun voiceFacePresentation(viewport: Rect, thumbnail: Rect, density: Float, topInset: Float, bottomInset: Float): CameraPresentation {
    val values = listOf(viewport.left, viewport.top, viewport.right, viewport.bottom,
        thumbnail.left, thumbnail.top, thumbnail.right, thumbnail.bottom, density, topInset, bottomInset)
    if (values.any { !it.isFinite() } || viewport.isEmpty || thumbnail.isEmpty || density <= 0f) return CameraPresentation()
    val source = faceSourceGuideRect(viewport.width, viewport.height, density, topInset, bottomInset)
    val localThumbnail = thumbnail.translate(Offset(-viewport.left, -viewport.top))
    return cameraPresentation(source, localThumbnail, 1f)
}
