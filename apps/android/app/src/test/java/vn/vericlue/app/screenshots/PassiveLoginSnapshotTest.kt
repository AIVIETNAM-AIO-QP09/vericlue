package vn.vericlue.app.screenshots

import app.cash.paparazzi.DeviceConfig
import app.cash.paparazzi.Paparazzi
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.ui.Modifier
import androidx.compose.ui.geometry.Rect
import androidx.compose.ui.layout.onGloballyPositioned
import androidx.compose.ui.node.RootForTest
import androidx.compose.ui.platform.LocalView
import androidx.compose.ui.semantics.*
import com.android.resources.Density
import org.junit.Assert.*
import org.junit.Rule
import org.junit.Test
import vn.vericlue.app.capture.FaceTimeline
import vn.vericlue.app.flow.FramingState
import vn.vericlue.app.ui.screens.FaceChallengeContent
import vn.vericlue.app.ui.screens.FramingScreen
import vn.vericlue.app.ui.theme.VcTheme

/** Short login must retain the accepted oval and distinguish capture progress from a verdict. */
abstract class PassiveLoginSnapshots(device: DeviceConfig) {
    @get:Rule val paparazzi = Paparazzi(deviceConfig = device)

    @Test fun stableFramingAndHonestProgress() {
        var expectedGuide: Rect? = null
        for (motion in listOf(false, true)) {
            for (progress in listOf(null, 0f, 0.5f, 1f)) {
                var guide: Rect? = null
                var header: Rect? = null
                var footer: Rect? = null
                var capture: ProgressBarRangeInfo? = null
                var texts = emptyList<String>()
                paparazzi.snapshot("login_${progress ?: "framing"}_motion_$motion") {
                    VcTheme(motionEnabled = motion) {
                        val root = LocalView.current as RootForTest
                        Box(Modifier.fillMaxSize().onGloballyPositioned {
                            val nodes = root.semanticsOwner.getAllSemanticsNodes(mergingEnabled = false)
                            fun tagged(tag: String) = nodes.firstOrNull {
                                it.config.getOrNull(SemanticsProperties.TestTag) == tag
                            }
                            guide = tagged("face-guide")?.boundsInRoot
                            header = tagged("face-instruction-header")?.boundsInRoot
                            footer = tagged("face-action-footer")?.boundsInRoot
                            capture = tagged("face-login-capture")?.config?.getOrNull(SemanticsProperties.ProgressBarRangeInfo)
                            texts = nodes.flatMap { it.config.getOrNull(SemanticsProperties.Text)?.map { text -> text.text } ?: emptyList() }
                        }) {
                            if (progress == null) FramingScreen({}, {}, live = FramingState.Good, reauth = true)
                            else FaceChallengeContent(FaceTimeline.passive(), FaceTimeline.Phase.Colour(0),
                                remainingSeconds = null, captureProgress = progress, onStop = {})
                        }
                    }
                }
                val aperture = requireNotNull(guide)
                if (expectedGuide == null) expectedGuide = aperture
                assertEquals("Accepted framing must not jump when recording begins", expectedGuide, aperture)
                assertTrue(aperture.top >= requireNotNull(header).bottom)
                assertTrue(aperture.bottom <= requireNotNull(footer).top)
                assertTrue(texts.contains("Đăng nhập khuôn mặt"))
                assertTrue(texts.contains("Dừng đăng nhập"))
                assertFalse(texts.any { it.contains("Quay sang") || it.contains("Bước") ||
                    it.contains("thành công", ignoreCase = true) || it == "Dừng xác minh" })
                if (progress == null) assertNull(capture)
                else assertEquals("Reduced motion must preserve real capture progress", progress, requireNotNull(capture).current)
            }
        }
    }
}

class PassiveLoginSnapshotTest : PassiveLoginSnapshots(DeviceConfig(
    screenWidth = 375, screenHeight = 812, xdpi = 160, ydpi = 160, density = Density.MEDIUM,
))

class LargeTextPassiveLoginSnapshotTest : PassiveLoginSnapshots(DeviceConfig(
    screenWidth = 375, screenHeight = 812, xdpi = 160, ydpi = 160, density = Density.MEDIUM, fontScale = 2f,
))
