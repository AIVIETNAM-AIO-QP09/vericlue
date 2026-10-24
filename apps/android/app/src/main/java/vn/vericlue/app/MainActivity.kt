package vn.vericlue.app

import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.activity.enableEdgeToEdge
import vn.vericlue.app.ui.VeriClueApp
import vn.vericlue.app.ui.theme.VcTheme

class MainActivity : ComponentActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        enableEdgeToEdge()
        setContent { VcTheme { VeriClueApp() } }
    }
}
