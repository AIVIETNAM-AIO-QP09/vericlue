package vn.vericlue.app.screenshots

import app.cash.paparazzi.DeviceConfig
import app.cash.paparazzi.Paparazzi
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.runtime.CompositionLocalProvider
import androidx.compose.ui.Modifier
import androidx.compose.ui.geometry.Rect
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.geometry.Size
import androidx.compose.ui.layout.boundsInRoot
import androidx.compose.ui.layout.onGloballyPositioned
import androidx.compose.ui.layout.positionInParent
import androidx.compose.ui.unit.toSize
import androidx.compose.ui.node.RootForTest
import androidx.compose.ui.platform.LocalView
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
                    CompositionLocalProvider(LocalCameraFeed provides { modifier ->
                        // Drawing transforms may shrink the selfie; CameraX must keep its layout size.
                        Box(modifier.onGloballyPositioned { preview = Rect(it.positionInParent(), it.size.toSize()) }) { FakeCameraFeed(centerYFraction = 0.5f) }
                    }) {
                        Box(Modifier.fillMaxSize().onGloballyPositioned {
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
                assertEquals(requireNotNull(guide).center.x, requireNotNull(reportedGuide).center.x, 1f)
                assertEquals(requireNotNull(guide).center.y, requireNotNull(reportedGuide).center.y, 1f)
            }
            assertEquals("Preview changed in phase $phase", expectedPreview, actualPreview)
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
