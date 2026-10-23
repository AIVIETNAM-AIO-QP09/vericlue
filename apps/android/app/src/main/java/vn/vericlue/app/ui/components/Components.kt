package vn.vericlue.app.ui.components

import android.app.Activity
import androidx.compose.animation.AnimatedContent
import androidx.compose.animation.core.Animatable
import androidx.compose.animation.core.FastOutSlowInEasing
import androidx.compose.animation.core.tween
import androidx.compose.animation.fadeIn
import androidx.compose.animation.fadeOut
import androidx.compose.animation.scaleIn
import androidx.compose.animation.togetherWith
import androidx.compose.foundation.BorderStroke
import androidx.compose.foundation.Image
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.ColumnScope
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxHeight
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.navigationBarsPadding
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.statusBarsPadding
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.outlined.ArrowBack
import androidx.compose.material.icons.automirrored.outlined.Backspace
import androidx.compose.material.icons.outlined.Check
import androidx.compose.material.icons.outlined.CheckCircle
import androidx.compose.material.icons.outlined.Info
import androidx.compose.material.icons.outlined.WarningAmber
import androidx.compose.material3.Button
import androidx.compose.material3.ButtonDefaults
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.SideEffect
import androidx.compose.runtime.remember
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.ColorFilter
import androidx.compose.ui.graphics.luminance
import androidx.compose.ui.graphics.vector.ImageVector
import androidx.compose.ui.platform.LocalView
import androidx.compose.ui.res.painterResource
import androidx.compose.ui.semantics.Role
import androidx.compose.ui.text.SpanStyle
import androidx.compose.ui.text.buildAnnotatedString
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.text.withStyle
import androidx.compose.ui.unit.Dp
import androidx.compose.ui.unit.dp
import androidx.core.view.WindowCompat
import vn.vericlue.app.R
import vn.vericlue.app.ui.theme.Palette
import vn.vericlue.app.ui.theme.Vc
import vn.vericlue.app.ui.theme.VcType

/** Sets status/navigation bar icon colour to match the screen background. */
@Composable
fun SystemBarIcons(background: Color) {
    val view = LocalView.current
    if (view.isInEditMode) return
    val lightBg = background.luminance() > 0.5f
    SideEffect {
        val window = (view.context as? Activity)?.window ?: return@SideEffect
        val controller = WindowCompat.getInsetsController(window, view)
        controller.isAppearanceLightStatusBars = lightBg
        controller.isAppearanceLightNavigationBars = lightBg
    }
}

@Composable
fun VcLogo(modifier: Modifier = Modifier, height: Dp = 22.dp, onDark: Boolean = Vc.colors.isDark) {
    Image(
        painter = painterResource(if (onDark) R.drawable.logo_lockup_on_dark else R.drawable.logo_lockup),
        contentDescription = "VeriClue",
        modifier = modifier.height(height).width(height * 441f / 75f),
    )
}

@Composable
fun TopBar(onBack: (() -> Unit)?, showLogo: Boolean = true, title: (@Composable () -> Unit)? = null) {
    val c = Vc.colors
    Row(
        Modifier.fillMaxWidth().height(56.dp).padding(horizontal = 4.dp),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        if (onBack != null) {
            IconButton(onClick = onBack) {
                Icon(Icons.AutoMirrored.Outlined.ArrowBack, contentDescription = "Quay lại", tint = c.ink)
            }
        } else {
            Spacer(Modifier.width(16.dp))
        }
        when {
            title != null -> title()
            showLogo -> VcLogo(Modifier.padding(start = 4.dp))
        }
    }
}

/** Remembers the last step shown so the bar only animates when moving forward. */
private object StepMemory {
    var last = 0
}

@Composable
fun StepProgress(step: Int, label: String, total: Int = 3) {
    val c = Vc.colors
    val shownBefore = remember { StepMemory.last }
    Column(Modifier.fillMaxWidth().padding(start = 20.dp, end = 20.dp, top = 4.dp, bottom = 4.dp)) {
        Row(horizontalArrangement = Arrangement.spacedBy(6.dp)) {
            for (i in 1..total) {
                val target = if (i <= step) 1f else 0f
                val fill = remember { Animatable(if (i <= step && i <= shownBefore) 1f else 0f) }
                LaunchedEffect(target) { fill.animateTo(target, tween(500, easing = FastOutSlowInEasing)) }
                Box(
                    Modifier.weight(1f).height(4.dp).clip(RoundedCornerShape(2.dp)).background(c.border),
                ) {
                    Box(Modifier.fillMaxHeight().fillMaxWidth(fill.value).background(c.accent))
                }
            }
        }
        Text(
            buildAnnotatedString {
                append("Bước $step/$total · ")
                withStyle(SpanStyle(fontWeight = FontWeight.SemiBold, color = c.ink)) { append(label) }
            },
            style = VcType.footnote,
            color = c.muted,
            modifier = Modifier.padding(top = 8.dp),
        )
    }
    SideEffect { StepMemory.last = step }
}

fun stepLabel(step: Int): String = when (step) {
    1 -> "Danh tính"
    2 -> "Khuôn mặt"
    else -> "Giọng nói"
}

/**
 * Standard screen: top bar, optional progress, content and a bottom action area.
 * [centered] puts the content in the middle (result and error screens).
 */
@Composable
fun VcScreen(
    onBack: (() -> Unit)? = null,
    step: Int? = null,
    showLogo: Boolean = true,
    centered: Boolean = false,
    background: Color = Vc.colors.background,
    actions: (@Composable ColumnScope.() -> Unit)? = null,
    bottom: (@Composable () -> Unit)? = null,
    content: @Composable ColumnScope.() -> Unit,
) {
    SystemBarIcons(background)
    Column(Modifier.fillMaxSize().background(background).statusBarsPadding()) {
        TopBar(onBack, showLogo)
        if (step != null) StepProgress(step, stepLabel(step))
        val body = if (centered) {
            Modifier.weight(1f).fillMaxWidth().padding(horizontal = 20.dp, vertical = 24.dp)
        } else {
            Modifier.weight(1f).fillMaxWidth().verticalScroll(rememberScrollState())
                .padding(horizontal = 20.dp, vertical = 24.dp)
        }
        Column(
            body,
            verticalArrangement = if (centered) {
                Arrangement.spacedBy(24.dp, Alignment.CenterVertically)
            } else {
                Arrangement.spacedBy(24.dp)
            },
            horizontalAlignment = if (centered) Alignment.CenterHorizontally else Alignment.Start,
            content = content,
        )
        if (actions != null) {
            Column(
                Modifier.fillMaxWidth().padding(start = 20.dp, end = 20.dp, top = 8.dp, bottom = 16.dp),
                verticalArrangement = Arrangement.spacedBy(8.dp),
                content = actions,
            )
        }
        if (bottom != null) bottom()
        Spacer(Modifier.navigationBarsPadding())
    }
}

@Composable
fun TitleBlock(title: String, body: String? = null, eyebrow: String? = null, centered: Boolean = false) {
    val c = Vc.colors
    val align = if (centered) TextAlign.Center else TextAlign.Start
    Column(
        Modifier.fillMaxWidth(),
        verticalArrangement = Arrangement.spacedBy(8.dp),
        horizontalAlignment = if (centered) Alignment.CenterHorizontally else Alignment.Start,
    ) {
        if (eyebrow != null) Text(eyebrow, style = VcType.labelXs, color = c.accent)
        Text(title, style = VcType.titleLarge, color = c.ink, textAlign = align)
        if (body != null) Text(body, style = VcType.body, color = c.muted, textAlign = align)
    }
}

@Composable
fun PrimaryButton(
    text: String,
    onClick: () -> Unit,
    modifier: Modifier = Modifier,
    enabled: Boolean = true,
    container: Color = Vc.colors.primary,
) {
    val c = Vc.colors
    Button(
        onClick = onClick,
        enabled = enabled,
        modifier = modifier.fillMaxWidth().height(52.dp),
        shape = RoundedCornerShape(12.dp),
        colors = ButtonDefaults.buttonColors(
            containerColor = container,
            contentColor = Color.White,
            disabledContainerColor = c.disabled,
            disabledContentColor = c.onDisabled,
        ),
    ) { Text(text, style = VcType.button) }
}

@Composable
fun SecondaryButton(text: String, onClick: () -> Unit, modifier: Modifier = Modifier) {
    val c = Vc.colors
    OutlinedButton(
        onClick = onClick,
        modifier = modifier.fillMaxWidth().height(52.dp),
        shape = RoundedCornerShape(12.dp),
        border = BorderStroke(1.dp, c.border),
        colors = ButtonDefaults.outlinedButtonColors(
            containerColor = if (c.isDark) Color.Transparent else c.surfaceInfo,
            contentColor = c.accent,
        ),
    ) { Text(text, style = VcType.button) }
}

@Composable
fun LinkButton(text: String, onClick: () -> Unit, modifier: Modifier = Modifier) {
    TextButton(onClick = onClick, modifier = modifier.fillMaxWidth()) {
        Text(text, style = VcType.label, color = Vc.colors.accent, textAlign = TextAlign.Center)
    }
}

enum class Tone { Info, Warn, Ok }

@Composable
fun Banner(text: String, modifier: Modifier = Modifier, tone: Tone = Tone.Info, icon: ImageVector? = null) {
    val c = Vc.colors
    val (bg, border, fg) = when (tone) {
        Tone.Info -> Triple(c.surfaceSubtle, c.border, c.muted)
        Tone.Warn -> Triple(c.warnBg, c.warnBorder, c.warn)
        Tone.Ok -> Triple(c.okBg, c.okBg, c.ok)
    }
    val glyph = icon ?: when (tone) {
        Tone.Info -> Icons.Outlined.Info
        Tone.Warn -> Icons.Outlined.WarningAmber
        Tone.Ok -> Icons.Outlined.CheckCircle
    }
    Row(
        modifier.fillMaxWidth().clip(RoundedCornerShape(12.dp)).background(bg)
            .border(1.dp, border, RoundedCornerShape(12.dp)).padding(12.dp),
        horizontalArrangement = Arrangement.spacedBy(10.dp),
    ) {
        Icon(glyph, contentDescription = null, tint = fg, modifier = Modifier.size(18.dp))
        Text(text, style = VcType.caption, color = fg)
    }
}

/** Icon + text row on a subtle card (intro, permission screens). */
@Composable
fun InfoRow(icon: ImageVector, text: String, detail: String? = null) {
    val c = Vc.colors
    Row(
        Modifier.fillMaxWidth().clip(RoundedCornerShape(12.dp)).background(c.surfaceSubtle).padding(16.dp),
        horizontalArrangement = Arrangement.spacedBy(12.dp),
    ) {
        Icon(icon, contentDescription = null, tint = c.accent, modifier = Modifier.size(20.dp))
        Column(verticalArrangement = Arrangement.spacedBy(4.dp)) {
            Text(text, style = if (detail != null) VcType.label else VcType.bodySmall, color = c.ink)
            if (detail != null) Text(detail, style = VcType.caption, color = c.muted)
        }
    }
}

@Composable
fun StatusBadge(icon: ImageVector?, tone: Tone? = null, spinning: Boolean = false) {
    val c = Vc.colors
    val (bg, fg) = when (tone) {
        Tone.Ok -> c.okBg to c.ok
        Tone.Warn -> c.warnBg to c.warn
        else -> c.surfaceInfo to c.accent
    }
    Box(Modifier.size(96.dp).clip(CircleShape).background(bg), contentAlignment = Alignment.Center) {
        if (spinning) {
            CircularProgressIndicator(color = fg, trackColor = fg.copy(alpha = 0.15f), strokeWidth = 3.dp, modifier = Modifier.size(44.dp))
        } else if (icon != null) {
            Icon(icon, contentDescription = null, tint = fg, modifier = Modifier.size(44.dp))
        }
    }
}

enum class RowState { Done, Doing, Waiting }

/** Card listing steps (checking screen) or facts (result screens). */
@Composable
fun ChecklistCard(title: String?, rows: List<Triple<ImageVector?, String, RowState?>>, trailing: List<String?> = emptyList()) {
    val c = Vc.colors
    Column(
        Modifier.fillMaxWidth().clip(RoundedCornerShape(16.dp)).background(c.surfaceSubtle).padding(18.dp),
        verticalArrangement = Arrangement.spacedBy(14.dp),
    ) {
        if (title != null) Text(title, style = VcType.labelSmall, color = c.muted)
        rows.forEachIndexed { i, (icon, label, state) ->
            Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(12.dp)) {
                Box(Modifier.size(24.dp), contentAlignment = Alignment.Center) {
                    if (state != null) {
                        AnimatedContent(
                            targetState = state,
                            transitionSpec = { (fadeIn(tween(250)) + scaleIn(initialScale = 0.6f)) togetherWith fadeOut(tween(150)) },
                            label = "row-state",
                        ) { s -> StateIcon(s) }
                    } else if (icon != null) {
                        Icon(icon, contentDescription = null, tint = c.accent, modifier = Modifier.size(22.dp))
                    }
                }
                Text(label, style = VcType.bodyStrong, color = c.ink, modifier = Modifier.weight(1f))
                val trail = trailing.getOrNull(i) ?: state?.let {
                    when (it) {
                        RowState.Done -> "Xong"
                        RowState.Doing -> "Đang xử lý"
                        RowState.Waiting -> "Chờ"
                    }
                }
                if (trail != null) {
                    Text(trail, style = VcType.caption, color = if (state == RowState.Done) c.ok else c.muted)
                }
            }
        }
    }
}

@Composable
private fun StateIcon(state: RowState) {
    val c = Vc.colors
    when (state) {
        RowState.Done -> Box(Modifier.size(24.dp).clip(CircleShape).background(c.ok), contentAlignment = Alignment.Center) {
            Icon(Icons.Outlined.Check, contentDescription = null, tint = Color.White, modifier = Modifier.size(16.dp))
        }
        RowState.Doing -> CircularProgressIndicator(
            color = c.accent,
            trackColor = c.accent.copy(alpha = 0.2f),
            strokeWidth = 2.5.dp,
            modifier = Modifier.size(20.dp),
        )
        RowState.Waiting -> Box(Modifier.size(20.dp).border(2.dp, c.border, CircleShape))
    }
}

/** Android-style number pad. Digits only: phone and OTP screens. */
@Composable
fun NumericKeypad(onDigit: (Char) -> Unit, onBackspace: () -> Unit, onDone: () -> Unit) {
    val c = Vc.colors
    val letters = mapOf('2' to "ABC", '3' to "DEF", '4' to "GHI", '5' to "JKL", '6' to "MNO", '7' to "PQRS", '8' to "TUV", '9' to "WXYZ", '0' to "+")
    val rows = listOf("123", "456", "789")
    Column(
        Modifier.fillMaxWidth().background(c.keypad).padding(6.dp),
        verticalArrangement = Arrangement.spacedBy(6.dp),
    ) {
        rows.forEach { row ->
            Row(horizontalArrangement = Arrangement.spacedBy(6.dp)) {
                row.forEach { d -> Key(Modifier.weight(1f), c.key, { onDigit(d) }) { DigitLabel(d, letters[d]) } }
            }
        }
        Row(horizontalArrangement = Arrangement.spacedBy(6.dp)) {
            Key(Modifier.weight(1f), c.border, onBackspace) {
                Icon(Icons.AutoMirrored.Outlined.Backspace, contentDescription = "Xóa", tint = c.ink)
            }
            Key(Modifier.weight(1f), c.key, { onDigit('0') }) { DigitLabel('0', letters['0']) }
            Key(Modifier.weight(1f), c.primary, onDone) {
                Icon(Icons.Outlined.Check, contentDescription = "Xong", tint = Color.White)
            }
        }
    }
}

@Composable
private fun Key(modifier: Modifier, color: Color, onClick: () -> Unit, content: @Composable () -> Unit) {
    Box(
        modifier.height(50.dp).clip(RoundedCornerShape(8.dp)).background(color)
            .clickable(role = Role.Button, onClick = onClick),
        contentAlignment = Alignment.Center,
    ) { content() }
}

@Composable
private fun DigitLabel(d: Char, sub: String?) {
    val c = Vc.colors
    Column(horizontalAlignment = Alignment.CenterHorizontally) {
        Text(d.toString(), style = VcType.titleMedium.copy(fontWeight = FontWeight.Medium), color = c.ink)
        if (sub != null) Text(sub, style = VcType.footnote.copy(fontSize = VcType.footnote.fontSize * 0.75f), color = c.muted)
    }
}

/** Six OTP boxes; amber when the code was wrong (never red). */
@Composable
fun OtpBoxes(code: String, error: Boolean) {
    val c = Vc.colors
    Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(8.dp)) {
        for (i in 0 until 6) {
            val ch = code.getOrNull(i)
            val active = i == code.length
            val (bg, border) = when {
                error -> c.warnBg to c.warnBorder
                ch != null || active -> c.surface to c.accent
                else -> c.surface to c.border
            }
            Box(
                Modifier.weight(1f).height(56.dp).clip(RoundedCornerShape(10.dp)).background(bg)
                    .border(if (active && !error) 2.dp else 1.dp, border, RoundedCornerShape(10.dp)),
                contentAlignment = Alignment.Center,
            ) {
                Text(ch?.toString() ?: "–", style = VcType.titleMedium, color = if (ch != null) c.ink else c.muted)
            }
        }
    }
}

/** Pill with an icon, used on the camera screens. */
@Composable
fun GuidanceChip(text: String, icon: ImageVector? = null, tone: Tone? = null, modifier: Modifier = Modifier) {
    val (bg, fg) = when (tone) {
        Tone.Ok -> Palette.Ok to Color.White
        Tone.Warn -> Palette.WarnBg to Palette.Warn
        else -> Color.White to Palette.Ink
    }
    Row(
        modifier.clip(RoundedCornerShape(50)).background(bg).padding(horizontal = 14.dp, vertical = 10.dp),
        verticalAlignment = Alignment.CenterVertically,
        horizontalArrangement = Arrangement.spacedBy(8.dp),
    ) {
        if (icon != null) Icon(icon, contentDescription = null, tint = fg, modifier = Modifier.size(18.dp))
        Text(text, style = VcType.label, color = fg)
    }
}
