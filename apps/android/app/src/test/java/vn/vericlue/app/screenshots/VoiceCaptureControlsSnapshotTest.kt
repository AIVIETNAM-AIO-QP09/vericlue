package vn.vericlue.app.screenshots

import android.os.Handler
import android.os.Looper
import android.view.Choreographer
import app.cash.paparazzi.DeviceConfig
import app.cash.paparazzi.Paparazzi
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.runtime.CompositionLocalProvider
import androidx.compose.runtime.DisposableEffect
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.Recomposer
import androidx.compose.runtime.mutableStateOf
import androidx.compose.ui.Modifier
import androidx.compose.ui.geometry.Rect
import androidx.compose.ui.layout.onGloballyPositioned
import androidx.compose.ui.node.RootForTest
import androidx.compose.ui.platform.ComposeView
import androidx.compose.ui.platform.AndroidUiFrameClock
import androidx.compose.ui.platform.LocalView
import androidx.compose.ui.semantics.SemanticsProperties
import androidx.compose.ui.semantics.SemanticsActions
import androidx.compose.ui.semantics.getAllSemanticsNodes
import androidx.compose.ui.semantics.getOrNull
import androidx.compose.ui.text.TextLayoutResult
import com.android.resources.Density
import org.junit.Assert.*
import org.junit.Rule
import org.junit.Test
import kotlinx.coroutines.delay
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.CoroutineStart
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.android.asCoroutineDispatcher
import kotlinx.coroutines.cancel
import kotlinx.coroutines.launch
import vn.vericlue.app.capture.VoiceCapturePhase
import vn.vericlue.app.ui.screens.Messages
import vn.vericlue.app.ui.screens.VoiceScreen
import vn.vericlue.app.ui.theme.VcTheme
import vn.vericlue.app.ui.components.LocalCameraFeed

private const val LONG_READING = "Tôi xác nhận thuyền đường thuyền đường, mã không không không không không không."

abstract class VoiceCaptureControlsSnapshots(private val device: DeviceConfig) {
    @get:Rule val paparazzi = Paparazzi(deviceConfig = device)

    @Test fun recordingKeepsTheActualCountdownAndExplicitFinishVisibleAtLargeText() {
        var finish: Rect? = null
        var countdown: Rect? = null
        var phrase: Rect? = null
        val phraseLayouts = mutableListOf<TextLayoutResult>()
        val reading = LONG_READING
        val view = ComposeView(paparazzi.context).apply { setContent {
            val root = LocalView.current as RootForTest
            VcTheme(motionEnabled = false) {
                Box(Modifier.fillMaxSize().onGloballyPositioned {
                    val nodes = root.semanticsOwner.getAllSemanticsNodes(mergingEnabled = false)
                    fun bounds(text: String) = nodes.firstOrNull { node ->
                        node.config.getOrNull(SemanticsProperties.Text)?.any { it.text == text } == true
                    }?.boundsInRoot
                    finish = bounds("Đọc xong")
                    countdown = bounds("Còn 7 giây")
                    phrase = bounds("“$reading”")
                    nodes.firstOrNull { node -> node.config.getOrNull(SemanticsProperties.Text)
                        ?.any { it.text == "“$reading”" } == true }
                        ?.config?.getOrNull(SemanticsActions.GetTextLayoutResult)?.action?.invoke(phraseLayouts)
                }) {
                    VoiceScreen({}, {}, again = true,
                        sentence = reading,
                        capturePhase = VoiceCapturePhase.Recording, recordedDurationMs = 3_000, recordingLimitMs = 10_000)
                }
            }
        } }
        try { paparazzi.snapshot(view, "actual_countdown") } finally { view.disposeComposition() }
        assertNotNull("Explicit finish action must be visible", finish)
        assertNotNull("Countdown must deduct native preparation time", countdown)
        val action = finish!!
        val time = countdown!!
        assertTrue(action.top >= 0 && action.bottom <= device.screenHeight)
        assertTrue(time.top >= 0 && time.bottom <= action.top)
        assertNotNull("The full reading phrase must be on screen while recording", phrase)
        assertTrue("Reading layout must be available", phraseLayouts.isNotEmpty())
        val readingBounds = phrase!!
        assertTrue("Preparation content must not push the reading below the fold",
            readingBounds.top >= 0 && readingBounds.bottom <= time.top &&
                readingBounds.height >= phraseLayouts.last().size.height - 1f)
    }

    @Test fun deadlineMessageIsDifferentFromAnAudioOrPermissionFailure() {
        var found = false
        paparazzi.snapshot("local_limit") {
            val root = LocalView.current as RootForTest
            VcTheme(motionEnabled = false) {
                Box(Modifier.fillMaxSize().onGloballyPositioned {
                    found = root.semanticsOwner.getAllSemanticsNodes(mergingEnabled = false).any { node ->
                        node.config.getOrNull(SemanticsProperties.Text)?.any { it.text == "Bản ghi đã hết thời gian" } == true
                    }
                }) { Messages.VoiceTimeLimit({}, {}) }
            }
        }
        assertTrue("Deadline must not be labeled silence or missing permission", found)
    }
}

class CompactVoiceCaptureControlsSnapshotTest : VoiceCaptureControlsSnapshots(DeviceConfig(
    screenWidth = 375, screenHeight = 812, xdpi = 160, ydpi = 160, density = Density.MEDIUM,
))
class LargeTextVoiceCaptureControlsSnapshotTest : VoiceCaptureControlsSnapshots(DeviceConfig(
    screenWidth = 375, screenHeight = 812, xdpi = 160, ydpi = 160, density = Density.MEDIUM, fontScale = 2f,
)) {
    @Test fun scrolledIdleKeepsOneCameraHostAndReturnsToThePhraseWhenReadingStarts() {
        val phase = mutableStateOf(VoiceCapturePhase.Idle)
        var mounts = 0
        var disposals = 0
        var preparingDisposals = -1
        var preparingPreview = false
        var recordingPreview = false
        var readScroll: (() -> Float)? = null
        var requestScroll: (() -> Unit)? = null
        var idleScrolled = false
        var recordingScroll = -1f
        var clockAdvanced = false
        var scrollRequested = false
        var idleMaximum = -1f
        // ScrollBy is animated. Its frames must belong to this Paparazzi session,
        // rather than Compose's process-cached window-recomposer frame clock.
        val dispatcher = Handler(Looper.getMainLooper())
            .asCoroutineDispatcher("VoiceCaptureTransitionSnapshot").immediate
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
            val root = LocalView.current as RootForTest
            VcTheme(motionEnabled = false) {
                CompositionLocalProvider(LocalCameraFeed provides { modifier ->
                    DisposableEffect(Unit) { mounts++; onDispose { disposals++ } }
                    Box(modifier)
                }) {
                    LaunchedEffect(Unit) {
                        delay(50)
                        requestScroll?.let { scrollRequested = true; it() }
                        delay(100)
                        idleScrolled = (readScroll?.invoke() ?: 0f) > 0f
                        phase.value = VoiceCapturePhase.Preparing
                        delay(100)
                        preparingDisposals = disposals
                        preparingPreview = root.semanticsOwner
                            .getAllSemanticsNodes(mergingEnabled = false).any {
                                it.config.getOrNull(SemanticsProperties.TestTag) == "voice-preview-thumbnail" &&
                                    it.boundsInRoot.width > 0f && it.boundsInRoot.height > 0f
                            }
                        phase.value = VoiceCapturePhase.Recording
                        delay(100)
                        recordingScroll = readScroll?.invoke() ?: -1f
                        recordingPreview = root.semanticsOwner
                            .getAllSemanticsNodes(mergingEnabled = false).any {
                                it.config.getOrNull(SemanticsProperties.TestTag) == "voice-preview-thumbnail" &&
                                    it.boundsInRoot.width > 0f && it.boundsInRoot.height > 0f
                            }
                        phase.value = VoiceCapturePhase.Finished
                        delay(100)
                        clockAdvanced = true
                    }
                    Box(Modifier.fillMaxSize().onGloballyPositioned {
                        val scroll = root.semanticsOwner.getAllSemanticsNodes(mergingEnabled = false)
                            .firstOrNull { it.config.getOrNull(SemanticsActions.ScrollBy) != null }
                        val range = scroll?.config?.getOrNull(SemanticsProperties.VerticalScrollAxisRange)
                        if (phase.value == VoiceCapturePhase.Idle) idleMaximum = range?.maxValue?.invoke() ?: -1f
                        readScroll = range?.let { { it.value() } }
                        val action = scroll?.config?.getOrNull(SemanticsActions.ScrollBy)?.action
                        requestScroll = action?.let { { it(0f, 1000f); Unit } }
                    }) {
                        VoiceScreen({}, {}, sentence = LONG_READING, capturePhase = phase.value,
                            recordedDurationMs = 3_000, recordingLimitMs = 10_000)
                    }
                }
            }
            }
        }
        try { paparazzi.gif(view, "reading_transition", end = 500L, fps = 20) }
        finally {
            view.disposeComposition()
            recomposer.cancel()
            scope.cancel()
        }
        assertTrue("The fixture must advance through every capture phase", clockAdvanced)
        assertTrue("The fixture must expose a scroll action", scrollRequested)
        assertTrue("The idle reading must overflow its viewport: $idleMaximum", idleMaximum > 0f)
        assertTrue("The fixture must actually scroll the idle reading (maximum=$idleMaximum)", idleScrolled)
        assertTrue("Camera guide must remain visible while preparing", preparingPreview)
        assertTrue("Camera guide must remain visible while recording", recordingPreview)
        assertEquals("Starting recording must not detach the native preview", 0, preparingDisposals)
        assertEquals("One native preview must survive every capture phase", 1, mounts)
        assertEquals("Only final fixture teardown may dispose the preview", 1, disposals)
        assertEquals("Reading starts at the top of its phrase, not the old preparation offset", 0f, recordingScroll, 0.1f)
    }
}
