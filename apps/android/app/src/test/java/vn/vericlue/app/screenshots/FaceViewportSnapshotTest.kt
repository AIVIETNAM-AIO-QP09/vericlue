package vn.vericlue.app.screenshots

import app.cash.paparazzi.DeviceConfig
import app.cash.paparazzi.Paparazzi
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.WindowInsets
import androidx.compose.foundation.layout.statusBars
import androidx.compose.foundation.layout.navigationBars
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.runtime.CompositionLocalProvider
import androidx.compose.ui.Modifier
import androidx.compose.ui.geometry.Rect
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.geometry.Size
import androidx.compose.ui.layout.onGloballyPositioned
import androidx.compose.ui.layout.positionInParent
import androidx.compose.ui.unit.toSize
import androidx.compose.ui.node.RootForTest
import androidx.compose.ui.platform.LocalView
import androidx.compose.ui.platform.LocalDensity
import androidx.compose.ui.semantics.*
import com.android.resources.Density
import com.android.resources.ScreenOrientation
import org.junit.Assert.*
import org.junit.Rule
import org.junit.Test
import vn.vericlue.app.capture.FaceTimeline
import vn.vericlue.app.flow.FramingState
import vn.vericlue.app.flow.TurnDir
import vn.vericlue.app.ui.components.FakeCameraFeed
import vn.vericlue.app.ui.components.LocalCameraFeed
import vn.vericlue.app.ui.components.faceSourceGuideRect
import vn.vericlue.app.ui.screens.FaceChallengeContent
import vn.vericlue.app.ui.screens.FramingScreen
import vn.vericlue.app.ui.theme.VcTheme

/** Compare measured native layouts, including the real camera host's supplied modifier. */
abstract class FaceViewportSnapshots(device: DeviceConfig) {
    @get:Rule val paparazzi = Paparazzi(deviceConfig = device)
    @Test fun cameraAndGuideDoNotJumpBetweenPhases() {
        val timeline = FaceTimeline.demo(listOf(TurnDir.Left, TurnDir.Right))
        val phases = listOf(null, FaceTimeline.Phase.Colour(0), FaceTimeline.Phase.Colour(2), FaceTimeline.Phase.Gap,
            FaceTimeline.Phase.Gaze(0.25, 0.55), FaceTimeline.Phase.Gaze(0.75, 0.35),
            FaceTimeline.Phase.Head(0, TurnDir.Left), FaceTimeline.Phase.Head(1, TurnDir.Right), FaceTimeline.Phase.Head(2, null))
        var expectedPreview: Rect? = null
        var expectedGuide: Rect? = null
        phases.forEachIndexed { index, phase ->
            var preview: Rect? = null
            var previewSourceDrawing: Rect? = null
            var sourceGuide: Rect? = null
            var guide: Rect? = null
            var thumbnail: Rect? = null
            var dot: Rect? = null
            var header: Rect? = null
            var footer: Rect? = null
            var reportedGuide: Rect? = null
            var reportedViewport: Size? = null
            paparazzi.snapshot("phase_$index") {
                VcTheme(motionEnabled = false) {
                    val root = LocalView.current as RootForTest
                    val density = LocalDensity.current
                    val topInset = WindowInsets.statusBars.getTop(density).toFloat()
                    val bottomInset = WindowInsets.navigationBars.getBottom(density).toFloat()
                    CompositionLocalProvider(LocalCameraFeed provides { modifier ->
                        // Drawing transforms may shrink the selfie; CameraX must keep its layout size.
                        Box(modifier.onGloballyPositioned {
                            preview = Rect(it.positionInParent(), it.size.toSize())
                            val localSource = faceSourceGuideRect(it.size.width.toFloat(), it.size.height.toFloat(),
                                density.density, topInset, bottomInset)
                            val first = it.localToRoot(localSource.topLeft)
                            val last = it.localToRoot(localSource.bottomRight)
                            previewSourceDrawing = Rect(first.x, first.y, last.x, last.y)
                        }) { FakeCameraFeed(centerYFraction = 0.5f) }
                    }) {
                        Box(Modifier.fillMaxSize().onGloballyPositioned {
                            sourceGuide = faceSourceGuideRect(it.size.width.toFloat(), it.size.height.toFloat(),
                                density.density, topInset, bottomInset)
                            val nodes = root.semanticsOwner.getAllSemanticsNodes(mergingEnabled = false)
                            guide = nodes.firstOrNull { it.config.getOrNull(SemanticsProperties.TestTag) == "face-guide" }?.boundsInRoot
                            thumbnail = nodes.firstOrNull { it.config.getOrNull(SemanticsProperties.TestTag) == "face-preview-thumbnail" }?.boundsInRoot
                            dot = nodes.firstOrNull { it.config.getOrNull(SemanticsProperties.TestTag) == "face-gaze-target" }?.boundsInRoot
                            header = nodes.firstOrNull { it.config.getOrNull(SemanticsProperties.TestTag) == "face-instruction-header" }?.boundsInRoot
                            footer = nodes.firstOrNull { it.config.getOrNull(SemanticsProperties.TestTag) == "face-action-footer" }?.boundsInRoot
                        }) {
                            if (phase == null) FramingScreen({}, {}, live = FramingState.Good, auto = false,
                                onGuidePosition = { rect, size -> reportedGuide = rect; reportedViewport = size })
                            else FaceChallengeContent(timeline, phase) {}
                        }
                    }
                }
            }
            val actualPreview = requireNotNull(preview)
            if (index == 0) { expectedPreview = actualPreview; expectedGuide = requireNotNull(guide) }
            if (phase == null) {
                assertEquals(actualPreview.size, requireNotNull(reportedViewport))
                assertEquals("Framing must report camera coordinates, independent of display text size",
                    requireNotNull(sourceGuide), requireNotNull(reportedGuide))
            }
            assertEquals("Preview changed in phase $phase", expectedPreview, actualPreview)
            val aperture = requireNotNull(if (phase is FaceTimeline.Phase.Gaze) thumbnail else guide)
            val drawn = requireNotNull(previewSourceDrawing)
            // Map the accepted source corners through the real native drawing transform.
            // Compare at the aperture: inferring scale from rounded semantics amplifies error
            // over the full host, and boundsInRoot clips enlarged landscape previews.
            assertEquals("Projected source left differs from aperture in $phase", aperture.left, drawn.left, 1f)
            assertEquals("Projected source top differs from aperture in $phase", aperture.top, drawn.top, 1f)
            assertEquals("Projected source right differs from aperture in $phase", aperture.right, drawn.right, 1f)
            assertEquals("Projected source bottom differs from aperture in $phase", aperture.bottom, drawn.bottom, 1f)
            if (phase is FaceTimeline.Phase.Gaze) {
                assertNull("Gaze should release the main view", guide)
                val small = requireNotNull(thumbnail)
                assertTrue(small.width <= 93 && small.width > 0)
                assertTrue(small.left > actualPreview.width / 2f && small.bottom < actualPreview.height)
                val target = requireNotNull(dot)
                assertEquals((actualPreview.left + actualPreview.width * phase.x).toFloat(), target.center.x, 1f)
                assertEquals((actualPreview.top + actualPreview.height * phase.y).toFloat(), target.center.y, 1f)
            } else {
                assertNull(thumbnail)
                val actualGuide = requireNotNull(guide)
                assertEquals("Main oval did not restore in phase $phase", expectedGuide, actualGuide)
                assertTrue(actualGuide.width > 0 && actualGuide.height > 0)
                assertTrue("Header overlaps oval in phase $phase", actualGuide.top >= requireNotNull(header).bottom)
                assertTrue("Footer overlaps oval in phase $phase", actualGuide.bottom <= requireNotNull(footer).top)
            }
        }
    }
}
class CompactFaceViewportSnapshotTest : FaceViewportSnapshots(DeviceConfig(
    screenWidth = 375, screenHeight = 812, xdpi = 160, ydpi = 160, density = Density.MEDIUM,
))
class LargeTextFaceViewportSnapshotTest : FaceViewportSnapshots(DeviceConfig(
    screenWidth = 375, screenHeight = 812, xdpi = 160, ydpi = 160, density = Density.MEDIUM, fontScale = 2f,
))
class LandscapeFaceViewportSnapshotTest : FaceViewportSnapshots(DeviceConfig(
    screenWidth = 812, screenHeight = 375, xdpi = 160, ydpi = 160, density = Density.MEDIUM,
    orientation = ScreenOrientation.LANDSCAPE,
))
