package vn.vericlue.app.screenshots

import app.cash.paparazzi.DeviceConfig
import app.cash.paparazzi.Paparazzi
import androidx.compose.foundation.layout.Column
import androidx.compose.ui.Modifier
import androidx.compose.ui.layout.onGloballyPositioned
import androidx.compose.ui.node.RootForTest
import androidx.compose.ui.platform.LocalView
import androidx.compose.ui.semantics.*
import com.android.resources.Density
import com.android.resources.ScreenOrientation
import org.junit.Assert.*
import org.junit.Rule
import org.junit.Test
import vn.vericlue.app.ui.components.*
import vn.vericlue.app.ui.theme.VcTheme

/** Native content remains complete and selectable without creating a WebView. */
abstract class SceneExperienceSnapshots(device: DeviceConfig) {
    @get:Rule val paparazzi = Paparazzi(deviceConfig = device)

    @Test fun chapterControlsAndReducedMotionFallbacks() {
        for (dark in listOf(false, true)) {
            for ((preparation, scene) in listOf(false to IllustrationScene.Card, false to IllustrationScene.Face,
                false to IllustrationScene.Voice, true to IllustrationScene.Face, true to IllustrationScene.Eyes,
                true to IllustrationScene.Turn)) {
                var tabs = 0
                var selected = 0
                var disabled = 0
                var readable = false
                var minimumTouchHeight = Float.MAX_VALUE
                paparazzi.snapshot("${preparation}_${scene.name}_$dark") {
                    VcTheme(dark = dark, motionEnabled = false) {
                        val root = LocalView.current as RootForTest
                        VcScreen {
                            Column(Modifier.onGloballyPositioned {
                                val nodes = root.semanticsOwner.getAllSemanticsNodes(mergingEnabled = true)
                                val controls = nodes.filter { it.config.getOrNull(SemanticsProperties.Role) == Role.Tab }
                                tabs = controls.size
                                selected = controls.count { it.config.getOrNull(SemanticsProperties.Selected) == true }
                                minimumTouchHeight = controls.minOfOrNull { it.boundsInRoot.height } ?: 0f
                                disabled = nodes.count { it.config.contains(SemanticsProperties.Disabled) }
                                readable = nodes.any { node -> node.config.getOrNull(SemanticsProperties.Text)
                                    ?.any { it.text == scene.explanation } == true }
                            }) { SceneExplorer(preparation, scene) }
                        }
                    }
                }
                assertEquals("All native chapter controls remain available", 3, tabs)
                assertEquals("Exactly one chapter announces selection", 1, selected)
                assertTrue("Native explanation survives WebGL fallback", readable)
                assertTrue("Motion controls respect reduced motion", disabled >= 2)
                assertTrue("Tab touch target must be at least 48dp", minimumTouchHeight >= 48f)
            }
        }
    }
}

class CompactSceneExperienceSnapshotTest : SceneExperienceSnapshots(DeviceConfig(
    screenWidth = 375, screenHeight = 812, xdpi = 160, ydpi = 160, density = Density.MEDIUM,
))
class LargeTextSceneExperienceSnapshotTest : SceneExperienceSnapshots(DeviceConfig(
    screenWidth = 375, screenHeight = 812, xdpi = 160, ydpi = 160, density = Density.MEDIUM, fontScale = 2f,
))
class LandscapeSceneExperienceSnapshotTest : SceneExperienceSnapshots(DeviceConfig(
    screenWidth = 812, screenHeight = 375, xdpi = 160, ydpi = 160, density = Density.MEDIUM,
    orientation = ScreenOrientation.LANDSCAPE,
))
