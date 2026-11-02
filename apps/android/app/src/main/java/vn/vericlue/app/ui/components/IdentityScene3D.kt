package vn.vericlue.app.ui.components

import android.annotation.SuppressLint
import android.content.Context
import android.graphics.Color
import android.view.MotionEvent
import android.view.View
import android.webkit.ConsoleMessage
import android.webkit.PermissionRequest
import android.webkit.RenderProcessGoneDetail
import android.webkit.WebChromeClient
import android.webkit.WebResourceError
import android.webkit.WebResourceRequest
import android.webkit.WebResourceResponse
import android.webkit.WebSettings
import android.webkit.WebView
import android.webkit.WebViewClient
import android.widget.FrameLayout
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.runtime.*
import androidx.compose.ui.Modifier
import androidx.compose.ui.layout.boundsInWindow
import androidx.compose.ui.layout.onGloballyPositioned
import androidx.compose.ui.platform.LocalInspectionMode
import androidx.compose.ui.platform.LocalView
import androidx.compose.ui.semantics.clearAndSetSemantics
import androidx.compose.ui.viewinterop.AndroidView
import androidx.lifecycle.Lifecycle
import androidx.lifecycle.LifecycleEventObserver
import androidx.lifecycle.compose.LocalLifecycleOwner
import java.io.ByteArrayInputStream
import kotlin.coroutines.resume
import kotlinx.coroutines.delay
import kotlinx.coroutines.suspendCancellableCoroutine
import kotlinx.coroutines.withTimeoutOrNull
import vn.vericlue.app.ui.ThreeAssetPolicy
import vn.vericlue.app.ui.theme.Vc

/** Decorative only: never takes focus, consumes touch, or receives identity/session data. */
private class IllustrationWebView(context: Context) : WebView(context) {
    // Deliberately not a clickable control: return every gesture to the Compose scroller.
    @SuppressLint("ClickableViewAccessibility")
    override fun onTouchEvent(event: MotionEvent): Boolean = false
}

/** Offline Three.js hero; snapshots, reduced motion and unavailable WebGL use the native drawing. */
@SuppressLint("SetJavaScriptEnabled")
@Composable
fun IdentityScene3D(
    modifier: Modifier = Modifier,
    scene: IllustrationScene = IllustrationScene.Card,
) {
    val preview = LocalInspectionMode.current || LocalView.current.isInEditMode
    if (preview || !Vc.motion.enabled) {
        SceneFallback(scene, modifier)
        return
    }
    var browser by remember { mutableStateOf<WebView?>(null) }
    var ready by remember { mutableStateOf(false) }
    var failed by remember { mutableStateOf(false) }
    var visible by remember { mutableStateOf(false) }
    val lifecycle = LocalLifecycleOwner.current.lifecycle
    var resumed by remember(lifecycle) { mutableStateOf(lifecycle.currentState.isAtLeast(Lifecycle.State.RESUMED)) }
    DisposableEffect(lifecycle) {
        val observer = LifecycleEventObserver { _, _ -> resumed = lifecycle.currentState.isAtLeast(Lifecycle.State.RESUMED) }
        lifecycle.addObserver(observer)
        onDispose { lifecycle.removeObserver(observer) }
    }
    LaunchedEffect(browser, resumed) {
        val view = browser ?: return@LaunchedEffect
        if (!resumed || ready || failed) return@LaunchedEffect
        withTimeoutOrNull(3500) {
            while (!ready && !failed) {
                val state = suspendCancellableCoroutine<String> { continuation ->
                    runCatching {
                        view.evaluateJavascript("window.vericlueScene ? window.vericlueScene.status : 'loading'") {
                            if (continuation.isActive) continuation.resume(it ?: "null")
                        }
                    }.onFailure { if (continuation.isActive) continuation.resume("\"fallback\"") }
                }
                if (browser !== view) return@withTimeoutOrNull
                if (state == "\"ready\"") ready = true
                if (state == "\"fallback\"") failed = true
                if (!ready && !failed) delay(100)
            }
        }
        if (!ready && browser === view) failed = true
    }
    val dark = Vc.colors.isDark
    // Configuration contains only enum literals and booleans; switching never recreates the WebView.
    LaunchedEffect(browser, ready, scene, dark) {
        if (ready) runCatching {
            browser?.evaluateJavascript("window.vericlueScene?.configure('${scene.wireName}', $dark)", null)
        }.onFailure { failed = true }
    }
    LaunchedEffect(browser, resumed, visible, ready) {
        browser?.let { view ->
            runCatching {
                if (resumed && visible) {
                    view.onResume()
                    view.evaluateJavascript("window.vericlueScene?.setActive(${ready})", null)
                } else {
                    view.evaluateJavascript("window.vericlueScene?.setActive(false)", null)
                    view.onPause()
                }
            }.onFailure { failed = true }
        }
    }
    Box(modifier.clearAndSetSemantics {}.onGloballyPositioned { visible = !it.boundsInWindow().isEmpty }) {
        if (!ready || failed) SceneFallback(scene, Modifier.fillMaxSize())
        if (!failed) AndroidView(
            modifier = Modifier.fillMaxSize(),
            factory = { context ->
                FrameLayout(context).apply host@ {
                    importantForAccessibility = View.IMPORTANT_FOR_ACCESSIBILITY_NO_HIDE_DESCENDANTS
                    var created: WebView? = null
                    // WebView may be absent or unavailable on a device. Keep the native fallback.
                    runCatching {
                        IllustrationWebView(context).also { created = it }.apply web@ {
                            alpha = 0f
                            setBackgroundColor(Color.TRANSPARENT)
                            isFocusable = false
                            isFocusableInTouchMode = false
                            isClickable = false
                            overScrollMode = View.OVER_SCROLL_NEVER
                            settings.apply {
                                javaScriptEnabled = true
                                allowFileAccess = false
                                allowContentAccess = false
                                domStorageEnabled = false
                                blockNetworkLoads = true
                                cacheMode = WebSettings.LOAD_NO_CACHE
                                mixedContentMode = WebSettings.MIXED_CONTENT_NEVER_ALLOW
                                javaScriptCanOpenWindowsAutomatically = false
                                setSupportMultipleWindows(false)
                                setSupportZoom(false)
                            }
                            webViewClient = object : WebViewClient() {
                                override fun shouldOverrideUrlLoading(view: WebView, request: WebResourceRequest) = true
                                override fun shouldInterceptRequest(view: WebView, request: WebResourceRequest): WebResourceResponse {
                                    val asset = if (request.method == "GET") ThreeAssetPolicy.asset(request.url.toString()) else null
                                    if (asset != null) {
                                        return runCatching {
                                            WebResourceResponse(asset.second, "UTF-8", context.assets.open(asset.first))
                                        }.getOrElse { deniedAsset() }
                                    }
                                    return deniedAsset()
                                }
                                override fun onReceivedError(view: WebView, request: WebResourceRequest, error: WebResourceError) {
                                    if (request.isForMainFrame && browser === view) failed = true
                                }
                                override fun onRenderProcessGone(view: WebView, detail: RenderProcessGoneDetail): Boolean {
                                    if (browser === view) failed = true
                                    return true
                                }
                            }
                            webChromeClient = object : WebChromeClient() {
                                override fun onPermissionRequest(request: PermissionRequest) { request.deny() }
                                override fun onConsoleMessage(message: ConsoleMessage): Boolean {
                                    if (message.message() == "vericlue-scene-fallback" && browser === this@web) failed = true
                                    return true
                                }
                            }
                            browser = this
                            this@host.addView(this, FrameLayout.LayoutParams(-1, -1))
                            loadUrl(ThreeAssetPolicy.PAGE)
                        }
                    }.onFailure {
                        created?.let { view -> removeView(view); runCatching { view.destroy() } }
                        browser = null
                        failed = true
                    }
                }
            },
            update = { host -> host.getChildAt(0)?.alpha = if (ready) 1f else 0f },
            onRelease = { host ->
                (host.getChildAt(0) as? WebView)?.let { view ->
                    if (browser === view) browser = null
                    host.removeView(view)
                    runCatching {
                        view.stopLoading()
                        view.evaluateJavascript("window.vericlueScene?.dispose()", null)
                    }
                    view.destroy()
                }
            },
        )
    }
}

private fun deniedAsset() = WebResourceResponse("text/plain", "UTF-8", 403, "Forbidden",
    emptyMap(), ByteArrayInputStream(ByteArray(0)))
