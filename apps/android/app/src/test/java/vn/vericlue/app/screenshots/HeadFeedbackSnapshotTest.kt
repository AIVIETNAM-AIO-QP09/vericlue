package vn.vericlue.app.screenshots

import app.cash.paparazzi.DeviceConfig
import app.cash.paparazzi.Paparazzi
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.ui.Modifier
import androidx.compose.ui.geometry.Rect
import androidx.compose.ui.layout.onGloballyPositioned
import androidx.compose.ui.node.RootForTest
import androidx.compose.ui.platform.ComposeView
import androidx.compose.ui.platform.LocalView
import androidx.compose.ui.semantics.LiveRegionMode
import androidx.compose.ui.semantics.SemanticsActions
import androidx.compose.ui.semantics.SemanticsProperties
import androidx.compose.ui.semantics.getAllSemanticsNodes
import androidx.compose.ui.semantics.getOrNull
import androidx.compose.ui.text.TextLayoutResult
import com.android.resources.Density
import com.android.resources.ScreenOrientation
import org.junit.Assert.*
import org.junit.Rule
import org.junit.Test
import vn.vericlue.app.capture.HeadCaptureState
import vn.vericlue.app.capture.HeadFeedback
import vn.vericlue.app.capture.hint
import vn.vericlue.app.flow.TurnDir
import vn.vericlue.app.ui.components.FaceCaptureSurface
import vn.vericlue.app.ui.components.Tone
import vn.vericlue.app.ui.theme.VcTheme

/** Inline corrections replace the hint; they must not move the face guide or jump the footer. */
abstract class HeadFeedbackSnapshots(device: DeviceConfig) {
    @get:Rule val paparazzi = Paparazzi(deviceConfig = device)

    @Test fun correctionsStayReadableAndKeepTheirFootprint() {
        val cases = HeadFeedback.entries.flatMap { feedback ->
            val directions = when (feedback) {
                HeadFeedback.Turn -> listOf(TurnDir.Left, TurnDir.Right, null)
                HeadFeedback.Further, HeadFeedback.WrongDirection -> listOf(TurnDir.Left, TurnDir.Right)
                else -> listOf(TurnDir.Left)
            }
            directions.map { direction -> HeadCaptureState(0, direction,
                if (feedback == HeadFeedback.Complete) 1f else if (feedback == HeadFeedback.Hold) 0.5f else 0f,
                feedback) }
        }
        var expectedGuide: Rect? = null
        var expectedFooter: Rect? = null
        cases.forEachIndexed { index, state ->
            val feedback = state.hint()
            val tone = if (state.feedback in setOf(HeadFeedback.Hold, HeadFeedback.Complete)) Tone.Ok else Tone.Info
            var guide: Rect? = null
            var footer: Rect? = null
            var announcement: LiveRegionMode? = null
            val layouts = mutableListOf<TextLayoutResult>()
            val view = ComposeView(paparazzi.context).apply {
                setContent {
                    VcTheme(motionEnabled = false) {
                        val root = LocalView.current as RootForTest
                        Box(Modifier.fillMaxSize().onGloballyPositioned {
                            val nodes = root.semanticsOwner.getAllSemanticsNodes(mergingEnabled = false)
                            guide = nodes.firstOrNull { it.config.getOrNull(SemanticsProperties.TestTag) == "face-guide" }?.boundsInRoot
                            footer = nodes.firstOrNull { it.config.getOrNull(SemanticsProperties.TestTag) == "face-action-footer" }?.boundsInRoot
                            announcement = nodes.firstOrNull { it.config.getOrNull(SemanticsProperties.TestTag) == "face-inline-feedback" }
                                ?.config?.getOrNull(SemanticsProperties.LiveRegion)
                            nodes.firstOrNull { node -> node.config.getOrNull(SemanticsProperties.Text)?.any { text -> text.text == feedback } == true }
                                ?.config?.getOrNull(SemanticsActions.GetTextLayoutResult)?.action?.invoke(layouts)
                        }) {
                            FaceCaptureSurface(
                                title = "Quay sang trái", hint = "Giữ điện thoại cố định", onStop = {},
                                direction = state.direction, headGuidance = true,
                                actionProgress = state.progress,
                                feedback = feedback, feedbackTone = tone,
                            )
                        }
                    }
                }
            }
            // Each case owns its composition; do not leak animation state into later motion tests.
            try {
                paparazzi.snapshot(view, name = "feedback_$index")
            } finally {
                view.disposeComposition()
            }
            if (index == 0) { expectedGuide = requireNotNull(guide); expectedFooter = requireNotNull(footer) }
            assertEquals(expectedGuide, requireNotNull(guide))
            assertEquals(expectedFooter, requireNotNull(footer))
            assertTrue(requireNotNull(guide).bottom <= requireNotNull(footer).top)
            assertEquals(LiveRegionMode.Polite, announcement)
            assertTrue("Feedback text layout is available", layouts.isNotEmpty())
            assertTrue("Feedback wraps beyond its stable two-line slot", layouts.last().lineCount <= 2)
            assertFalse(layouts.last().hasVisualOverflow)
        }
    }
}

class CompactHeadFeedbackSnapshotTest : HeadFeedbackSnapshots(DeviceConfig(
    screenWidth = 375, screenHeight = 812, xdpi = 160, ydpi = 160, density = Density.MEDIUM,
))
class LargeTextHeadFeedbackSnapshotTest : HeadFeedbackSnapshots(DeviceConfig(
    screenWidth = 375, screenHeight = 812, xdpi = 160, ydpi = 160, density = Density.MEDIUM, fontScale = 2f,
))
class LandscapeHeadFeedbackSnapshotTest : HeadFeedbackSnapshots(DeviceConfig(
    screenWidth = 812, screenHeight = 375, xdpi = 160, ydpi = 160, density = Density.MEDIUM,
    orientation = ScreenOrientation.LANDSCAPE,
))
