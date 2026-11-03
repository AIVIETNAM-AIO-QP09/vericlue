package vn.vericlue.app.ui.components

import androidx.compose.foundation.Canvas
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.outlined.*
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.geometry.CornerRadius
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.geometry.Size
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.StrokeCap
import androidx.compose.ui.graphics.drawscope.Stroke
import androidx.compose.ui.graphics.drawscope.rotate
import androidx.compose.ui.semantics.clearAndSetSemantics
import androidx.compose.ui.unit.dp
import vn.vericlue.app.ui.theme.Palette
import vn.vericlue.app.ui.theme.Vc
import vn.vericlue.app.ui.theme.VcStage
import vn.vericlue.app.ui.theme.VcType

/** Decorative vocabulary; never carries identity, capture state or server decisions. */
enum class IllustrationScene(val wireName: String) {
    Card("card"), Face("face"), Eyes("eyes"), Turn("turn"), Voice("voice"), Privacy("privacy"), Success("success"),
    Backdrop("backdrop"),
}

@Composable
internal fun SceneFallback(scene: IllustrationScene, modifier: Modifier = Modifier) {
    if (scene == IllustrationScene.Backdrop) { BackdropFallback(modifier); return }
    Box(modifier, contentAlignment = Alignment.Center) {
        if (scene == IllustrationScene.Card) IdentityIllustration(Modifier.fillMaxSize())
        else {
            val icon = when (scene) {
                IllustrationScene.Face -> Icons.Outlined.Face
                IllustrationScene.Eyes -> Icons.Outlined.Visibility
                IllustrationScene.Turn -> Icons.Outlined.SwapHoriz
                IllustrationScene.Voice -> Icons.Outlined.Mic
                IllustrationScene.Privacy -> Icons.Outlined.Shield
                IllustrationScene.Success -> Icons.Outlined.CheckCircle
                else -> Icons.Outlined.Badge
            }
            Surface(shape = RoundedCornerShape(36.dp), color = Vc.colors.surfaceSubtle) {
                Icon(icon, contentDescription = null, tint = if (scene == IllustrationScene.Success) Vc.colors.ok else Vc.colors.accent,
                    modifier = Modifier.padding(24.dp).size(64.dp))
            }
        }
    }
}

/**
 * Native twin of the 3D login stage, in the same scene units (screen width = 3.65, y up from the
 * centre). Shown in snapshots, with reduced motion, and whenever WebGL is unavailable.
 */
@Composable
private fun BackdropFallback(modifier: Modifier) {
    Canvas(modifier.clearAndSetSemantics {}) {
        val u = size.width / 3.65f
        fun at(x: Float, y: Float) = Offset(size.width / 2 + x * u, size.height / 2 - y * u)
        fun pill(x: Float, y: Float, w: Float, h: Float, turn: Float, top: Color, bottom: Color) {
            val c = at(x, y)
            rotate(-turn * 57.3f, c) {
                val origin = Offset(c.x - w * u / 2, c.y - h * u / 2)
                drawRoundRect(Brush.verticalGradient(listOf(top, bottom), origin.y, origin.y + h * u), origin,
                    Size(w * u, h * u), CornerRadius(h * u / 2))
                drawRoundRect(Color.White.copy(alpha = .22f), Offset(origin.x + h * u * .3f, origin.y + h * u * .14f),
                    Size(w * u - h * u * .6f, h * u * .16f), CornerRadius(h * u * .08f))
            }
        }
        pill(1.45f, 3.55f, 3.6f, 1.05f, -.42f, VcStage.slab, VcStage.slabDeep)
        pill(-1.75f, 1.75f, 3.0f, .95f, .36f, VcStage.slabDeep, VcStage.mid)
        pill(1.75f, -2.6f, 2.4f, .8f, .5f, VcStage.slab, VcStage.slabDeep)
        val ring = at(.7f, 2.5f)
        rotate(10f, ring) {
            drawRoundRect(Palette.Background, Offset(ring.x - .48f * u, ring.y - .3f * u), Size(.96f * u, .6f * u), CornerRadius(.08f * u))
            drawRoundRect(Palette.CardChip, Offset(ring.x - .37f * u, ring.y - .2f * u), Size(.18f * u, .13f * u), CornerRadius(.025f * u))
        }
        VcStage.ring.forEachIndexed { i, color ->
            drawArc(color, i * 90f + 6f, 78f, useCenter = false, topLeft = Offset(ring.x - .72f * u, ring.y - .72f * u),
                size = Size(1.44f * u, 1.44f * u), style = Stroke(.08f * u, cap = StrokeCap.Round))
        }
    }
}
