package vn.vericlue.app.screenshots

import android.os.Handler
import android.os.Looper
import android.view.Choreographer
import app.cash.paparazzi.DeviceConfig
import app.cash.paparazzi.Paparazzi
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.runtime.Recomposer
import androidx.compose.runtime.getValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.AndroidUiFrameClock
import androidx.compose.ui.platform.ComposeView
import com.airbnb.lottie.LottieComposition
import com.airbnb.lottie.LottieCompositionFactory
import com.airbnb.lottie.compose.animateLottieCompositionAsState
import com.android.resources.Density
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.CoroutineStart
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.android.asCoroutineDispatcher
import kotlinx.coroutines.cancel
import kotlinx.coroutines.launch
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertTrue
import org.junit.Rule
import org.junit.Test
import vn.vericlue.app.R
import vn.vericlue.app.ui.components.SuccessArtwork
import vn.vericlue.app.ui.components.SuccessBadge
import vn.vericlue.app.ui.theme.Vc
import vn.vericlue.app.ui.theme.VcTheme

class SuccessAnimationSnapshotTest {
    @get:Rule val paparazzi = Paparazzi(deviceConfig = DeviceConfig(
        screenWidth = 240, screenHeight = 240, xdpi = 160, ydpi = 160, density = Density.MEDIUM,
    ))

    private fun composition(): LottieComposition {
        val result = LottieCompositionFactory.fromRawResSync(paparazzi.context, R.raw.vericlue_success)
        return requireNotNull(result.value) { "Bundled animation did not parse: ${result.exception}" }
    }

    @Test fun bundledAnimationIsShortAndSelfContained() {
        val composition = composition()
        assertTrue("Animation must complete promptly", composition.duration in 1f..1500f)
        assertFalse("Offline artwork must not require external images", composition.hasImages())
        assertTrue("Offline artwork must not require external fonts", composition.fonts.isEmpty())
        assertNotNull("Reduced motion must have a complete frame", composition.getMarker("reduced motion"))
        assertTrue("Lottie parser reported unsupported content", composition.warnings.isEmpty())
    }

    @Test fun actualAnimationFramesAndFailureFallback() {
        val composition = composition()
        for (dark in listOf(false, true)) {
            for (frame in listOf(0f, 0.5f, 1f)) {
                paparazzi.snapshot("ring_${dark}_$frame") {
                    VcTheme(dark = dark, motionEnabled = false) {
                        Box(Modifier.fillMaxSize().background(Vc.colors.background), contentAlignment = Alignment.Center) {
                            SuccessArtwork(composition) { frame }
                        }
                    }
                }
            }
            paparazzi.snapshot("fallback_$dark") {
                VcTheme(dark = dark, motionEnabled = false) {
                    Box(Modifier.fillMaxSize().background(Vc.colors.background), contentAlignment = Alignment.Center) {
                        SuccessArtwork(null) { 0f }
                    }
                }
            }
            paparazzi.snapshot("reduced_motion_$dark") {
                VcTheme(dark = dark, motionEnabled = false) {
                    Box(Modifier.fillMaxSize().background(Vc.colors.background), contentAlignment = Alignment.Center) {
                        SuccessBadge()
                    }
                }
            }
        }
    }

    @Test fun lightMotionCompletesInOnePass() = recordMotion(dark = false)

    @Test fun darkMotionCompletesInOnePass() = recordMotion(dark = true)

    @Test fun consecutiveMotionSnapshotsEachCompleteOnTheirOwnClock() {
        recordMotion(dark = false)
        recordMotion(dark = true)
    }

    private fun recordMotion(dark: Boolean) {
        val composition = composition()
        var lastDrawnProgress = 0f
        // Paparazzi 1.3.5 resets Layoutlib time/callbacks for every snapshot, while its
        // default window recomposer inherits Compose's process-cached AndroidUiDispatcher clock.
        // Own a main-thread dispatcher and real Choreographer clock for this recording so
        // pending frame-dispatch state cannot survive into a different rendering session.
        val dispatcher = Handler(Looper.getMainLooper())
            .asCoroutineDispatcher("SuccessAnimationSnapshot").immediate
        val scope = CoroutineScope(
            SupervisorJob() + dispatcher + AndroidUiFrameClock(Choreographer.getInstance()),
        )
        val recomposer = Recomposer(scope.coroutineContext)
        scope.launch(start = CoroutineStart.UNDISPATCHED) {
            recomposer.runRecomposeAndApplyChanges()
        }
        val view = ComposeView(paparazzi.context).apply {
            setParentCompositionContext(recomposer)
            setContent {
                VcTheme(dark = dark, motionEnabled = true) {
                    val progress by animateLottieCompositionAsState(composition, iterations = 1)
                    Box(Modifier.fillMaxSize().background(Vc.colors.background), contentAlignment = Alignment.Center) {
                        SuccessArtwork(composition) { progress.also { lastDrawnProgress = it } }
                    }
                }
            }
        }
        try {
            paparazzi.gif(view, name = "motion_$dark", end = 1500L, fps = 30)
        } finally {
            view.disposeComposition()
            recomposer.cancel()
            scope.cancel()
        }
        assertTrue("Animation did not reach its final frame: $lastDrawnProgress", lastDrawnProgress >= 0.99f)
    }
}
