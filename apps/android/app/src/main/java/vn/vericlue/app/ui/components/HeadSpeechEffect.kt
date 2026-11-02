package vn.vericlue.app.ui.components

import androidx.compose.runtime.Composable
import androidx.compose.runtime.DisposableEffect
import androidx.compose.runtime.remember
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.platform.LocalInspectionMode
import androidx.compose.ui.platform.LocalLifecycleOwner
import androidx.compose.ui.platform.LocalView
import androidx.lifecycle.Lifecycle
import androidx.lifecycle.LifecycleEventObserver
import vn.vericlue.app.capture.HeadSpeech

@Composable
fun rememberHeadSpeech(): HeadSpeech? {
    val context = LocalContext.current
    val enabled = LocalCameraFeed.current != null && !LocalInspectionMode.current && !LocalView.current.isInEditMode
    val owner = LocalLifecycleOwner.current
    val speech = remember(enabled) { if (enabled) HeadSpeech(context.applicationContext) else null }
    DisposableEffect(speech, owner) {
        val observer = LifecycleEventObserver { _, event ->
            if (event == Lifecycle.Event.ON_STOP) speech?.pause()
            if (event == Lifecycle.Event.ON_START) speech?.resume()
        }
        owner.lifecycle.addObserver(observer)
        onDispose { owner.lifecycle.removeObserver(observer); speech?.close() }
    }
    return speech
}
