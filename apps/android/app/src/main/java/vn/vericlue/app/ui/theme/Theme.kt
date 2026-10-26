package vn.vericlue.app.ui.theme

import androidx.compose.foundation.isSystemInDarkTheme
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Typography
import androidx.compose.material3.darkColorScheme
import androidx.compose.material3.lightColorScheme
import androidx.compose.runtime.Composable
import androidx.compose.runtime.CompositionLocalProvider
import androidx.compose.runtime.Immutable
import androidx.compose.runtime.ReadOnlyComposable
import androidx.compose.runtime.staticCompositionLocalOf
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.luminance
import androidx.compose.ui.graphics.lerp
import androidx.compose.ui.text.TextStyle
import androidx.compose.ui.text.font.Font
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.LineBreak
import androidx.compose.ui.unit.sp
import vn.vericlue.app.R

/** Raw palette. Names follow the Figma variable collection "VeriClue / Màu". */
object Palette {
    val Black = Color(0xFF000000)
    val Primary = Color(0xFF0B5FA5)
    val PrimaryPressed = Color(0xFF084C87)
    val Background = Color(0xFFF7F9FC)
    val Ink = Color(0xFF10243A)
    val Muted = Color(0xFF4A5B6C)
    val White = Color(0xFFFFFFFF)
    val SurfaceSubtle = Color(0xFFF0F5FA)
    val SurfaceMuted = Color(0xFFF3F6F9)
    val SurfaceInfo = Color(0xFFE6F0FA)
    val Border = Color(0xFFE0E7EF)
    val LogoNavy = Color(0xFF0C2345)
    val LogoBlue = Color(0xFF246BDF)
    val LogoLight = Color(0xFF6FA3FF)
    val DarkBg = Color(0xFF0E1822)
    val DarkSurface = Color(0xFF192A3A)
    val DarkSubtle = Color(0xFF1C2F42)
    val DarkInfo = Color(0xFF193954)
    val DarkBorder = Color(0xFF344A60)
    val DarkMuted = Color(0xFFB7C7D6)
    val DarkAccent = Color(0xFF8CC8FF)
    val Ok = Color(0xFF147343)
    val OkBg = Color(0xFFE3F3EA)
    val OkOnDark = Color(0xFF4CD497)
    val Warn = Color(0xFF8A5A00)
    val WarnBg = Color(0xFFFFF3D6)
    val WarnBorder = Color(0xFFE5B84B)
    val CameraBg = Color(0xFF13171C)
    val BankGreen = Color(0xFF0F6E56)
    val SplashBlue = Color(0xFF0B4F8A)
    val CardBackground = Color(0xFFDDEDEA)
    val CardLine = Color(0xFF9DB7B2)
    val CardPortrait = Color(0xFFB8CCC9)
    val CardChip = Color(0xFFC79A3B)
    val CardQr = Color(0xFF6C807C)

    // Screen colours for the light-reflection challenge (ADR-0016, layer 1).
    val FlashGrey = Color(0xFFD1D1D1)
    val FlashBlue = Color(0xFFCFE9FF)
    val FlashPink = Color(0xFFFFD6EF)
    val FlashYellow = Color(0xFFFFEFC2)
    val FlashMint = Color(0xFFCFF2DC)
}

/** Semantic colours. Screens use these, never the raw palette. */
@Immutable
data class VcColors(
    val isDark: Boolean,
    val background: Color,
    val surface: Color,
    val surfaceSubtle: Color,
    val surfaceInfo: Color,
    val border: Color,
    val ink: Color,
    val muted: Color,
    val primary: Color,
    val primaryPressed: Color,
    val onPrimary: Color,
    val accent: Color,
    val ok: Color,
    val onOk: Color,
    val okBg: Color,
    val warn: Color,
    val warnBg: Color,
    val warnBorder: Color,
    val disabled: Color,
    val onDisabled: Color,
    val keypad: Color,
    val key: Color,
    val bankAccent: Color,
) {
    /** Keep pressed backgrounds opaque so the state layer cannot wash out white text. */
    fun buttonPressed(container: Color): Color =
        if (container == primary) primaryPressed else lerp(container, Palette.Black, 0.14f)

    /** Switch label tone at a safe contrast boundary while the button background animates. */
    fun buttonForeground(background: Color): Color {
        fun contrast(fg: Color): Float = (maxOf(fg.luminance(), background.luminance()) + 0.05f) /
            (minOf(fg.luminance(), background.luminance()) + 0.05f)
        return when {
            background == disabled -> onDisabled
            contrast(onPrimary) >= 4.5f -> onPrimary
            contrast(onDisabled) >= 4.5f -> onDisabled
            else -> Palette.Black
        }
    }
}

val LightColors = VcColors(
    isDark = false,
    background = Palette.Background,
    surface = Palette.White,
    surfaceSubtle = Palette.SurfaceSubtle,
    surfaceInfo = Palette.SurfaceInfo,
    border = Palette.Border,
    ink = Palette.Ink,
    muted = Palette.Muted,
    primary = Palette.Primary,
    primaryPressed = Palette.PrimaryPressed,
    onPrimary = Palette.White,
    accent = Palette.Primary,
    ok = Palette.Ok,
    onOk = Palette.White,
    okBg = Palette.OkBg,
    warn = Palette.Warn,
    warnBg = Palette.WarnBg,
    warnBorder = Palette.WarnBorder,
    disabled = Palette.Border,
    onDisabled = Palette.Muted,
    keypad = Color(0xFFE8ECF0),
    key = Palette.White,
    bankAccent = Palette.BankGreen,
)

val DarkColors = VcColors(
    isDark = true,
    background = Palette.DarkBg,
    surface = Palette.DarkSurface,
    surfaceSubtle = Palette.DarkSubtle,
    surfaceInfo = Palette.DarkInfo,
    border = Palette.DarkBorder,
    ink = Palette.White,
    muted = Palette.DarkMuted,
    primary = Palette.Primary,
    primaryPressed = Palette.PrimaryPressed,
    onPrimary = Palette.White,
    accent = Palette.DarkAccent,
    ok = Palette.OkOnDark,
    onOk = Palette.DarkBg,
    okBg = Color(0xFF173A2B),
    warn = Color(0xFFFFD27A),
    warnBg = Color(0xFF3A2E12),
    warnBorder = Palette.Warn,
    disabled = Palette.DarkBorder,
    onDisabled = Palette.DarkMuted,
    keypad = Color(0xFF16212C),
    key = Palette.DarkSurface,
    bankAccent = Palette.OkOnDark,
)

val BeVietnamPro = FontFamily(
    Font(R.font.be_vietnam_pro_regular, FontWeight.Normal),
    Font(R.font.be_vietnam_pro_medium, FontWeight.Medium),
    Font(R.font.be_vietnam_pro_semibold, FontWeight.SemiBold),
    Font(R.font.be_vietnam_pro_bold, FontWeight.Bold),
)

/** Text styles. Names follow the Figma text styles. */
object VcType {
    private fun style(weight: FontWeight, size: Int, lineHeight: Float) = TextStyle(
        fontFamily = BeVietnamPro,
        fontWeight = weight,
        fontSize = size.sp,
        lineHeight = (size * lineHeight).sp,
    )

    // Headings balance their lines so a single word is not left alone on the last line.
    val titleLarge = style(FontWeight.Bold, 28, 1.4f).copy(lineBreak = LineBreak.Heading, letterSpacing = (-0.4).sp)
    val titleMedium = style(FontWeight.SemiBold, 22, 1.4f).copy(lineBreak = LineBreak.Heading, letterSpacing = (-0.2).sp)
    val section = style(FontWeight.SemiBold, 16, 1.4f)
    val body = style(FontWeight.Normal, 15, 1.5f)
    val bodyStrong = style(FontWeight.SemiBold, 15, 1.5f)
    val bodySmall = style(FontWeight.Normal, 14, 1.5f)
    val caption = style(FontWeight.Normal, 13, 1.5f)
    val footnote = style(FontWeight.Normal, 12, 1.5f)
    val button = style(FontWeight.SemiBold, 15, 1.4f)
    val label = style(FontWeight.SemiBold, 14, 1.4f)
    val labelSmall = style(FontWeight.SemiBold, 13, 1.4f)
    val labelXs = style(FontWeight.SemiBold, 12, 1.4f)
}

val LocalVcColors = staticCompositionLocalOf { LightColors }

object Vc {
    val colors: VcColors
        @Composable @ReadOnlyComposable
        get() = LocalVcColors.current

    val motion: VcMotion
        @Composable @ReadOnlyComposable
        get() = LocalVcMotion.current ?: VcMotion(enabled = true)
}

@Composable
fun VcTheme(dark: Boolean = isSystemInDarkTheme(), motionEnabled: Boolean? = null, content: @Composable () -> Unit) {
    val colors = if (dark) DarkColors else LightColors
    val motion = motionEnabled?.let { VcMotion(it) } ?: LocalVcMotion.current ?: rememberSystemMotion()
    val scheme = if (dark) {
        darkColorScheme(
            primary = colors.accent,
            onPrimary = colors.background,
            background = colors.background,
            surface = colors.surface,
            onSurface = colors.ink,
            onBackground = colors.ink,
        )
    } else {
        lightColorScheme(
            primary = colors.primary,
            onPrimary = colors.onPrimary,
            background = colors.background,
            surface = colors.surface,
            onSurface = colors.ink,
            onBackground = colors.ink,
        )
    }
    CompositionLocalProvider(LocalVcColors provides colors, LocalVcMotion provides motion) {
        MaterialTheme(
            colorScheme = scheme,
            typography = Typography(bodyLarge = VcType.body, bodyMedium = VcType.bodySmall),
            content = content,
        )
    }
}
