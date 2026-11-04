package vn.vericlue.app.ui.screens

import androidx.activity.compose.BackHandler
import androidx.compose.animation.core.Animatable
import androidx.compose.animation.core.FastOutSlowInEasing
import androidx.compose.animation.core.VectorConverter
import androidx.compose.animation.core.tween
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.foundation.background
import androidx.compose.foundation.Canvas
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.BoxWithConstraints
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.offset
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.statusBarsPadding
import androidx.compose.foundation.layout.navigationBarsPadding
import androidx.compose.foundation.layout.WindowInsets
import androidx.compose.foundation.layout.statusBars
import androidx.compose.foundation.layout.navigationBars
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.outlined.Face
import androidx.compose.material.icons.outlined.WbSunny
import androidx.compose.material.icons.outlined.PhoneAndroid
import androidx.compose.material3.LinearProgressIndicator
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.setValue
import androidx.compose.runtime.snapshotFlow
import androidx.compose.runtime.mutableIntStateOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.drawWithContent
import androidx.compose.ui.draw.clip
import androidx.compose.ui.draw.clipToBounds
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.Path
import androidx.compose.ui.graphics.drawscope.clipPath
import androidx.compose.ui.platform.LocalDensity
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.semantics.ProgressBarRangeInfo
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.semantics.progressBarRangeInfo
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.unit.dp
import kotlinx.coroutines.delay
import kotlinx.coroutines.flow.first
import vn.vericlue.app.flow.TurnDir
import vn.vericlue.app.flow.FramingState
import vn.vericlue.app.capture.CaptureClock
import vn.vericlue.app.capture.ColorSchedule
import vn.vericlue.app.capture.ColorSlot
import vn.vericlue.app.capture.FaceSignal
import vn.vericlue.app.capture.HeadTurnGuide
import vn.vericlue.app.capture.TurnTracker
import vn.vericlue.app.capture.FaceTimeline
import vn.vericlue.app.capture.FaceAttemptGuard
import vn.vericlue.app.capture.FaceAttemptIssue
import vn.vericlue.app.capture.AdaptiveHeadCapture
import vn.vericlue.app.capture.HeadCaptureState
import vn.vericlue.app.capture.HeadFeedback
import vn.vericlue.app.capture.hint
import vn.vericlue.app.ui.components.Tone
import androidx.compose.runtime.rememberUpdatedState
import androidx.compose.ui.geometry.Rect
import androidx.compose.ui.geometry.Size
import androidx.compose.runtime.withFrameNanos
import vn.vericlue.app.ui.components.ContentCard
import vn.vericlue.app.ui.components.Banner
import vn.vericlue.app.ui.components.FaceCaptureSurface
import vn.vericlue.app.ui.components.faceGuideRect
import vn.vericlue.app.ui.components.IdentityScene3D
import vn.vericlue.app.ui.components.IllustrationScene
import vn.vericlue.app.ui.components.FeatureRow
import vn.vericlue.app.ui.components.LinkButton
import vn.vericlue.app.ui.components.PrimaryButton
import vn.vericlue.app.ui.components.TitleBlock
import vn.vericlue.app.ui.components.VcScreen
import vn.vericlue.app.ui.components.SystemBarIcons
import vn.vericlue.app.ui.components.TopBar
import vn.vericlue.app.ui.components.StepProgress
import vn.vericlue.app.ui.components.stepLabel
import vn.vericlue.app.ui.theme.Palette
import vn.vericlue.app.ui.theme.Vc
import vn.vericlue.app.ui.theme.VcType
import vn.vericlue.app.ui.theme.VcTheme

/*
 * Stage B of ADR-0016 (22/10 update): two tasks, about 18 seconds.
 *  1 · Hold still (~12 s): grey → colour flash → follow the dot, starts by itself.
 *  2 · Turn left/right in the order the server gives.
 * Camera and flash screens have no decorative motion; only guidance moves.
 */

@OptIn(androidx.compose.material3.ExperimentalMaterial3Api::class)
@Composable
fun FaceReadyScreen(onBack: () -> Unit, onReady: () -> Unit, onSkipFlash: () -> Unit,
    manualDemo: Boolean = false, usesLightChallenge: Boolean = true) {
    val c = Vc.colors
    var lightHelp by remember { mutableStateOf(false) }
    VcScreen(
        onBack = onBack,
        step = 2,
        actions = {
            PrimaryButton("Bắt đầu", onReady)
        },
    ) {
        TitleBlock("Xác minh khuôn mặt", "Giữ điện thoại ngang tầm mắt.")
        if (manualDemo) Banner("Chế độ trình diễn · Ngưỡng thử nghiệm, chưa hiệu chỉnh. Kết quả không dùng để xác minh danh tính.", tone = Tone.Warn)
        IdentityScene3D(Modifier.fillMaxWidth().height(132.dp), IllustrationScene.Face)
        ContentCard {
            FeatureRow(Icons.Outlined.WbSunny, "Chọn nơi đủ sáng")
            FeatureRow(Icons.Outlined.Face, "Không che khuôn mặt")
            FeatureRow(Icons.Outlined.PhoneAndroid, "Giữ nguyên vị trí điện thoại")
        }
        if (usesLightChallenge) {
            Text("Màn hình sẽ thay đổi màu trong vài giây.", style = VcType.bodySmall, color = c.muted)
            LinkButton("Tôi nhạy cảm với ánh sáng", { lightHelp = true })
        }
    }
    if (lightHelp) {
        androidx.compose.material3.ModalBottomSheet(
            onDismissRequest = { lightHelp = false },
            sheetState = androidx.compose.material3.rememberModalBottomSheetState(skipPartiallyExpanded = true),
            containerColor = c.background,
        ) {
            Column(Modifier.fillMaxWidth().verticalScroll(rememberScrollState()).padding(24.dp),
                verticalArrangement = Arrangement.spacedBy(16.dp)) {
                TitleBlock("Về bước đổi màu", "Luồng này chưa hỗ trợ xác minh không đổi màu màn hình.")
                Text("Nếu ánh sáng thay đổi khiến bạn khó chịu, đừng bắt đầu bước này. Bạn có thể quay lại trước khi mở camera.",
                    style = VcType.body, color = c.ink)
                PrimaryButton("Quay lại", { lightHelp = false })
                LinkButton("Rời bước xác minh", onSkipFlash)
            }
        }
    }
}

/** Compatibility layout for the optional local rehearsal, outside the recorded challenge. */
@Composable
internal fun CameraScaffold(onBack: () -> Unit, content: @Composable () -> Unit) {
    BackHandler(onBack = onBack)
    VcTheme(dark = true) {
        val c = Vc.colors
        SystemBarIcons(c.background)
        Column(Modifier.fillMaxSize().background(c.background).statusBarsPadding()) {
            TopBar(onBack)
            StepProgress(2, stepLabel(2))
            Box(Modifier.weight(1f).fillMaxWidth()) { content() }
            Spacer(Modifier.navigationBarsPadding())
        }
    }
}

private val demoFraming = listOf(FramingState.LowLight, FramingState.TooFar, FramingState.Good)

/**
 * [live] comes from the real camera (QualityGate); when it is null the screen plays a demo
 * sequence so the design can be reviewed without a camera.
 */
@Composable
fun FramingScreen(
    onExit: () -> Unit,
    onCaptured: () -> Unit,
    start: FramingState = FramingState.LowLight,
    auto: Boolean = false,
    live: FramingState? = null,
    captureProgress: Float = 0f,
    hintOverride: String? = null,
    onGuidePosition: ((Rect, Size) -> Unit)? = null,
    reauth: Boolean = false,
) {
    var demo by remember { mutableStateOf(start) }
    LaunchedEffect(auto, live == null) {
        if (!auto || live != null) return@LaunchedEffect
        var i = demoFraming.indexOf(demo).coerceAtLeast(0)
        while (i < demoFraming.lastIndex) {
            delay(1600)
            i++
            demo = demoFraming[i]
        }
        delay(1400)
        onCaptured()
    }
    val state = live ?: demo
    FaceCaptureSurface(
        title = if (reauth) "Đăng nhập khuôn mặt" else "Đưa mặt vào khung", onStop = onExit,
        reauth = reauth,
        hint = hintOverride ?: when (state) {
            FramingState.NoFace -> "Nhìn thẳng vào camera"
            FramingState.LowLight -> "Chọn nơi đủ sáng"
            FramingState.TooFar -> "Đưa điện thoại lại gần một chút"
            FramingState.TooClose -> "Đưa điện thoại ra xa một chút"
            FramingState.OffCenter -> "Giữ khoảng cách, đưa mặt vào giữa khung"
            FramingState.MultipleFaces -> "Chỉ để một người trong khung hình"
            FramingState.IncompleteFace -> "Đưa toàn bộ khuôn mặt vào khung"
            FramingState.NotStraight -> "Nhìn thẳng và giữ đầu ngay ngắn"
            FramingState.Good -> "Giữ yên trong giây lát"
        },
        good = state == FramingState.Good,
        faceScale = if (state == FramingState.TooFar) 0.6f else 1f,
        dim = if (state == FramingState.LowLight) 0.45f else 0f,
        progress = captureProgress.takeIf { it > 0f }, onGuidePosition = onGuidePosition,
    )
}

// ── Task 1: hold still (grey → colour flash → follow the dot) ────────────────

/**
 * Task 1. Plays [slots] (grey baseline, the server's 8 colours, grey tail), then the dot.
 * [onPainted] gets the time each colour actually reached the screen (first frame after the
 * change, on the shared clock). [onColorsStart]/[onColorsDone] bracket the video recording.
 * When [auto] is false the screen is frozen at [startPhase] (0 grey, 1..4 a colour, 5 dot) for previews.
 */
@Composable
fun HoldStillScreen(
    onStop: () -> Unit,
    onDone: () -> Unit,
    startPhase: Int = 0,
    auto: Boolean = true,
    slots: List<ColorSlot> = ColorSchedule.demo(),
    onColorsStart: () -> Unit = {},
    onPainted: (ColorSlot, Double) -> Unit = { _, _ -> },
    onColorsDone: () -> Unit = {},
    onBaselineDone: () -> Unit = {},
    onDotDone: () -> Unit = {},
    frozenSlot: Int? = null,
) {
    var dotFinished by remember { mutableStateOf(false) }
    val frozen = frozenSlot ?: when {
        startPhase == 0 -> 0
        startPhase in 1..4 -> slots.indexOfFirst { it.index == startPhase - 1 }.coerceAtLeast(0)
        else -> -1
    }
    var slot by remember(auto, frozen) { mutableIntStateOf(if (auto) 0 else frozen) }
    LaunchedEffect(auto) {
        if (!auto) return@LaunchedEffect
        // Let the screen transition finish first: the camera reconfigures when the preview moves
        // to this screen, and a recording started during that is cancelled (ERROR_SOURCE_INACTIVE).
        delay(SETTLE_MS)
        onColorsStart()
        for (i in slots.indices) {
            slot = i
            withFrameNanos { t -> onPainted(slots[i], CaptureClock.frameNanosToMs(t)) }
            delay(slots[i].durationMs.toLong())
            if (i == 0) onBaselineDone()
        }
        onColorsDone()
        slot = -1
        // Demo / MVP only: the live FLOW-01 schedule runs in FaceTimelineScreen instead.
        snapshotFlow { dotFinished }.first { it }
        onDotDone()
        onDone()
    }
    BackHandler(onBack = onStop)
    FullBrightness(enabled = auto)
    val current = slots.getOrNull(slot)
    FaceCaptureSurface(
        title = if (current != null) "Giữ yên, nhìn thẳng" else "Đưa mắt theo chấm",
        hint = if (current != null) "Giữ nguyên vị trí điện thoại" else "Giữ đầu yên, chỉ di chuyển mắt",
        onStop = onStop, light = true,
        background = current?.let { Color(ColorSchedule.parse(it.rgb)) } ?: Color.White,
        progress = current?.let { (slot + 1f) / slots.size.coerceAtLeast(1) },
        extraOverlay = { if (current == null) FollowDot(Modifier.fillMaxSize(), auto) { dotFinished = true } },
    )
}

private const val SETTLE_MS = 600L

/** Screen at full brightness while the colours play, so the skin reflection is measurable. */
@Composable
private fun FullBrightness(enabled: Boolean) {
    val view = androidx.compose.ui.platform.LocalView.current
    androidx.compose.runtime.DisposableEffect(enabled) {
        val window = (view.context as? android.app.Activity)?.window
        val before = window?.attributes?.screenBrightness
        if (enabled && window != null) {
            window.attributes = window.attributes.apply { screenBrightness = 1f }
            window.addFlags(android.view.WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON)
        }
        onDispose {
            if (enabled && window != null && before != null) {
                window.attributes = window.attributes.apply { screenBrightness = before }
                window.clearFlags(android.view.WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON)
            }
        }
    }
}

/** Demo / MVP: the dot wanders at random; the user follows it with the eyes only (ADR-0016, layer 2). */
@Composable
private fun FollowDot(modifier: Modifier, running: Boolean, onFinished: () -> Unit = {}) {
    BoxWithConstraints(modifier) {
        val w = maxWidth.value
        val h = maxHeight.value
        val pos = remember { Animatable(Offset(w * 0.2f, h * 0.5f), Offset.VectorConverter) }
        val total = 7
        var steps by remember { mutableIntStateOf(0) }
        LaunchedEffect(running) {
            if (!running) return@LaunchedEffect
            val rnd = java.util.Random()
            repeat(total) {
                val target = Offset(w * (0.1f + rnd.nextFloat() * 0.8f), h * (0.15f + rnd.nextFloat() * 0.6f))
                pos.animateTo(target, tween(850, easing = FastOutSlowInEasing))
                steps++
            }
            onFinished()
        }
        Box(
            Modifier.offset(x = (pos.value.x - 12).dp, y = (pos.value.y - 12).dp).size(24.dp)
                .clip(CircleShape).background(Palette.Primary.copy(alpha = 0.18f)),
            contentAlignment = Alignment.Center,
        ) { Box(Modifier.size(14.dp).clip(CircleShape).background(Palette.Primary)) }
        LinearProgressIndicator(
            progress = { steps / total.toFloat() },
            modifier = Modifier.fillMaxWidth().height(3.dp).align(Alignment.BottomCenter),
            color = Palette.Primary,
            trackColor = Palette.Border,
        )
    }
}

// ── Task 2: turn left / right in server order ────────────────────────────────

@Composable
fun TurnHeadScreen(
    order: List<TurnDir>,
    onExit: () -> Unit,
    onDone: () -> Unit,
    auto: Boolean = true,
    yaw: Float? = null,
) {
    var index by remember { mutableIntStateOf(0) }
    // Live: advance when the head turn is detected (ML Kit yaw). Demo: advance on a timer.
    val tracker = remember(index) { TurnTracker(direction = order[index]) }
    LaunchedEffect(yaw) {
        if (yaw == null || !auto) return@LaunchedEffect
        if (tracker.update(yaw, android.os.SystemClock.elapsedRealtime())) {
            if (index < order.size - 1) index++ else onDone()
        }
    }
    val dir = order[index]
    TurnHeadContent(dir, onExit)
}

/** The latest demo's camera layout, shared with each server-scheduled head segment. */
@Composable
private fun TurnHeadContent(
    dir: TurnDir?, onExit: () -> Unit,
) {
    FaceCaptureSurface(
        title = when (dir) { TurnDir.Left -> "Quay sang trái"; TurnDir.Right -> "Quay sang phải"; null -> "Nhìn thẳng" },
        hint = "Giữ nguyên vị trí điện thoại", onStop = onExit, direction = dir, headGuidance = true,
    )
}

private data class TimedHeadUi(val title: String, val feedback: String, val tone: Tone, val good: Boolean)

/** Legacy schedule coaching stays local; a return never asks for the same side twice. */
@Composable
private fun rememberTimedHeadUi(
    head: FaceTimeline.Phase.Head,
    remainingSeconds: Int?,
    face: FaceSignal?,
    debugTrace: vn.vericlue.app.capture.PresenceDebugTrace?,
    recordingOriginMs: Double?,
    speech: vn.vericlue.app.capture.HeadSpeech?,
): TimedHeadUi {
    val dir = head.dir
    val index = head.segment
    val view = androidx.compose.ui.platform.LocalView.current
    val liveAssist = face != null
    val segmentStartMs = remember(index, dir) { android.os.SystemClock.elapsedRealtime() }
    var clock by remember { mutableStateOf(android.os.SystemClock.elapsedRealtime()) }
    LaunchedEffect(liveAssist) {
        if (liveAssist) while (true) { clock = android.os.SystemClock.elapsedRealtime(); delay(100) }
    }
    val now = maxOf(clock, android.os.SystemClock.elapsedRealtime())
    val activeFace = HeadTurnGuide.freshFace(face, now, segmentStartMs)
    val stale = face != null && activeFace == null
    val hold = remember(index, dir) { vn.vericlue.app.capture.SegmentHoldTracker(segmentStartMs = segmentStartMs) }
    val returned = remember(index, dir) { vn.vericlue.app.capture.SegmentReturnTracker(segmentStartMs) }
    var completed by remember(index, dir) { mutableStateOf(false) }
    var waiting by remember(index, dir) { mutableStateOf(false) }
    LaunchedEffect(activeFace, index, dir) {
        returned.update(dir, activeFace, android.os.SystemClock.elapsedRealtime())
        waiting = returned.waitingForNext
        if (hold.update(dir, activeFace, android.os.SystemClock.elapsedRealtime())) completed = true
    }
    val measured = if (stale || (waiting && activeFace == null)) vn.vericlue.app.capture.TurnPoseState.Warn
        else HeadTurnGuide.evaluatePose(dir, activeFace, completed)
    val pose = if (waiting && !completed && measured != vn.vericlue.app.capture.TurnPoseState.Warn)
        vn.vericlue.app.capture.TurnPoseState.TurnMore else measured
    LaunchedEffect(clock, pose, completed) {
        recordingOriginMs?.let { origin -> debugTrace?.recordGuidance(
            (now - origin).toLong(), index, pose.name, completed,
            activeFace?.timestampNs?.takeIf { it > 0L }?.let { (it / 1e6 - origin).toLong() },
        ) }
    }
    val notified = remember(index, dir) { mutableSetOf<vn.vericlue.app.capture.TurnPoseState>() }
    LaunchedEffect(index, dir, liveAssist) {
        if (liveAssist) runCatching { view.performHapticFeedback(android.view.HapticFeedbackConstants.LONG_PRESS) }
    }
    LaunchedEffect(pose, index, liveAssist) {
        if (liveAssist && notified.add(pose)) runCatching {
            when (pose) {
                vn.vericlue.app.capture.TurnPoseState.Hold -> view.performHapticFeedback(android.view.HapticFeedbackConstants.CLOCK_TICK)
                vn.vericlue.app.capture.TurnPoseState.Completed -> view.performHapticFeedback(android.view.HapticFeedbackConstants.CONFIRM)
                vn.vericlue.app.capture.TurnPoseState.Warn -> view.performHapticFeedback(android.view.HapticFeedbackConstants.REJECT)
                vn.vericlue.app.capture.TurnPoseState.TurnMore -> Unit
            }
        }
    }
    val cue = vn.vericlue.app.capture.headCue(dir, activeFace, completed, waiting)
    val policy = remember { vn.vericlue.app.capture.HeadCuePolicy() }
    LaunchedEffect(cue, clock, index, speech) {
        val awaitingFirstFrame = stale && now - segmentStartMs <= HeadTurnGuide.MAX_FRAME_AGE_MS
        if ((liveAssist || waiting) && !awaitingFirstFrame) policy.dispatch(index, cue, now,
            stop = { speech?.stop() }, say = { speech?.say(it) })
    }
    androidx.compose.runtime.DisposableEffect(index, speech) { onDispose { speech?.stop() } }
    val good = pose == vn.vericlue.app.capture.TurnPoseState.Hold || pose == vn.vericlue.app.capture.TurnPoseState.Completed
    // The legacy countdown shares this slot; keep equivalent cues short at 200% text.
    val hint = when {
        stale -> "Chờ camera nhận mặt"
        cue == vn.vericlue.app.capture.HeadCue.FindFace -> "Đưa mặt vào khung"
        cue == vn.vericlue.app.capture.HeadCue.Straighten -> "Giữ đầu thẳng"
        cue == vn.vericlue.app.capture.HeadCue.EaseBack -> "Quay nhẹ về giữa"
        completed || waiting -> "Nhìn thẳng, chờ tiếp"
        pose == vn.vericlue.app.capture.TurnPoseState.Hold && dir != null -> "Dừng xoay, giữ yên"
        dir == null -> "Giữ yên, nhìn thẳng"
        else -> cue.text
    }
    return TimedHeadUi(
        title = if (liveAssist || waiting) cue.text else when (dir) {
            TurnDir.Left -> "Quay nhẹ sang trái"; TurnDir.Right -> "Quay nhẹ sang phải"; null -> "Nhìn thẳng"
        },
        feedback = hint + (remainingSeconds?.let { " · Còn $it giây" } ?: ""),
        tone = if (good) Tone.Ok else if (pose == vn.vericlue.app.capture.TurnPoseState.Warn) Tone.Warn else Tone.Info,
        good = good,
    )
}

// ── Live FLOW-01 schedule: the whole face part on one recording ─────────────

/**
 * Plays the server's schedule (FaceTimeline) on one continuous recording: grey baseline (frontal
 * still at its mark), colour steps, the dot path over the whole screen, then the head turns. Times
 * run from the recording's first frame. Adaptive head guidance waits for each observed hold;
 * colour/gaze marks stay unchanged. [recordingStartMs] gives the first frame (null until it
 * exists). Both offline and API flows use this screen; only their schedule source differs.
 */
@Composable
fun FaceTimelineScreen(
    timeline: FaceTimeline,
    onStop: () -> Unit,
    onStart: () -> Unit,
    recordingStartMs: () -> Double?,
    onPainted: (ColorSlot, Double) -> Unit,
    onFrontal: () -> Unit,
    onBaselineDone: () -> Unit,
    onColorsDone: () -> Unit,
    onDone: () -> Unit,
    onNoRecording: () -> Unit,
    face: FaceSignal? = null,
    faceSignal: () -> FaceSignal? = { face },
    onIncomplete: (FaceAttemptIssue) -> Unit = { onNoRecording() },
    debugTrace: vn.vericlue.app.capture.PresenceDebugTrace? = null,
) {
    val speech = if (timeline.headTurns.isNotEmpty()) vn.vericlue.app.ui.components.rememberHeadSpeech() else null
    val passive = timeline.isPassiveLogin
    var phase by remember { mutableStateOf<FaceTimeline.Phase>(FaceTimeline.Phase.Colour(0)) }
    var actionProgress by remember { mutableStateOf(0f) }
    var captureProgress by remember { mutableStateOf(0f) }
    var headFeedback by remember { mutableStateOf<HeadCaptureState?>(null) }
    var observedFace by remember { mutableStateOf(face) }
    var recordingOriginMs by remember { mutableStateOf<Double?>(null) }
    var remainingSeconds by remember { mutableStateOf<Int?>(null) }
    val cuePolicy = remember { vn.vericlue.app.capture.HeadCuePolicy() }
    val currentSignal by rememberUpdatedState(faceSignal)
    val incomplete by rememberUpdatedState(onIncomplete)
    LaunchedEffect(Unit) {
        delay(SETTLE_MS) // let the preview settle before recording (see HoldStillScreen)
        onStart()
        var t0: Double? = null
        kotlinx.coroutines.withTimeoutOrNull(3000) {
            while (t0 == null) {
                t0 = recordingStartMs()
                if (t0 == null) delay(16)
            }
        }
        val start = t0 ?: return@LaunchedEffect onNoRecording()
        recordingOriginMs = start
        var lastSlot = -1
        var lastHeadSegment = -1
        var headSegmentStartMs = 0.0
        var frontalDone = false
        var baselineDone = false
        var coloursDone = false
        val guard = FaceAttemptGuard(timeline)
        val adaptive = if (timeline.adaptiveHead) AdaptiveHeadCapture(timeline.headTurns, timeline.headDeadlineMs.toDouble()) else null
        while (true) {
            val nowMs = withFrameNanos { CaptureClock.frameNanosToMs(it) }
            val t = nowMs - start
            // Recording time only: capture completion is never an authentication verdict.
            if (passive) captureProgress = (t / timeline.endMs.coerceAtLeast(1)).toFloat().coerceIn(0f, 1f)
            val signal = currentSignal()
            val observedNow = android.os.SystemClock.elapsedRealtime()
            val headState = if (adaptive != null && t >= timeline.headStartMs)
                adaptive.update(guard.observationForTracking(signal), observedNow, t) else null
            headState?.issue?.let {
                speech?.stop()
                incomplete(it)
                return@LaunchedEffect
            }
            val p = when {
                headState?.done == true -> FaceTimeline.Phase.Done
                headState != null -> FaceTimeline.Phase.Head(headState.segment, headState.direction)
                else -> timeline.phaseAt(t)
            }
            guard.update(p, signal, observedNow)?.let {
                speech?.stop()
                incomplete(it)
                return@LaunchedEffect
            }
            actionProgress = headState?.progress ?: guard.actionProgress
            headFeedback = headState
            observedFace = signal
            phase = p
            remainingSeconds = if (timeline.adaptiveHead) null else timeline.headRemainingSeconds(t)
            if (p is FaceTimeline.Phase.Head && p.segment != lastHeadSegment) {
                lastHeadSegment = p.segment
                headSegmentStartMs = t
                debugTrace?.recordPhaseBoundary(
                    recordingRelMs = t.toLong(),
                    phase = "head",
                    segmentIndex = p.segment,
                    direction = p.dir,
                )
            }
            if (headState != null && p is FaceTimeline.Phase.Head) {
                val frameAt = signal?.timestampNs?.takeIf { it > 0L }?.div(1e6)
                val frameRel = frameAt?.minus(start)
                val belongsToSegment = frameRel != null && frameRel >= headSegmentStartMs
                debugTrace?.recordFaceSample(t.toLong(), signal?.yaw, signal?.pitch, signal?.roll,
                    p.dir.takeIf { belongsToSegment }, 0, frameRel?.toLong(),
                    frameAt?.let { (nowMs - it).toLong() }, signal?.faces,
                    if (belongsToSegment) p.segment else -1)
                debugTrace?.recordGuidance(t.toLong(), p.segment, headState.feedback.name,
                    headState.feedback == HeadFeedback.Complete, frameRel?.toLong())
                vn.vericlue.app.capture.adaptiveHeadCue(headState)?.let { cue ->
                    cuePolicy.dispatch(p.segment, cue, observedNow,
                        stop = { speech?.stop() }, say = { speech?.say(it) })
                }
            } else debugTrace?.recordAnalyzerFrame(signal, timeline, start, nowMs)
            if (p is FaceTimeline.Phase.Colour && p.slot != lastSlot) {
                lastSlot = p.slot
                onPainted(timeline.slots[p.slot], nowMs)
            }
            if (!frontalDone && t >= timeline.frontalAtMs) {
                frontalDone = true
                onFrontal()
            }
            if (!baselineDone && t >= timeline.baselineEndMs) {
                baselineDone = true
                onBaselineDone()
            }
            if (!coloursDone && t >= timeline.coloursEndMs) {
                coloursDone = true
                onColorsDone()
            }
            if (p is FaceTimeline.Phase.Done) {
                speech?.stop()
                onDone()
                break
            }
        }
    }
    val stop = { speech?.stop(); onStop() }
    BackHandler(onBack = stop)
    FullBrightness(enabled = true)
    FaceChallengeContent(timeline, phase, remainingSeconds, observedFace, debugTrace, recordingOriginMs,
        speech, actionProgress, headFeedback, captureProgress = captureProgress, onStop = stop)
}

/** Shared presentation, independently snapshot-tested without opening a camera or starting work. */
@Composable
fun FaceChallengeContent(timeline: FaceTimeline, phase: FaceTimeline.Phase, onStop: () -> Unit) {
    val seconds = if (timeline.adaptiveHead) null else (phase as? FaceTimeline.Phase.Head)?.let {
        timeline.headRemainingSeconds(timeline.headSegmentStartMs(it.segment).toDouble())
    }
    FaceChallengeContent(timeline, phase, seconds, onStop = onStop)
}

@Composable
fun FaceChallengeContent(timeline: FaceTimeline, phase: FaceTimeline.Phase, actionProgress: Float, onStop: () -> Unit,
    headFeedback: HeadCaptureState? = null) =
    FaceChallengeContent(timeline, phase, null, actionProgress = actionProgress, headFeedback = headFeedback, onStop = onStop)

@Composable
fun FaceChallengeContent(
    timeline: FaceTimeline,
    phase: FaceTimeline.Phase,
    remainingSeconds: Int?,
    face: FaceSignal? = null,
    debugTrace: vn.vericlue.app.capture.PresenceDebugTrace? = null,
    recordingOriginMs: Double? = null,
    speech: vn.vericlue.app.capture.HeadSpeech? = null,
    actionProgress: Float = 0f,
    headFeedback: HeadCaptureState? = null,
    captureProgress: Float = 0f,
    onStop: () -> Unit,
) {
    val passive = timeline.isPassiveLogin
    val colour = (phase as? FaceTimeline.Phase.Colour)?.let { timeline.slots[it.slot] }
    val gaze = phase as? FaceTimeline.Phase.Gaze
    val head = phase as? FaceTimeline.Phase.Head
    val timed = if (head != null && !timeline.adaptiveHead)
        rememberTimedHeadUi(head, remainingSeconds, face, debugTrace, recordingOriginMs, speech) else null
    val adaptiveCue = headFeedback?.let { vn.vericlue.app.capture.adaptiveHeadCue(it) }
    val adaptiveGood = headFeedback?.feedback in setOf(HeadFeedback.Hold, HeadFeedback.Complete)
    val adaptiveWarning = headFeedback?.feedback in setOf(HeadFeedback.FaceMissing, HeadFeedback.MultipleFaces,
        HeadFeedback.Level, HeadFeedback.EaseBack)
    val light = colour != null || phase == FaceTimeline.Phase.Gap || gaze != null
    FaceCaptureSurface(
        title = when {
            passive -> "Đăng nhập khuôn mặt"
            timed != null -> timed.title
            head != null && adaptiveCue != null -> adaptiveCue.text
            gaze != null -> "Nhìn theo chấm"
            head?.dir == TurnDir.Left -> "Quay sang trái"
            head?.dir == TurnDir.Right -> "Quay sang phải"
            else -> "Giữ yên, nhìn thẳng"
        },
        hint = when {
            passive -> "Giữ yên, nhìn thẳng vào camera"
            gaze != null -> "Giữ đầu yên, chỉ di chuyển mắt"
            else -> "Giữ nguyên vị trí điện thoại"
        },
        onStop = onStop, light = light, reauth = passive,
        background = colour?.let { Color(ColorSchedule.parse(it.rgb)) } ?: if (light) Color.White else Palette.CameraBg,
        progress = if (passive) captureProgress else
            (phase as? FaceTimeline.Phase.Colour)?.let { (it.slot + 1f) / timeline.slots.size.coerceAtLeast(1) },
        direction = head?.dir, gaze = gaze?.let { Offset(it.x.toFloat(), it.y.toFloat()) },
        headGuidance = head != null, actionProgress = actionProgress.takeIf { head != null },
        good = head != null && (timed?.good ?: adaptiveGood),
        feedback = timed?.feedback ?: headFeedback?.hint(),
        feedbackTone = timed?.tone ?: if (adaptiveGood) Tone.Ok else if (adaptiveWarning) Tone.Warn else Tone.Info,
        extraOverlay = {
            if (passive) PassiveLoginScan(captureProgress)
            if (gaze != null && debugTrace != null && recordingOriginMs != null) {
                Box(Modifier.fillMaxSize().drawWithContent {
                    drawContent()
                    debugTrace.recordGazeTarget((CaptureClock.nowMs() - recordingOriginMs).toLong(),
                        gaze.x.toFloat(), gaze.y.toFloat())
                })
            }
        },
    )
}

private val FaceTimeline.isPassiveLogin: Boolean
    get() = gaze.isEmpty() && headTurns.isEmpty() && slots.size == 1 && slots.single().index == null

/** A capture indicator over the same aperture; it never changes camera framing or exposure. */
@Composable
private fun PassiveLoginScan(progress: Float) {
    val density = LocalDensity.current
    val top = WindowInsets.statusBars.getTop(density).toFloat()
    val bottom = WindowInsets.navigationBars.getBottom(density).toFloat()
    val motion = Vc.motion.enabled
    val captured = progress.coerceIn(0f, 1f)
    Canvas(Modifier.fillMaxSize().testTag("face-login-capture").semantics {
        contentDescription = "Đang thu hình khuôn mặt"
        progressBarRangeInfo = ProgressBarRangeInfo(captured, 0f..1f)
    }) {
        if (motion && captured > 0f && captured < 1f) {
            val oval = faceGuideRect(size.width, size.height, density.density, density.fontScale, top, bottom)
            val y = oval.top + oval.height * captured
            val trail = 36.dp.toPx()
            clipPath(Path().apply { addOval(oval) }) {
                drawRect(
                    Brush.verticalGradient(listOf(Color.Transparent, Palette.Primary.copy(alpha = 0.12f)),
                        startY = y - trail, endY = y),
                    topLeft = Offset(oval.left, y - trail), size = Size(oval.width, trail),
                )
                drawLine(Palette.Primary.copy(alpha = 0.65f), Offset(oval.left, y), Offset(oval.right, y),
                    strokeWidth = 1.5.dp.toPx())
            }
        }
    }
}
