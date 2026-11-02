package vn.vericlue.app.screenshots

import app.cash.paparazzi.DeviceConfig
import app.cash.paparazzi.Paparazzi
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.ComposeView
import com.android.resources.Density
import org.junit.Rule
import org.junit.Test
import vn.vericlue.app.flow.TurnDir
import vn.vericlue.app.ui.components.HeadMotionGuide
import vn.vericlue.app.ui.theme.Vc
import vn.vericlue.app.ui.theme.VcTheme

/** Native motion evidence plus complete/reduced-motion states, without camera access. */
class HeadMotionGuideSnapshotTest {
    @get:Rule val paparazzi = Paparazzi(deviceConfig = DeviceConfig(
        screenWidth = 160, screenHeight = 104, xdpi = 160, ydpi = 160, density = Density.MEDIUM,
    ))

    @Test fun everyDirectionRemainsClearWithoutMotion() {
        for (dark in listOf(false, true)) for (direction in listOf(TurnDir.Left, TurnDir.Right, null)) {
            for (progress in listOf(0f, 1f)) paparazzi.snapshot("${direction}_${dark}_$progress") {
                VcTheme(dark = dark, motionEnabled = false) {
                    Box(Modifier.fillMaxSize().background(Vc.colors.background), contentAlignment = Alignment.Center) {
                        HeadMotionGuide(direction, progress)
                    }
                }
            }
        }
    }

    @Test fun demonstrateLeftThenHold() = record(TurnDir.Left, dark = true)
    @Test fun demonstrateRightThenHold() = record(TurnDir.Right, dark = false)
    @Test fun demonstrateReturnToCenterThenHold() = record(null, dark = true)

    private fun record(direction: TurnDir?, dark: Boolean) {
        val view = ComposeView(paparazzi.context).apply {
            setContent {
                VcTheme(dark = dark, motionEnabled = true) {
                    Box(Modifier.fillMaxSize().background(Vc.colors.background), contentAlignment = Alignment.Center) {
                        HeadMotionGuide(direction, 0f)
                    }
                }
            }
        }
        // A fresh Paparazzi clock per test; last frames document the stable held pose.
        try {
            paparazzi.gif(view, name = "head_${direction}_$dark", end = 1800L, fps = 20)
        } finally {
            view.disposeComposition()
        }
    }
}
