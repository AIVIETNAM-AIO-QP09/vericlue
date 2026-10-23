package vn.vericlue.app.ui.screens

import androidx.activity.compose.BackHandler
import androidx.compose.animation.core.Animatable
import androidx.compose.animation.core.FastOutSlowInEasing
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
import vn.vericlue.app.flow.TurnDir
import vn.vericlue.app.ui.components.Banner
import vn.vericlue.app.ui.components.CameraArea
import vn.vericlue.app.ui.components.FakeCameraFeed
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
            LinkButton("Bỏ qua nháy màu, chuyển sang đọc câu", onSkipFlash)
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

enum class FramingState { LowLight, TooFar, Good }

@Composable
fun FramingScreen(onExit: () -> Unit, onCaptured: () -> Unit, start: FramingState = FramingState.LowLight, auto: Boolean = true) {
    var state by remember { mutableStateOf(start) }
    LaunchedEffect(auto) {
        if (!auto) return@LaunchedEffect
        while (state != FramingState.Good) {
            delay(1600)
            state = FramingState.entries[state.ordinal + 1]
        }
        delay(1400)
        onCaptured()
    }
    CameraScaffold(onExit) {
        Box(Modifier.fillMaxSize()) {
            Box(Modifier.fillMaxSize()) {
                FakeCameraFeed(faceScale = if (state == FramingState.TooFar) 0.6f else 1f, dim = if (state == FramingState.LowLight) 0.45f else 0f)
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
                        FramingState.LowLight -> GuidanceChip("Ra chỗ sáng hơn", Icons.Outlined.WbSunny, Tone.Warn)
                        FramingState.TooFar -> GuidanceChip("Lại gần hơn", Icons.Outlined.OpenInFull)
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
            }
        }
    }
}

// ── Task 1: hold still (grey → colour flash → follow the dot) ────────────────

private val flashColors = listOf(Palette.FlashBlue, Palette.FlashPink, Palette.FlashYellow, Palette.FlashMint)

/** Phase index: 0 = grey, 1..4 = flash colours, 5 = follow the dot. */
@Composable
fun HoldStillScreen(onStop: () -> Unit, onDone: () -> Unit, startPhase: Int = 0, auto: Boolean = true) {
    var phase by remember { mutableIntStateOf(startPhase) }
    LaunchedEffect(auto) {
        if (!auto) return@LaunchedEffect
        while (phase < 5) {
            delay(if (phase == 0) 1200 else 900)
            phase++
        }
        delay(6400)
        onDone()
    }
    BackHandler(onBack = onStop)
    // The flash screens are light whatever the system theme, so the light palette is forced.
    CompositionLocalProvider(LocalVcColors provides LightColors) {
        val bg = when (phase) {
            0 -> Palette.FlashGrey
            in 1..4 -> flashColors[phase - 1]
            else -> Color.White
        }
        SystemBarIcons(bg)
        Column(Modifier.fillMaxSize().background(bg).statusBarsPadding()) {
            TopBar(onStop)
            StepProgress(2, stepLabel(2))
            Column(
                Modifier.weight(1f).fillMaxWidth().padding(horizontal = 20.dp, vertical = 20.dp),
                horizontalAlignment = Alignment.CenterHorizontally,
                verticalArrangement = Arrangement.spacedBy(20.dp),
            ) {
                if (phase < 5) {
                    Text(
                        if (phase == 0) "Giữ yên, nhìn thẳng" else "Giữ yên",
                        style = VcType.titleMedium,
                        color = Palette.Ink,
                    )
                    OvalPreview(progress = (phase + 1) / 6f)
                } else {
                    Text(
                        "Giữ đầu yên, chỉ đưa mắt theo chấm sáng",
                        style = VcType.titleMedium,
                        color = Palette.Ink,
                        modifier = Modifier.fillMaxWidth(),
                    )
                    FollowDot(Modifier.fillMaxWidth().weight(1f, fill = false).height(220.dp), running = auto)
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

@Composable
private fun OvalPreview(progress: Float) {
    Box(Modifier.size(width = 196.dp, height = 252.dp), contentAlignment = Alignment.Center) {
        Box(Modifier.size(width = 172.dp, height = 228.dp).clip(androidx.compose.foundation.shape.GenericShape { s, _ -> addOval(androidx.compose.ui.geometry.Rect(Offset.Zero, s)) })) {
            FakeCameraFeed()
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

/** The dot follows a random path; the user follows it with the eyes only (ADR-0016, layer 2). */
@Composable
private fun FollowDot(modifier: Modifier, running: Boolean) {
    BoxWithConstraints(modifier) {
        val w = maxWidth.value
        val h = maxHeight.value
        val pos = remember { Animatable(Offset(w * 0.2f, h * 0.5f), Offset.VectorConverter) }
        var steps by remember { mutableIntStateOf(0) }
        LaunchedEffect(running) {
            if (!running) return@LaunchedEffect
            val rnd = java.util.Random()
            repeat(7) {
                val target = Offset(w * (0.1f + rnd.nextFloat() * 0.8f), h * (0.15f + rnd.nextFloat() * 0.6f))
                pos.animateTo(target, tween(850, easing = FastOutSlowInEasing))
                steps++
            }
        }
        Box(
            Modifier.align(Alignment.TopEnd).size(width = 60.dp, height = 78.dp).clip(RoundedCornerShape(12.dp))
                .border(2.dp, Palette.Border, RoundedCornerShape(12.dp)),
        ) { FakeCameraFeed() }
        Box(
            Modifier.offset(x = (pos.value.x - 12).dp, y = (pos.value.y - 12).dp).size(24.dp)
                .clip(CircleShape).background(Palette.Primary.copy(alpha = 0.18f)),
            contentAlignment = Alignment.Center,
        ) { Box(Modifier.size(14.dp).clip(CircleShape).background(Palette.Primary)) }
        LinearProgressIndicator(
            progress = { steps / 7f },
            modifier = Modifier.fillMaxWidth().height(3.dp).align(Alignment.BottomCenter),
            color = Palette.Primary,
            trackColor = Palette.Border,
        )
    }
}

// ── Task 2: turn left / right in server order ────────────────────────────────

@Composable
fun TurnHeadScreen(order: List<TurnDir>, onExit: () -> Unit, onDone: () -> Unit, auto: Boolean = true) {
    var index by remember { mutableIntStateOf(0) }
    LaunchedEffect(auto) {
        if (!auto) return@LaunchedEffect
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
