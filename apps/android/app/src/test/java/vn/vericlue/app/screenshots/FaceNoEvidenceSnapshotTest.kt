package vn.vericlue.app.screenshots

import app.cash.paparazzi.DeviceConfig
import app.cash.paparazzi.Paparazzi
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.ui.platform.ComposeView
import com.android.resources.Density
import kotlinx.coroutines.delay
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Rule
import org.junit.Test
import vn.vericlue.app.flow.TurnDir
import vn.vericlue.app.ui.screens.FramingScreen
import vn.vericlue.app.ui.screens.TurnHeadScreen
import vn.vericlue.app.ui.theme.VcTheme

/** A camera without evidence must not fall back to the old gallery timers. */
class FaceNoEvidenceSnapshotTest {
    @get:Rule val paparazzi = Paparazzi(deviceConfig = DeviceConfig(
        screenWidth = 320, screenHeight = 640, xdpi = 160, ydpi = 160, density = Density.MEDIUM,
    ))

    @Test fun framingWithoutLiveFaceNeverCapturesByDefault() {
        var captures = 0
        advanceEightSeconds("framing_no_face") {
            // Deliberately omit auto/live: the public default must remain safe while a camera loads.
            FramingScreen(onExit = {}, onCaptured = { captures++ })
        }
        assertEquals("Missing camera evidence must not become a successful framing step", 0, captures)
    }

    @Test fun headWithoutYawNeverCompletesOnTheOldTimer() {
        var completions = 0
        advanceEightSeconds("head_no_yaw") {
            TurnHeadScreen(order = listOf(TurnDir.Left, TurnDir.Right), onExit = {}, onDone = { completions++ })
        }
        assertEquals("Elapsed time must not stand in for a measured head turn", 0, completions)
    }

    private fun advanceEightSeconds(name: String, content: @Composable () -> Unit) {
        var clockAdvanced = false
        val view = ComposeView(paparazzi.context).apply {
            setContent {
                VcTheme(motionEnabled = false) {
                    LaunchedEffect(Unit) {
                        delay(6500)
                        clockAdvanced = true
                    }
                    content()
                }
            }
        }
        // Nine frames keep this regression inexpensive while advancing chained coroutine delays.
        try {
            paparazzi.gif(view, name = name, start = 0L, end = 8000L, fps = 1)
        } finally {
            view.disposeComposition()
        }
        assertTrue("The test must actually advance past the legacy capture timers", clockAdvanced)
    }
}
