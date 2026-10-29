package vn.vericlue.app.ui.theme

import android.database.ContentObserver
import android.os.Handler
import android.os.Looper
import android.provider.Settings
import androidx.compose.animation.core.tween
import androidx.compose.runtime.Composable
import androidx.compose.runtime.DisposableEffect
import androidx.compose.runtime.Immutable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.runtime.staticCompositionLocalOf
import androidx.compose.ui.platform.LocalContext
import vn.vericlue.app.flow.Routes

/** Decorative motion only; the server's capture schedule never uses these durations. */
@Immutable
data class VcMotion(val enabled: Boolean) {
    fun duration(millis: Int): Int = if (enabled) millis else 0
    fun stagger(index: Int): Int = duration(index * 35)
    fun <T> tween(millis: Int = 180, delayMillis: Int = 0) =
        tween<T>(durationMillis = duration(millis), delayMillis = duration(delayMillis))

    fun screenTransition(from: String?, to: String?): Boolean =
        enabled && from !in cameraRoutes && to !in cameraRoutes

    private companion object {
        val cameraRoutes = setOf(Routes.IdFront, Routes.IdFrontGlare, Routes.IdBack,
            Routes.Framing, Routes.HoldStill, Routes.TurnHead, Routes.Voice, Routes.VoiceAgain)
    }
}

internal val LocalVcMotion = staticCompositionLocalOf<VcMotion?> { null }

/** Observe changes while the app is open as well as on its first composition. */
@Composable
internal fun rememberSystemMotion(): VcMotion {
    val resolver = LocalContext.current.contentResolver
    fun enabled() = Settings.Global.getFloat(resolver, Settings.Global.ANIMATOR_DURATION_SCALE, 1f) > 0f
    var motion by remember(resolver) { mutableStateOf(VcMotion(enabled())) }
    DisposableEffect(resolver) {
        val observer = object : ContentObserver(Handler(Looper.getMainLooper())) {
            override fun onChange(selfChange: Boolean) { motion = VcMotion(enabled()) }
        }
        resolver.registerContentObserver(Settings.Global.getUriFor(Settings.Global.ANIMATOR_DURATION_SCALE), false, observer)
        motion = VcMotion(enabled())
        onDispose { resolver.unregisterContentObserver(observer) }
    }
    return motion
}
