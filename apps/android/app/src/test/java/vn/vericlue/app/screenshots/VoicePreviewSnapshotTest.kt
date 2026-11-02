package vn.vericlue.app.screenshots

import android.os.Handler
import android.os.Looper
import android.view.Choreographer
import app.cash.paparazzi.DeviceConfig
import app.cash.paparazzi.HtmlReportWriter
import app.cash.paparazzi.Paparazzi
import app.cash.paparazzi.Snapshot
import app.cash.paparazzi.SnapshotHandler
import androidx.compose.foundation.Canvas
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.runtime.CompositionLocalProvider
import androidx.compose.runtime.DisposableEffect
import androidx.compose.runtime.Recomposer
import androidx.compose.ui.Modifier
import androidx.compose.ui.geometry.Rect
import androidx.compose.ui.geometry.Size
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.layout.onGloballyPositioned
import androidx.compose.ui.node.RootForTest
import androidx.compose.ui.platform.ComposeView
import androidx.compose.ui.platform.AndroidUiFrameClock
import androidx.compose.ui.platform.LocalView
import androidx.compose.ui.semantics.SemanticsProperties
import androidx.compose.ui.semantics.getAllSemanticsNodes
import androidx.compose.ui.semantics.getOrNull
import androidx.compose.ui.unit.toSize
import com.android.resources.Density
import java.lang.reflect.Proxy
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.CoroutineStart
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.android.asCoroutineDispatcher
import kotlinx.coroutines.cancel
import kotlinx.coroutines.launch
import org.junit.Assert.*
import org.junit.Rule
import org.junit.Test
import vn.vericlue.app.ui.components.LocalCameraFeed
import vn.vericlue.app.ui.screens.VoiceScreen
import vn.vericlue.app.ui.theme.VcTheme

class VoicePreviewSnapshotTest {
    private var thumbnail: Rect? = null
    private var centerRgb = 0
    private val reports = HtmlReportWriter()
    @get:Rule val paparazzi = Paparazzi(deviceConfig = DeviceConfig(
        screenWidth = 375, screenHeight = 812, xdpi = 160, ydpi = 160, density = Density.MEDIUM,
    ), snapshotHandler = object : SnapshotHandler {
        override fun close() = reports.close()
        override fun newFrameHandler(snapshot: Snapshot, frameCount: Int, fps: Int): SnapshotHandler.FrameHandler {
            val delegate = reports.newFrameHandler(snapshot, frameCount, fps)
            // The renderer supplies a JDK BufferedImage at runtime; Android's compile
            // bootclasspath omits AWT, so intercept it without importing that type.
            val handler = SnapshotHandler.FrameHandler::class.java
            return Proxy.newProxyInstance(handler.classLoader, arrayOf(handler)) { _, method, arguments ->
                if (method.name == "handle") {
                    val image = requireNotNull(arguments?.firstOrNull())
                    thumbnail?.let {
                        centerRgb = (image.javaClass.getMethod("getRGB", Integer.TYPE, Integer.TYPE)
                            .invoke(image, it.center.x.toInt(), it.center.y.toInt()) as Int) and 0xffffff
                    }
                }
                method.invoke(delegate, *(arguments ?: emptyArray()))
            } as SnapshotHandler.FrameHandler
        }
    })

    @Test fun nativeViewportCenterIsVisibleInTheThumbnailWithoutResizingTheHost() {
        var hostSize: Size? = null
        var mounts = 0
        var disposals = 0
        // Measuring the thumbnail schedules another composition. Keep its frame
        // callbacks local to this recording when Paparazzi resets Layoutlib time.
        val dispatcher = Handler(Looper.getMainLooper())
            .asCoroutineDispatcher("VoicePreviewSnapshot").immediate
        val scope = CoroutineScope(
            SupervisorJob() + dispatcher + AndroidUiFrameClock(Choreographer.getInstance()),
        )
        val recomposer = Recomposer(scope.coroutineContext)
        scope.launch(start = CoroutineStart.UNDISPATCHED) {
            recomposer.runRecomposeAndApplyChanges()
        }
        val view = ComposeView(paparazzi.context).apply {
            setParentCompositionContext(recomposer)
            setContent {
            val root = LocalView.current as RootForTest
            VcTheme(motionEnabled = false) {
                CompositionLocalProvider(LocalCameraFeed provides { modifier ->
                    DisposableEffect(Unit) { mounts++; onDispose { disposals++ } }
                    Canvas(modifier.onGloballyPositioned { hostSize = it.size.toSize() }) {
                        drawRect(Color.Blue)
                        drawCircle(Color.Red, radius = 60f)
                    }
                }) {
                    Box(Modifier.fillMaxSize().onGloballyPositioned {
                        thumbnail = root.semanticsOwner.getAllSemanticsNodes(mergingEnabled = false)
                            .firstOrNull { it.config.getOrNull(SemanticsProperties.TestTag) == "voice-preview-thumbnail" }?.boundsInRoot
                    }) { VoiceScreen({}, {}) }
                }
            }
            }
        }
        try { paparazzi.gif(view, "whole_viewport_preview", end = 200L, fps = 20) }
        finally {
            view.disposeComposition()
            recomposer.cancel()
            scope.cancel()
        }
        assertNotNull(thumbnail)
        assertEquals(Size(375f, 812f), hostSize)
        assertEquals(1, mounts)
        assertEquals(1, disposals)
        assertEquals("The center face marker must appear inside the thumbnail", 0xff0000, centerRgb)
    }
}
