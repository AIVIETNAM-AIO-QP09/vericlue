package vn.vericlue.app.ui

import java.net.URI

/** Exact local asset allowlist. An unknown path must never fall through to the network. */
internal object ThreeAssetPolicy {
    const val ORIGIN = "https://appassets.androidplatform.net"
    const val PAGE = "$ORIGIN/three/index.html"
    private val assets = mapOf(
        "/three/index.html" to "text/html",
        "/three/scene.css" to "text/css",
        "/three/scene.js" to "text/javascript",
        "/three/illustrations.js" to "text/javascript",
        "/three/vendor/three.module.min.js" to "text/javascript",
    )

    fun asset(url: String): Pair<String, String>? = runCatching {
        val uri = URI(url)
        if (uri.scheme != "https" || uri.rawAuthority != "appassets.androidplatform.net" ||
            uri.rawQuery != null || uri.rawFragment != null) return null
        val mime = assets[uri.rawPath] ?: return null
        uri.rawPath.removePrefix("/") to mime
    }.getOrNull()
}
