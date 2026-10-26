package vn.vericlue.app

import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.luminance
import androidx.compose.ui.graphics.lerp
import androidx.compose.ui.graphics.compositeOver
import org.junit.Assert.assertTrue
import org.junit.Test
import vn.vericlue.app.ui.theme.DarkColors
import vn.vericlue.app.ui.theme.LightColors
import vn.vericlue.app.ui.theme.VcType
import vn.vericlue.app.ui.theme.Palette

class ThemeAccessibilityTest {
    @Test fun heldPrimaryButtonsRemainReadableWithTheMaterialStateLayer() {
        listOf(LightColors, DarkColors).forEach { c ->
            listOf(c.primary, Palette.BankGreen).forEach { container ->
                val pressed = c.buttonPressed(container)
                for (i in 0..10) {
                    val bg = c.onPrimary.copy(alpha = i / 100f).compositeOver(pressed)
                    val fg = c.buttonForeground(pressed)
                    val contrast = (maxOf(fg.luminance(), bg.luminance()) + 0.05f) /
                        (minOf(fg.luminance(), bg.luminance()) + 0.05f)
                    assertTrue("Held button dark=${c.isDark}, layer=$i: $contrast", contrast >= 4.5f)
                }
            }
        }
    }

    @Test fun buttonLabelStaysReadableThroughoutEnableAndDisable() {
        listOf(LightColors, DarkColors).forEach { c ->
            for (i in 0..100) {
                val bg = lerp(c.disabled, c.primary, i / 100f)
                val fg = c.buttonForeground(bg)
                val contrast = (maxOf(fg.luminance(), bg.luminance()) + 0.05f) /
                    (minOf(fg.luminance(), bg.luminance()) + 0.05f)
                assertTrue("Button transition dark=${c.isDark}, frame=$i: $contrast", contrast >= 4.5f)
            }
        }
    }

    @Test fun textRemainsReadableOnSemanticSurfacesInBothThemes() {
        listOf(LightColors, DarkColors).forEach { c ->
            val pairs = buildList {
                listOf(c.background, c.surface, c.surfaceSubtle, c.surfaceInfo).forEach { bg ->
                    add(Triple("body", c.ink, bg))
                    add(Triple("secondary", c.muted, bg))
                    add(Triple("link", c.accent, bg))
                }
                add(Triple("success banner", c.ok, c.okBg))
                add(Triple("warning", c.warn, c.warnBg))
                add(Triple("primary button", c.onPrimary, c.primary))
                add(Triple("pressed button", c.onPrimary, c.primaryPressed))
                add(Triple("success badge", c.onOk, c.ok))
                add(Triple("disabled button", c.onDisabled, c.disabled))
                add(Triple("bank label", c.bankAccent, c.background))
                add(Triple("warm step number", c.onWarmAccent, c.warmAccent))
                add(Triple("camera step", c.warmAccent, Palette.CameraBg))
            }
            pairs.forEach { (name, fg, bg) ->
                val contrast = (maxOf(fg.luminance(), bg.luminance()) + 0.05f) /
                    (minOf(fg.luminance(), bg.luminance()) + 0.05f)
                assertTrue("$name (dark=${c.isDark}): $contrast", contrast >= 4.5f)
            }
        }
    }

    @Test fun vietnameseTextHasRoomForDiacritics() {
        // Style A deliberately uses tighter headings; paragraphs keep their full leading.
        assertTrue(VcType.titleLarge.lineHeight.value >= VcType.titleLarge.fontSize.value * 1.18f)
        listOf(VcType.titleMedium, VcType.section, VcType.body,
            VcType.bodyStrong, VcType.bodySmall, VcType.caption, VcType.footnote,
            VcType.button, VcType.label, VcType.labelSmall, VcType.labelXs).forEach {
            assertTrue("Line height clips accented text: $it", it.lineHeight.value >= it.fontSize.value * 1.4f)
        }
        assertTrue(VcType.body.lineHeight.value >= VcType.body.fontSize.value * 1.5f)
    }
}
