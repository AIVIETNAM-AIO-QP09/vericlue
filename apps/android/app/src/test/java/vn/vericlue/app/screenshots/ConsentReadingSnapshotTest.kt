package vn.vericlue.app.screenshots

import android.os.Handler
import android.os.Looper
import android.view.Choreographer
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.Recomposer
import androidx.compose.ui.node.RootForTest
import androidx.compose.ui.platform.AndroidUiFrameClock
import androidx.compose.ui.platform.ComposeView
import androidx.compose.ui.platform.LocalView
import androidx.compose.ui.semantics.Role
import androidx.compose.ui.semantics.SemanticsActions
import androidx.compose.ui.semantics.SemanticsProperties
import androidx.compose.ui.semantics.getAllSemanticsNodes
import androidx.compose.ui.semantics.getOrNull
import androidx.compose.ui.state.ToggleableState
import app.cash.paparazzi.DeviceConfig
import app.cash.paparazzi.Paparazzi
import com.android.resources.Density
import com.android.resources.ScreenOrientation
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.CoroutineStart
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.android.asCoroutineDispatcher
import kotlinx.coroutines.cancel
import kotlinx.coroutines.delay
import kotlinx.coroutines.launch
import org.junit.Assert.*
import org.junit.Rule
import org.junit.Test
import vn.vericlue.app.ui.screens.TermsScreen
import vn.vericlue.app.ui.theme.VcTheme

abstract class ConsentReadingSnapshots(device: DeviceConfig) {
    @get:Rule val paparazzi = Paparazzi(deviceConfig = device)

    @Test fun mustReadToEndAndExplicitlyChooseBothConsents() {
        var finished = false
        var initiallyLocked = false
        var detailsVisible = false
        var unlockedWithoutAcceptance = false
        var firstChoiceInsufficient = false
        var bothChoicesEnableContinue = false
        val dispatcher = Handler(Looper.getMainLooper()).asCoroutineDispatcher("ConsentReading").immediate
        val scope = CoroutineScope(SupervisorJob() + dispatcher + AndroidUiFrameClock(Choreographer.getInstance()))
        val recomposer = Recomposer(scope.coroutineContext)
        scope.launch(start = CoroutineStart.UNDISPATCHED) { recomposer.runRecomposeAndApplyChanges() }
        val view = ComposeView(paparazzi.context).apply {
            setParentCompositionContext(recomposer)
            setContent {
                val root = LocalView.current as RootForTest
                fun nodes() = root.semanticsOwner.getAllSemanticsNodes(mergingEnabled = true)
                fun choices() = nodes().filter { it.config.getOrNull(SemanticsProperties.Role) == Role.Checkbox }
                fun continueDisabled() = nodes().any { node ->
                    node.config.getOrNull(SemanticsProperties.Text).orEmpty().any { it.text == "Đồng ý và tiếp tục" } &&
                        node.config.contains(SemanticsProperties.Disabled)
                }
                VcTheme(motionEnabled = false) {
                    TermsScreen({}, {})
                    LaunchedEffect(Unit) {
                        delay(50)
                        initiallyLocked = choices().size == 2 && choices().all { it.config.contains(SemanticsProperties.Disabled) } && continueDisabled()
                        val text = nodes().flatMap { it.config.getOrNull(SemanticsProperties.Text).orEmpty() }.map { it.text }
                        detailsVisible = "Mục đích sử dụng" in text && "Quyền chủ động" in text && text.none { "Xem chi tiết" in it || "demo-v1" in it }
                        nodes().first { it.config.getOrNull(SemanticsActions.ScrollBy) != null }
                            .config[SemanticsActions.ScrollBy].action?.invoke(0f, 100_000f)
                        delay(400)
                        unlockedWithoutAcceptance = choices().size == 2 && choices().all {
                            !it.config.contains(SemanticsProperties.Disabled) && it.config.getOrNull(SemanticsProperties.ToggleableState) == ToggleableState.Off
                        } && continueDisabled()
                        choices()[0].config[SemanticsActions.OnClick].action?.invoke()
                        delay(100)
                        firstChoiceInsufficient = continueDisabled()
                        choices()[1].config[SemanticsActions.OnClick].action?.invoke()
                        delay(100)
                        bothChoicesEnableContinue = !continueDisabled()
                        finished = true
                    }
                }
            }
        }
        try { paparazzi.gif(view, "consent_read_and_choose", end = 900L, fps = 20) }
        finally { view.disposeComposition(); recomposer.cancel(); scope.cancel() }
        assertTrue("Test reached the final state", finished)
        assertTrue("Choices and continue are locked before reading", initiallyLocked)
        assertTrue("Full notice is inline without a technical demo label", detailsVisible)
        assertTrue("Scrolling unlocks choices but never accepts them", unlockedWithoutAcceptance)
        assertTrue("Both independent consents are required for onboarding", firstChoiceInsufficient)
        assertTrue("Continue opens only after both explicit choices", bothChoicesEnableContinue)
    }
}

class CompactConsentReadingSnapshotTest : ConsentReadingSnapshots(DeviceConfig(
    screenWidth = 375, screenHeight = 812, xdpi = 160, ydpi = 160, density = Density.MEDIUM,
))
class LargeTextConsentReadingSnapshotTest : ConsentReadingSnapshots(DeviceConfig(
    screenWidth = 375, screenHeight = 812, xdpi = 160, ydpi = 160, density = Density.MEDIUM, fontScale = 2f,
))
class LandscapeConsentReadingSnapshotTest : ConsentReadingSnapshots(DeviceConfig(
    screenWidth = 812, screenHeight = 375, xdpi = 160, ydpi = 160, density = Density.MEDIUM,
    orientation = ScreenOrientation.LANDSCAPE,
))
