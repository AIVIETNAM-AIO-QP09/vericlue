package vn.vericlue.app.ui.screens

import androidx.activity.compose.BackHandler
import androidx.compose.animation.core.Animatable
import androidx.compose.animation.core.FastOutSlowInEasing
import androidx.compose.animation.core.LinearEasing
import androidx.compose.animation.core.RepeatMode
import androidx.compose.animation.core.VectorConverter
import androidx.compose.animation.core.animateFloat
import androidx.compose.animation.core.infiniteRepeatable
import androidx.compose.animation.core.rememberInfiniteTransition
import androidx.compose.animation.core.tween
import androidx.compose.foundation.Canvas
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.BoxWithConstraints
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.navigationBarsPadding
import androidx.compose.foundation.layout.offset
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.statusBarsPadding
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.outlined.ArrowBack
import androidx.compose.material.icons.automirrored.outlined.ArrowForward
import androidx.compose.material.icons.outlined.CenterFocusWeak
import androidx.compose.material.icons.outlined.Check
import androidx.compose.material.icons.outlined.OpenInFull
import androidx.compose.material.icons.outlined.SwapHoriz
import androidx.compose.material.icons.outlined.WbSunny
import androidx.compose.material3.Button
import androidx.compose.material3.ButtonDefaults
import androidx.compose.material3.Icon
import androidx.compose.material3.LinearProgressIndicator
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.snapshotFlow
import androidx.compose.runtime.mutableIntStateOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.geometry.Size
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.drawscope.Stroke
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import kotlinx.coroutines.delay
import kotlinx.coroutines.flow.first
import vn.vericlue.app.flow.TurnDir
import vn.vericlue.app.flow.FramingState
import vn.vericlue.app.capture.CaptureClock
import vn.vericlue.app.capture.ColorSchedule
import vn.vericlue.app.capture.ColorSlot
import vn.vericlue.app.capture.TurnTracker
import vn.vericlue.app.data.api.DotPoint
import vn.vericlue.app.ui.components.CameraFeed
import androidx.compose.runtime.withFrameNanos
import vn.vericlue.app.ui.components.Banner
import vn.vericlue.app.ui.components.CameraArea
import vn.vericlue.app.ui.components.FullCamera
import vn.vericlue.app.ui.components.GuidanceChip
import vn.vericlue.app.ui.components.LinkButton
import vn.vericlue.app.ui.components.PrimaryButton
import vn.vericlue.app.ui.components.StepProgress
import vn.vericlue.app.ui.components.SystemBarIcons
import vn.vericlue.app.ui.components.TitleBlock
import vn.vericlue.app.ui.components.Tone
import vn.vericlue.app.ui.components.TopBar
import vn.vericlue.app.ui.components.VcScreen
import vn.vericlue.app.ui.components.stepLabel
import vn.vericlue.app.ui.theme.LightColors
import vn.vericlue.app.ui.theme.LocalVcColors
import vn.vericlue.app.ui.theme.Palette
import vn.vericlue.app.ui.theme.Vc
import vn.vericlue.app.ui.theme.VcTheme
import vn.vericlue.app.ui.theme.VcType
import androidx.compose.runtime.CompositionLocalProvider

/*
 * Stage B of ADR-0016 (22/10 update): two tasks, about 18 seconds.
 *  1 · Hold still (~12 s): grey → colour flash → follow the dot, starts by itself.
 *  2 · Turn left/right in the order the server gives.
 * Camera and flash screens have no decorative motion; only guidance moves.
 */

@Composable
fun FaceReadyScreen(onBack: () -> Unit, onReady: () -> Unit, onSkipFlash: () -> Unit) {
    val c = Vc.colors
    VcScreen(
        onBack = onBack,
        step = 2,
        actions = {
            PrimaryButton("Tôi đã sẵn sàng", onReady)
            LinkButton("Bỏ qua nháy màu, chờ nhân viên xác minh", onSkipFlash)
        },
    ) {
        TitleBlock("Tiếp theo: quay khuôn mặt", "Giữ điện thoại cách mặt khoảng 25 đến 40 cm, ở nơi đủ sáng.")
        Column(verticalArrangement = Arrangement.spacedBy(10.dp)) {
            TaskCard(Icons.Outlined.CenterFocusWeak, "1 · Giữ đầu yên", "Nhìn thẳng. Màn hình sẽ đổi màu nhạt, rồi một chấm sáng chạy: chỉ đưa mắt theo.")
            TaskCard(Icons.Outlined.SwapHoriz, "2 · Quay trái, quay phải", "Làm theo mũi tên.")
        }
        Banner(
            "Màn hình sẽ đổi màu nhạt trong vài giây. Người nhạy cảm với ánh sáng nhấp nháy không nên tiếp tục. Bạn có thể bấm Dừng bất cứ lúc nào.",
            tone = Tone.Warn,
        )
    }
}

@Composable
private fun TaskCard(icon: androidx.compose.ui.graphics.vector.ImageVector, title: String, body: String) {
    val c = Vc.colors
    Column(
        Modifier.fillMaxWidth().clip(RoundedCornerShape(12.dp)).background(c.surfaceSubtle).padding(16.dp),
        verticalArrangement = Arrangement.spacedBy(6.dp),
    ) {
        Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            Icon(icon, contentDescription = null, tint = c.accent, modifier = Modifier.size(20.dp))
            Text(title, style = VcType.bodyStrong, color = c.ink)
        }
        Text(body, style = VcType.bodySmall, color = c.muted)
    }
}

/** Dark camera layout shared by framing and turn-head screens. */
@Composable
private fun CameraScaffold(onBack: () -> Unit, content: @Composable () -> Unit) {
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
    auto: Boolean = true,
    live: FramingState? = null,
    onDebugCapture: (() -> Unit)? = null,
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
    CameraScaffold(onExit) {
        Box(Modifier.fillMaxSize()) {
            Box(Modifier.fillMaxSize()) {
                CameraFeed(faceScale = if (state == FramingState.TooFar) 0.6f else 1f, dim = if (state == FramingState.LowLight) 0.45f else 0f)
            }
            val good = state == FramingState.Good
            Box(Modifier.fillMaxSize()) {
                vn.vericlue.app.ui.components.OvalOverlay(
                    ringColor = if (good) Palette.OkOnDark else Color.White,
                    ringWidth = if (good) 3.dp else 2.dp,
                    progress = if (good) 0.72f else null,
                )
            }
            CameraArea { oval ->
                Text(
                    "Đưa khuôn mặt vào khung",
                    style = VcType.titleMedium,
                    color = Color.White,
                    textAlign = TextAlign.Center,
                    modifier = Modifier.fillMaxWidth().padding(top = 18.dp),
                )
                Box(Modifier.fillMaxWidth().offset(y = oval.bottom + 24.dp), contentAlignment = Alignment.TopCenter) {
                    when (state) {
                        FramingState.NoFace -> GuidanceChip("Đưa khuôn mặt vào khung", Icons.Outlined.CenterFocusWeak)
                        FramingState.LowLight -> GuidanceChip("Ra chỗ sáng hơn", Icons.Outlined.WbSunny, Tone.Warn)
                        FramingState.TooFar -> GuidanceChip("Lại gần hơn", Icons.Outlined.OpenInFull)
                        FramingState.OffCenter -> GuidanceChip("Đưa khuôn mặt vào giữa khung hình", Icons.Outlined.CenterFocusWeak)
                        FramingState.Good -> GuidanceChip("Tốt, giữ nguyên", Icons.Outlined.Check, Tone.Ok)
                    }
                }
                Text(
                    if (good) "Đang tự chụp…" else "Ảnh sẽ tự chụp khi đủ điều kiện",
                    style = VcType.bodySmall,
                    color = Color.White.copy(alpha = 0.85f),
                    textAlign = TextAlign.Center,
                    modifier = Modifier.fillMaxWidth().align(Alignment.BottomCenter).padding(bottom = 24.dp),
                )
                if (onDebugCapture != null) DebugButton("Chụp ngay (debug)", onDebugCapture, Modifier.align(Alignment.BottomCenter).padding(bottom = 56.dp))
            }
        }
    }
}

/** Debug builds only: lets developers test the upload path on an emulator with no face in view. */
@Composable
private fun DebugButton(text: String, onClick: () -> Unit, modifier: Modifier) {
    androidx.compose.material3.TextButton(onClick = onClick, modifier = modifier) {
        Text(text, style = VcType.labelSmall, color = Palette.WarnBorder)
    }
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
    dotPath: List<DotPoint>? = null,
    onDot: (index: Int, x: Double, y: Double, paintedAt: Double) -> Unit = { _, _, _, _ -> },
    onDotDone: () -> Unit = {},
) {
    var dotFinished by remember { mutableStateOf(false) }
    val frozen = when {
        startPhase == 0 -> 0
        startPhase in 1..4 -> slots.indexOfFirst { it.index == startPhase - 1 }.coerceAtLeast(0)
        else -> -1
    }
    var slot by remember { mutableIntStateOf(if (auto) 0 else frozen) }
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
        // The dot follows the server's path (LIVE-01); without one (demo) it runs on a timer.
        if (dotPath != null) snapshotFlow { dotFinished }.first { it } else delay(6400)
        onDotDone()
        onDone()
    }
    BackHandler(onBack = onStop)
    FullBrightness(enabled = auto)
    // The flash screens are light whatever the system theme, so the light palette is forced.
    CompositionLocalProvider(LocalVcColors provides LightColors) {
        val current = slots.getOrNull(slot)
        val bg = current?.let { Color(ColorSchedule.parse(it.rgb)) } ?: Color.White
        SystemBarIcons(bg)
        Column(Modifier.fillMaxSize().background(bg).statusBarsPadding()) {
            TopBar(onStop)
            StepProgress(2, stepLabel(2))
            Column(
                Modifier.weight(1f).fillMaxWidth().padding(horizontal = 20.dp, vertical = 20.dp),
                horizontalAlignment = Alignment.CenterHorizontally,
                verticalArrangement = Arrangement.spacedBy(20.dp),
            ) {
                if (current != null) {
                    Text(
                        if (current.index == null) "Giữ yên, nhìn thẳng" else "Giữ yên",
                        style = VcType.titleMedium,
                        color = Palette.Ink,
                    )
                    OvalPreview(progress = (slot + 1f) / (slots.size + 1))
                } else {
                    Text(
                        "Giữ đầu yên, chỉ đưa mắt theo chấm sáng",
                        style = VcType.titleMedium,
                        color = Palette.Ink,
                        modifier = Modifier.fillMaxWidth(),
                    )
                    FollowDot(
                        Modifier.fillMaxWidth().weight(1f, fill = false).height(220.dp),
                        running = auto,
                        path = dotPath,
                        onDot = onDot,
                        onFinished = { dotFinished = true },
                    )
                }
                Banner("Màn hình sẽ nhấp nháy màu nhạt vài giây. Người nhạy cảm với ánh sáng nhấp nháy không nên tiếp tục.")
                Spacer(Modifier.weight(1f))
                Button(
                    onClick = onStop,
                    modifier = Modifier.fillMaxWidth().height(52.dp),
                    shape = RoundedCornerShape(12.dp),
                    colors = ButtonDefaults.buttonColors(containerColor = Color.White, contentColor = Palette.Primary),
                ) { Text("Dừng", style = VcType.button) }
            }
            Spacer(Modifier.navigationBarsPadding())
        }
    }
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

@Composable
private fun OvalPreview(progress: Float) {
    Box(Modifier.size(width = 196.dp, height = 252.dp), contentAlignment = Alignment.Center) {
        Box(Modifier.size(width = 172.dp, height = 228.dp).clip(androidx.compose.foundation.shape.GenericShape { s, _ -> addOval(androidx.compose.ui.geometry.Rect(Offset.Zero, s)) })) {
            CameraFeed()
        }
        Canvas(Modifier.fillMaxSize()) {
            drawArc(
                Palette.Primary,
                startAngle = -90f,
                sweepAngle = 360f * progress,
                useCenter = false,
                topLeft = Offset(2.dp.toPx(), 2.dp.toPx()),
                size = Size(size.width - 4.dp.toPx(), size.height - 4.dp.toPx()),
                style = Stroke(2.5.dp.toPx()),
            )
        }
    }
}

/**
 * The dot follows the server's path (LIVE-01), x/y as a fraction of this area, moving in a straight
 * line between points on their t_ms; the user follows it with the eyes only (ADR-0016, layer 2).
 * Each point reached is reported with its frame time. Without a path (demo) it wanders at random.
 */
@Composable
private fun FollowDot(
    modifier: Modifier,
    running: Boolean,
    path: List<DotPoint>? = null,
    onDot: (index: Int, x: Double, y: Double, paintedAt: Double) -> Unit = { _, _, _, _ -> },
    onFinished: () -> Unit = {},
) {
    BoxWithConstraints(modifier) {
        val w = maxWidth.value
        val h = maxHeight.value
        val start = path?.firstOrNull()?.let { Offset(w * it.x.toFloat(), h * it.y.toFloat()) } ?: Offset(w * 0.2f, h * 0.5f)
        val pos = remember { Animatable(start, Offset.VectorConverter) }
        val total = path?.size ?: 7
        var steps by remember { mutableIntStateOf(0) }
        LaunchedEffect(running) {
            if (!running) return@LaunchedEffect
            if (path != null) {
                path.forEachIndexed { i, p ->
                    val target = Offset(w * p.x.toFloat(), h * p.y.toFloat())
                    if (i == 0) {
                        pos.snapTo(target)
                    } else {
                        pos.animateTo(target, tween((p.tMs - path[i - 1].tMs).coerceAtLeast(1), easing = LinearEasing))
                    }
                    withFrameNanos { t -> onDot(i, p.x, p.y, CaptureClock.frameNanosToMs(t)) }
                    steps = i + 1
                }
            } else {
                val rnd = java.util.Random()
                repeat(total) {
                    val target = Offset(w * (0.1f + rnd.nextFloat() * 0.8f), h * (0.15f + rnd.nextFloat() * 0.6f))
                    pos.animateTo(target, tween(850, easing = FastOutSlowInEasing))
                    steps++
                }
            }
            onFinished()
        }
        Box(
            Modifier.align(Alignment.TopEnd).size(width = 60.dp, height = 78.dp).clip(RoundedCornerShape(12.dp))
                .border(2.dp, Palette.Border, RoundedCornerShape(12.dp)),
        ) { CameraFeed() }
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
    onDebugSkip: (() -> Unit)? = null,
) {
    var index by remember { mutableIntStateOf(0) }
    // Live: advance when the head turn is detected (ML Kit yaw). Demo: advance on a timer.
    val tracker = remember(index) { TurnTracker() }
    LaunchedEffect(yaw) {
        if (yaw == null || !auto) return@LaunchedEffect
        if (tracker.update(yaw, android.os.SystemClock.elapsedRealtime())) {
            if (index < order.size - 1) index++ else onDone()
        }
    }
    LaunchedEffect(auto, yaw == null) {
        if (!auto || yaw != null) return@LaunchedEffect
        while (index < order.size - 1) {
            delay(2600)
            index++
        }
        delay(2600)
        onDone()
    }
    val dir = order[index]
    val nudge = rememberInfiniteTransition(label = "nudge")
    val shift by nudge.animateFloat(
        initialValue = 0f,
        targetValue = 1f,
        animationSpec = infiniteRepeatable(tween(700, easing = FastOutSlowInEasing), RepeatMode.Reverse),
        label = "shift",
    )
    CameraScaffold(onExit) {
        Box(Modifier.fillMaxSize()) {
            FullCamera()
            CameraArea { oval ->
                Text(
                    if (dir == TurnDir.Left) "Quay sang trái" else "Quay sang phải",
                    style = VcType.titleMedium,
                    color = Color.White,
                    textAlign = TextAlign.Center,
                    modifier = Modifier.fillMaxWidth().padding(top = 18.dp),
                )
                val sign = if (dir == TurnDir.Left) -1 else 1
                val x = if (dir == TurnDir.Left) oval.left - 28.dp else oval.left + oval.width - 36.dp
                Box(
                    Modifier.offset(x = x + (8 * shift * sign).dp, y = oval.centerY - 32.dp).size(64.dp)
                        .clip(CircleShape).background(Palette.LogoNavy.copy(alpha = 0.55f)),
                    contentAlignment = Alignment.Center,
                ) {
                    Icon(
                        if (dir == TurnDir.Left) Icons.AutoMirrored.Outlined.ArrowBack else Icons.AutoMirrored.Outlined.ArrowForward,
                        contentDescription = null,
                        tint = Color.White,
                        modifier = Modifier.size(32.dp),
                    )
                }
                Column(
                    Modifier.fillMaxWidth().offset(y = oval.bottom + 24.dp),
                    horizontalAlignment = Alignment.CenterHorizontally,
                    verticalArrangement = Arrangement.spacedBy(14.dp),
                ) {
                    GuidanceChip("Từ từ, rồi quay lại nhìn thẳng")
                    Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                        order.indices.forEach { i ->
                            Box(Modifier.size(6.dp).clip(CircleShape).background(if (i == index) Color.White else Color.White.copy(alpha = 0.35f)))
                            if (i == index) Text("${index + 1} / ${order.size}", style = VcType.labelXs, color = Color.White)
                        }
                    }
                }
                if (onDebugSkip != null) DebugButton("Bỏ qua (debug)", onDebugSkip, Modifier.align(Alignment.BottomCenter).padding(bottom = 56.dp))
                Text(
                    "Ảnh sẽ tự chụp khi bạn quay đủ",
                    style = VcType.bodySmall,
                    color = Color.White.copy(alpha = 0.85f),
                    textAlign = TextAlign.Center,
                    modifier = Modifier.fillMaxWidth().align(Alignment.BottomCenter).padding(bottom = 24.dp),
                )
            }
        }
    }
}
