package vn.vericlue.app.ui.components

import androidx.compose.foundation.layout.*
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.outlined.*
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import vn.vericlue.app.ui.theme.Vc
import vn.vericlue.app.ui.theme.VcType

/** Decorative vocabulary; never carries identity, capture state or server decisions. */
enum class IllustrationScene(val wireName: String) {
    Card("card"), Face("face"), Eyes("eyes"), Turn("turn"), Voice("voice"), Privacy("privacy"), Success("success"),
}

@Composable
internal fun SceneFallback(scene: IllustrationScene, modifier: Modifier = Modifier) {
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
