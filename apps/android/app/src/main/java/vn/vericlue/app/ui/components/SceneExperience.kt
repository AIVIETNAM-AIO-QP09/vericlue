package vn.vericlue.app.ui.components

import androidx.compose.foundation.layout.*
import androidx.compose.foundation.selection.selectable
import androidx.compose.foundation.selection.selectableGroup
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.outlined.*
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.semantics.Role
import androidx.compose.ui.unit.dp
import vn.vericlue.app.ui.theme.Vc
import vn.vericlue.app.ui.theme.VcType

/** Fixed visual vocabulary only. No identity, server verdict or media enters the renderer. */
enum class IllustrationScene(val wireName: String, val label: String, val explanation: String) {
    Card("card", "Thẻ căn cước", "Chuẩn bị thẻ thật, giữ trọn thẻ trong khung và tránh ánh sáng phản chiếu."),
    Face("face", "Khuôn mặt", "Giữ điện thoại ngang tầm mắt, mặt ở giữa khung. Giữ đầu thẳng và nhìn thẳng khi màn hình đổi màu."),
    Eyes("eyes", "Đưa mắt", "Giữ đầu yên, chỉ đưa mắt theo chấm khi ứng dụng hướng dẫn."),
    Turn("turn", "Quay đầu", "Quay chậm theo mũi tên trên màn hình, sau đó nhìn thẳng trở lại."),
    Voice("voice", "Giọng nói", "Chỉ đọc câu xác nhận khi được yêu cầu. Chọn nơi yên tĩnh và đọc rõ từng từ."),
    Privacy("privacy", "Quyền chủ động", "Bạn quyết định có tiếp tục cung cấp thông tin để xác minh hay không."),
    Success("success", "Đã hoàn tất", "Bạn có thể tiếp tục với dịch vụ."),
}

/** Text and controls stay native and usable when WebGL is unavailable or motion is disabled. */
@OptIn(ExperimentalLayoutApi::class)
@Composable
fun SceneExplorer(facePreparation: Boolean = false, initialScene: IllustrationScene? = null) {
    val choices = if (facePreparation) listOf(IllustrationScene.Face, IllustrationScene.Eyes, IllustrationScene.Turn)
        else listOf(IllustrationScene.Card, IllustrationScene.Face, IllustrationScene.Voice)
    var selectedName by rememberSaveable(facePreparation) { mutableStateOf((initialScene ?: choices.first()).name) }
    val selected = choices.firstOrNull { it.name == selectedName } ?: choices.first()
    var paused by rememberSaveable { mutableStateOf(false) }
    var replay by remember { mutableIntStateOf(0) }
    Column(verticalArrangement = Arrangement.spacedBy(12.dp)) {
        FlowRow(Modifier.fillMaxWidth().selectableGroup(), horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            choices.forEach { option ->
                Surface(shape = RoundedCornerShape(16.dp),
                    color = if (selected == option) Vc.colors.primary else Vc.colors.surfaceSubtle) {
                    Box(Modifier.selectable(selected == option, role = Role.Tab, onClick = { selectedName = option.name })
                        .heightIn(min = 48.dp).padding(horizontal = 12.dp, vertical = 12.dp), contentAlignment = Alignment.Center) {
                        Text(when {
                            facePreparation && option == IllustrationScene.Face -> "Giữ thẳng"
                            option == IllustrationScene.Card -> "Thẻ"
                            else -> option.label
                        },
                            style = VcType.labelSmall, color = if (selected == option) Vc.colors.onPrimary else Vc.colors.ink)
                    }
                }
            }
        }
        IdentityScene3D(Modifier.fillMaxWidth().height(144.dp), selected, paused, replay)
        Text(selected.explanation, style = VcType.bodySmall, color = Vc.colors.muted)
        Text(if (facePreparation) "Minh họa thao tác. Khi xác minh, làm theo hướng dẫn thực tế trên màn hình."
            else "Chọn từng mục để xem trước. Đây là minh họa, chưa bắt đầu thu dữ liệu.",
            style = VcType.caption, color = Vc.colors.muted)
        FlowRow(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            TextButton(onClick = { replay++; paused = false }, enabled = Vc.motion.enabled,
                modifier = Modifier.heightIn(min = 48.dp)) { Text("Xem lại") }
            TextButton(onClick = { paused = !paused }, enabled = Vc.motion.enabled,
                modifier = Modifier.heightIn(min = 48.dp)) { Text(if (paused) "Tiếp tục" else "Tạm dừng") }
        }
    }
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
