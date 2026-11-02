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

/** Decoration must never expose a player or chapter selection in citizen screens. */
abstract class SceneExperienceSnapshots(device: DeviceConfig) {
    @get:Rule val paparazzi = Paparazzi(deviceConfig = device)
    @Test fun decorationDoesNotAddControls() {
        for (dark in listOf(false, true)) for (screen in listOf("auth", "ready", "passive")) {
            var texts = emptyList<String>()
            var tabs = 0
            paparazzi.snapshot("${screen}_$dark") {
                VcTheme(dark = dark, motionEnabled = false) {
                    val root = LocalView.current as RootForTest
                    Column(Modifier.onGloballyPositioned {
                        val nodes = root.semanticsOwner.getAllSemanticsNodes(mergingEnabled = true)
                        texts = nodes.flatMap { it.config.getOrNull(SemanticsProperties.Text)?.map { text -> text.text } ?: emptyList() }
                        tabs = nodes.count { it.config.getOrNull(SemanticsProperties.Role) == Role.Tab }
                    }) {
                        if (screen == "auth") vn.vericlue.app.ui.screens.AuthScreen({}, {}, {})
                        else vn.vericlue.app.ui.screens.FaceReadyScreen({}, {}, {}, usesLightChallenge = screen != "passive")
                    }
                }
            }
            assertEquals(0, tabs)
            assertTrue("Primary action must remain present", texts.contains(if (screen == "auth") "Bắt đầu đăng ký" else "Bắt đầu"))
            assertFalse(texts.any { it == "Xem lại" || it == "Tạm dừng" || it.contains("Chọn từng mục") })
            if (screen == "passive") assertFalse(texts.any { it.contains("đổi màu") || it.contains("nhạy cảm") })
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
