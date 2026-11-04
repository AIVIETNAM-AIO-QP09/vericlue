package vn.vericlue.app.ui.components

import androidx.compose.animation.core.LinearEasing
import androidx.compose.animation.core.RepeatMode
import androidx.compose.animation.core.animateFloat
import androidx.compose.animation.core.infiniteRepeatable
import androidx.compose.animation.core.rememberInfiniteTransition
import androidx.compose.animation.core.tween
import androidx.compose.foundation.Canvas
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.draw.drawBehind
import androidx.compose.ui.geometry.CornerRadius
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.geometry.Size
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.Shape
import androidx.compose.ui.graphics.drawscope.rotate
import androidx.compose.ui.semantics.clearAndSetSemantics
import androidx.compose.ui.unit.dp
import vn.vericlue.app.ui.theme.Vc
import vn.vericlue.app.ui.theme.VcStage
import androidx.compose.animation.core.Animatable
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.remember
import androidx.compose.ui.Alignment
import androidx.compose.ui.graphics.StrokeCap
import androidx.compose.ui.graphics.drawscope.Stroke
import androidx.compose.ui.unit.Dp
import kotlin.math.cos
import kotlin.math.sin

/** Night page gradient shared by every non-camera screen. */
fun Modifier.stageBackground(): Modifier = drawBehind {
    drawRect(Brush.verticalGradient(listOf(VcStage.top, VcStage.mid, VcStage.pageBottom)))
}

/**
 * Decorative depth behind ordinary screens: two soft slabs at the edges and a light pool that drift
 * slowly. Kept faint and away from the reading column; reduced motion holds a single still pose.
 */
@Composable
fun StageAmbient(modifier: Modifier = Modifier) {
    val motion = Vc.motion
    val drift = if (motion.enabled) {
        rememberInfiniteTransition(label = "stage-ambient").animateFloat(0f, 1f,
            infiniteRepeatable(tween(18_000, easing = LinearEasing), RepeatMode.Reverse), label = "drift").value
    } else .5f
    Canvas(modifier.fillMaxSize().clearAndSetSemantics {}) {
        val w = size.width
        fun slab(cx: Float, cy: Float, sw: Float, sh: Float, turn: Float, alpha: Float) {
            val c = Offset(cx, cy)
            rotate(turn, c) {
                val origin = Offset(cx - sw / 2, cy - sh / 2)
                drawRoundRect(Brush.verticalGradient(listOf(VcStage.slab, VcStage.slabDeep), origin.y, origin.y + sh),
                    origin, Size(sw, sh), CornerRadius(sh / 2), alpha = alpha)
                drawRoundRect(Color.White, Offset(origin.x + sh * .3f, origin.y + sh * .14f),
                    Size(sw - sh * .6f, sh * .14f), CornerRadius(sh * .07f), alpha = alpha * .35f)
            }
        }
        slab(w * (1.02f + .03f * drift), w * (.10f + .04f * drift), w * .95f, w * .26f, 24f + 4f * drift, .42f)
        slab(w * (-.08f - .03f * drift), size.height * (.72f - .03f * drift), w * .8f, w * .22f, -20f - 3f * drift, .30f)
        val pool = Offset(w * (.78f - .1f * drift), w * .28f)
        drawCircle(Brush.radialGradient(listOf(VcStage.cta.copy(alpha = .16f), Color.Transparent), pool, w * .55f), w * .55f, pool)
    }
}

/**
 * Glass reading surface: deep navy tint with a light top edge, no runtime blur. The tint stays dark
 * enough that muted and link text keep 4.5:1 over any part of the page gradient.
 */
fun Modifier.glass(shape: Shape = RoundedCornerShape(24.dp)): Modifier = clip(shape)
    .background(Brush.verticalGradient(listOf(VcStage.cardTop, VcStage.cardBottom)))
    .border(1.dp, Brush.verticalGradient(listOf(VcStage.glassBorder, Color.White.copy(alpha = .06f))), shape)

/**
 * Ring of the reflection-challenge colours around a disc. Purely ornamental; it never shows
 * capture progress or a verification outcome.
 */
@Composable
fun LivenessRing(
    active: Boolean, size: Dp,
    arc: List<Color> = Vc.colors.spectrum, tick: Color = Vc.colors.border, disc: Color = Vc.colors.surfaceSubtle,
    glow: Color = Vc.colors.accent, ticks: Boolean = true, content: @Composable () -> Unit,
) {
    val motion = Vc.motion
    val sweep = remember { Animatable(if (motion.enabled) 0f else 1f) }
    LaunchedEffect(motion.enabled) { sweep.animateTo(1f, motion.tween(900, delayMillis = 200)) }
    val spin = if (motion.enabled && active) {
        rememberInfiniteTransition(label = "liveness-ring")
            .animateFloat(0f, 360f, infiniteRepeatable(tween(14_000, easing = LinearEasing)), label = "ring-spin").value
    } else 0f
    val colors = if (active) arc else listOf(tick, tick)
    val halo = (if (active) glow else tick).copy(alpha = .18f)
    val arcInset = if (ticks) 14.dp else 3.dp
    Box(Modifier.size(size).clearAndSetSemantics {}, contentAlignment = Alignment.Center) {
        Canvas(Modifier.matchParentSize()) {
            val r = this.size.minDimension / 2
            drawCircle(Brush.radialGradient(listOf(halo, Color.Transparent), center, r), r)
            if (ticks) {
                val tickOuter = r - 1.dp.toPx()
                repeat(60) { i ->
                    val a = Math.toRadians(i * 6.0)
                    val dir = Offset(cos(a).toFloat(), sin(a).toFloat())
                    val len = if (i % 5 == 0) 7.dp.toPx() else 3.dp.toPx()
                    drawLine(tick, center + dir * (tickOuter - len), center + dir * tickOuter,
                        strokeWidth = 1.dp.toPx(), cap = StrokeCap.Round)
                }
            }
            val inset = arcInset.toPx()
            rotate(spin) {
                drawArc(Brush.sweepGradient(colors + colors.first(), center), -90f, 360f * sweep.value, useCenter = false,
                    topLeft = Offset(inset, inset), size = Size(this.size.width - 2 * inset, this.size.height - 2 * inset),
                    style = Stroke(if (ticks) 4.dp.toPx() else 3.dp.toPx(), cap = StrokeCap.Round))
            }
        }
        Box(Modifier.size(size - arcInset * 2 - 8.dp).clip(CircleShape).background(disc), contentAlignment = Alignment.Center) {
            content()
        }
    }
}

/**
 * Horizontal light beam sweeping a disc while the server works: reads as "analysing" without
 * claiming progress. Reduced motion parks the beam across the centre.
 */
@Composable
fun ScanBeam(modifier: Modifier = Modifier, color: Color = VcStage.cta) {
    val motion = Vc.motion
    val y = if (motion.enabled) {
        rememberInfiniteTransition(label = "scan-beam").animateFloat(0.1f, 0.9f,
            infiniteRepeatable(tween(1600), RepeatMode.Reverse), label = "beam").value
    } else .5f
    Canvas(modifier.clearAndSetSemantics {}) {
        val h = size.height * y
        drawRect(Brush.verticalGradient(listOf(Color.Transparent, color.copy(alpha = .35f), Color.Transparent),
            h - 22.dp.toPx(), h + 22.dp.toPx()))
        drawLine(color, Offset(size.width * .12f, h), Offset(size.width * .88f, h), 2.dp.toPx(), StrokeCap.Round)
    }
}

/**
 * One-off burst of challenge-colour particles around a success mark. Decorative only; with reduced
 * motion it shows the settled ring of dots immediately.
 */
@Composable
fun SpectrumBurst(modifier: Modifier = Modifier) {
    val motion = Vc.motion
    val t = remember { Animatable(if (motion.enabled) 0f else 1f) }
    LaunchedEffect(motion.enabled) { t.animateTo(1f, motion.tween(1400, delayMillis = 250)) }
    Canvas(modifier.clearAndSetSemantics {}) {
        val r0 = size.minDimension * .34f
        val p = t.value
        val travel = 1f - (1f - p) * (1f - p) * (1f - p)
        repeat(24) { i ->
            val angle = Math.toRadians(i * 15.0 + 7.5 * (i % 2))
            val dist = r0 + size.minDimension * (.10f + .06f * (i % 3)) * travel
            val dot = Offset(center.x + cos(angle).toFloat() * dist, center.y + sin(angle).toFloat() * dist)
            val fade = if (motion.enabled) (1f - p * .45f) else .55f
            drawCircle(VcStage.ring[i % 4], radius = (if (i % 3 == 0) 4.dp else 2.5.dp).toPx(), center = dot, alpha = fade)
        }
    }
}
