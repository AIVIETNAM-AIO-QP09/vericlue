package vn.vericlue.app.capture

import android.content.Context
import android.graphics.BitmapFactory
import android.net.Uri
import java.io.File

/** Read only the fresh JPEG returned by the scanner; never import gallery or network content. */
fun readDocumentJpeg(context: Context, uri: Uri): ByteArray {
    require(uri.scheme == "content" || ownedDocumentFile(context, uri) != null)
    val bytes = requireNotNull(context.contentResolver.openInputStream(uri)).use {
        DocumentImageLimits.readBounded(it)
    }
    val bounds = BitmapFactory.Options().apply { inJustDecodeBounds = true }
    BitmapFactory.decodeByteArray(bytes, 0, bytes.size, bounds)
    require(bounds.outMimeType == "image/jpeg" && DocumentImageLimits.dimensionsAllowed(bounds.outWidth, bounds.outHeight))
    return bytes
}

/** Scanner gallery import is disabled: returned images are disposable capture results. */
fun discardDocumentImage(context: Context, uri: Uri) {
    runCatching {
        if (uri.scheme == "content") context.contentResolver.delete(uri, null, null)
        else ownedDocumentFile(context, uri)?.delete()
    }
}

private fun ownedDocumentFile(context: Context, uri: Uri): File? {
    if (uri.scheme != "file") return null
    val file = uri.path?.let(::File)?.canonicalFile ?: return null
    val roots = listOfNotNull(context.cacheDir, context.externalCacheDir)
    return file.takeIf { roots.any { root -> file.path.startsWith(root.canonicalPath + File.separator) } }
}
