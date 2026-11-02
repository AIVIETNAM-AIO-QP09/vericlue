package vn.vericlue.app.screenshots

import app.cash.paparazzi.DeviceConfig
import app.cash.paparazzi.Paparazzi
import androidx.compose.foundation.ScrollState
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.material3.Text
import androidx.compose.ui.Modifier
import androidx.compose.ui.geometry.Rect
import androidx.compose.ui.layout.onGloballyPositioned
import androidx.compose.ui.layout.positionInRoot
import androidx.compose.ui.unit.toSize
import com.android.resources.Density
import com.android.resources.ScreenOrientation
import org.junit.Assert.assertTrue
import org.junit.Rule
import org.junit.Test
import vn.vericlue.app.ui.components.PrimaryButton
import vn.vericlue.app.ui.components.TitleBlock
import vn.vericlue.app.ui.components.VcScreen
import vn.vericlue.app.ui.theme.Vc
import vn.vericlue.app.ui.theme.VcTheme
import vn.vericlue.app.ui.theme.VcType

/** A long screen must retain a reachable footer even when text consumes most of the viewport. */
abstract class AdaptiveScreenSnapshots(private val device: DeviceConfig) {
    @get:Rule val paparazzi = Paparazzi(deviceConfig = device)

    @Test fun canScrollToTheEntirePrimaryAction() {
        val scroll = ScrollState(Int.MAX_VALUE)
        var button: Rect? = null
        paparazzi.snapshot("footer_reachable") {
            VcTheme(motionEnabled = false) {
                VcScreen(
                    onBack = {},
                    scrollState = scroll,
                    actions = {
                        PrimaryButton("Đồng ý và tiếp tục", {}, Modifier.onGloballyPositioned {
                            button = Rect(it.positionInRoot(), it.size.toSize())
                        })
                    },
                ) {
                    TitleBlock("Thông tin trước khi xác minh")
                    repeat(8) {
                        Text(
                            "Bạn có thể dừng xác minh thay vì tiếp tục cung cấp dữ liệu.",
                            modifier = Modifier.fillMaxWidth(), style = VcType.body, color = Vc.colors.ink,
                        )
                    }
                }
            }
        }
        val bounds = requireNotNull(button) { "Primary action was not laid out" }
        assertTrue("Reading content must remain scrollable", scroll.maxValue > 0 && scroll.value > 0)
        assertTrue("Primary action is above the visible viewport: $bounds", bounds.top >= 0f)
        assertTrue("Primary action is below the visible viewport: $bounds", bounds.bottom <= device.screenHeight)
        assertTrue("Touch target became too small: $bounds", bounds.height >= 48f)
    }
}

class LargeTextAdaptiveScreenSnapshotTest : AdaptiveScreenSnapshots(DeviceConfig(
    screenWidth = 375, screenHeight = 812, xdpi = 160, ydpi = 160, density = Density.MEDIUM, fontScale = 2f,
))

class ShortAdaptiveScreenSnapshotTest : AdaptiveScreenSnapshots(DeviceConfig(
    screenWidth = 600, screenHeight = 375, xdpi = 160, ydpi = 160, density = Density.MEDIUM,
    orientation = ScreenOrientation.LANDSCAPE,
))
