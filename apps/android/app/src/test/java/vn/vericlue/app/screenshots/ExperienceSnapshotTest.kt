package vn.vericlue.app.screenshots

import app.cash.paparazzi.DeviceConfig
import app.cash.paparazzi.Paparazzi
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.*
import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import androidx.compose.ui.layout.onGloballyPositioned
import androidx.compose.ui.node.RootForTest
import androidx.compose.ui.platform.LocalView
import androidx.compose.ui.semantics.SemanticsProperties
import androidx.compose.ui.semantics.getAllSemanticsNodes
import androidx.compose.ui.semantics.getOrNull
import com.android.resources.Density
import com.android.resources.ScreenOrientation
import org.junit.Assert.assertTrue
import org.junit.Rule
import org.junit.Test
import vn.vericlue.app.ui.components.*
import vn.vericlue.app.ui.screens.PhoneScreen
import vn.vericlue.app.ui.screens.OtpScreen
import vn.vericlue.app.ui.theme.Vc
import vn.vericlue.app.ui.theme.VcTheme

abstract class ExperienceSnapshots(device: DeviceConfig) {
    @get:Rule val paparazzi = Paparazzi(deviceConfig = device)

    private fun shot(name: String, dark: Boolean, content: @Composable () -> Unit) {
        paparazzi.snapshot("${name}_$dark") {
            VcTheme(dark = dark, motionEnabled = false) {
                Box(Modifier.fillMaxSize().background(Vc.colors.background)) { content() }
            }
        }
    }

    @Test fun formsAndContextualHelp() {
        for (dark in listOf(false, true)) {
            shot("phone_ready", dark) { PhoneScreen({}, {}, initialPhone = "0900000000") }
            shot("phone_invalid", dark) { PhoneScreen({}, {}, initialPhone = "1900000000") }
            shot("phone_busy", dark) { PhoneScreen({}, {}, busy = true, initialPhone = "0900000000") }
            shot("otp_busy", dark) { OtpScreen({}, {}, busy = true, autoCode = "001234") }
            HelpTopic.entries.forEach { topic ->
                shot("help_${topic.name}", dark) { HelpSheetContent(topic, step = 2, onClose = {}) }
            }
        }
    }
}

class CompactExperienceSnapshotTest : ExperienceSnapshots(DeviceConfig(
    screenWidth = 375, screenHeight = 812, xdpi = 160, ydpi = 160, density = Density.MEDIUM,
))

class LargeTextExperienceSnapshotTest : ExperienceSnapshots(DeviceConfig(
    screenWidth = 375, screenHeight = 812, xdpi = 160, ydpi = 160, density = Density.MEDIUM, fontScale = 2f,
))

class LandscapeExperienceSnapshotTest : ExperienceSnapshots(DeviceConfig(
    screenWidth = 812, screenHeight = 375, xdpi = 160, ydpi = 160, density = Density.MEDIUM,
    orientation = ScreenOrientation.LANDSCAPE,
))

/** The actual Compose control must expose disabled/busy state to accessibility services. */
class BusyActionSnapshotTest {
    @get:Rule val paparazzi = Paparazzi(deviceConfig = DeviceConfig.PIXEL_5)

    @Test fun busyActionAndKeypadAreDisabled() {
        var foundBusy = false
        var disabledCount = 0
        paparazzi.snapshot("busy_controls") {
            VcTheme(motionEnabled = false) {
                val root = LocalView.current as RootForTest
                Column(Modifier.onGloballyPositioned {
                    val nodes = root.semanticsOwner.getAllSemanticsNodes(mergingEnabled = true)
                    foundBusy = nodes.any { it.config.getOrNull(SemanticsProperties.StateDescription) == "Đang xử lý" &&
                        it.config.contains(SemanticsProperties.Disabled) }
                    disabledCount = nodes.count { it.config.contains(SemanticsProperties.Disabled) }
                }) {
                    PrimaryButton("Đang gửi mã…", { error("Busy action submitted") }, loading = true)
                    NumericKeypad({}, {}, {}, enabled = false)
                }
            }
        }
        assertTrue("Busy action must announce that it is disabled and processing", foundBusy)
        assertTrue("All 12 keypad keys and the busy action must be disabled", disabledCount >= 13)
    }
}
