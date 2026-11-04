package vn.vericlue.app.ui.components

import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.ColumnScope
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.Icon
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.vector.ImageVector
import androidx.compose.ui.unit.dp
import vn.vericlue.app.ui.theme.Vc
import vn.vericlue.app.ui.theme.VcType

/** Shared reading surface for consent, preparation and identity details. */
@Composable
fun ContentCard(modifier: Modifier = Modifier, content: @Composable ColumnScope.() -> Unit) {
    Column(modifier.fillMaxWidth().glass().padding(20.dp), verticalArrangement = Arrangement.spacedBy(20.dp), content = content)
}

/** The text carries the meaning; the icon is decorative for screen readers. */
@Composable
fun FeatureRow(icon: ImageVector, title: String, detail: String? = null) {
    val c = Vc.colors
    Row(
        Modifier.fillMaxWidth(),
        horizontalArrangement = Arrangement.spacedBy(14.dp),
        verticalAlignment = if (detail == null) Alignment.CenterVertically else Alignment.Top,
    ) {
        Box(
            Modifier.size(40.dp).background(c.surfaceSubtle, RoundedCornerShape(12.dp)),
            contentAlignment = Alignment.Center,
        ) {
            Icon(icon, contentDescription = null, tint = c.accent, modifier = Modifier.size(20.dp))
        }
        Column(Modifier.weight(1f), verticalArrangement = Arrangement.spacedBy(4.dp)) {
            Text(title, style = VcType.bodyStrong, color = c.ink)
            if (detail != null) Text(detail, style = VcType.bodySmall, color = c.muted)
        }
    }
}
