package vn.vericlue.app.ui.components

import androidx.compose.foundation.Canvas
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.size
import androidx.compose.runtime.Composable
import androidx.compose.runtime.DisposableEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.drawscope.Stroke
import androidx.compose.ui.graphics.toArgb
import androidx.compose.ui.semantics.clearAndSetSemantics
import androidx.compose.ui.unit.dp
import androidx.lifecycle.Lifecycle
import androidx.lifecycle.LifecycleEventObserver
import androidx.lifecycle.compose.LocalLifecycleOwner
import com.airbnb.lottie.AsyncUpdates
import com.airbnb.lottie.LottieComposition
import com.airbnb.lottie.LottieProperty
import com.airbnb.lottie.compose.LottieAnimation
import com.airbnb.lottie.compose.LottieCompositionSpec
import com.airbnb.lottie.compose.animateLottieCompositionAsState
import com.airbnb.lottie.compose.rememberLottieComposition
import com.airbnb.lottie.compose.rememberLottieDynamicProperties
import com.airbnb.lottie.compose.rememberLottieDynamicProperty
import vn.vericlue.app.R
import vn.vericlue.app.ui.theme.Vc

/** A single offline flourish. It never determines verification or delays the next action. */
@Composable
fun SuccessBadge() {
    val composition by rememberLottieComposition(LottieCompositionSpec.RawRes(R.raw.vericlue_success))
    val lifecycle = LocalLifecycleOwner.current.lifecycle
    var resumed by remember(lifecycle) { mutableStateOf(lifecycle.currentState.isAtLeast(Lifecycle.State.RESUMED)) }
    DisposableEffect(lifecycle) {
        val observer = LifecycleEventObserver { _, _ ->
            resumed = lifecycle.currentState.isAtLeast(Lifecycle.State.RESUMED)
        }
        lifecycle.addObserver(observer)
        onDispose { lifecycle.removeObserver(observer) }
    }
    val motion = Vc.motion.enabled
    val progress by animateLottieCompositionAsState(
        composition, isPlaying = motion && resumed, restartOnPlay = false, iterations = 1,
    )
    SuccessArtwork(composition, progress = { if (motion) progress else 1f })
}

/** Shared renderer also lets snapshots exercise actual Lottie frames, not an async placeholder. */
@Composable
internal fun SuccessArtwork(composition: LottieComposition?, progress: () -> Float) {
    val c = Vc.colors
    val dynamic = rememberLottieDynamicProperties(
        rememberLottieDynamicProperty(LottieProperty.STROKE_COLOR, c.ok.toArgb(), "**"),
    )
    // The adjacent result title announces success. This artwork adds no duplicate semantics.
    Box(Modifier.size(152.dp).clearAndSetSemantics {}, contentAlignment = Alignment.Center) {
        if (composition == null) {
            Canvas(Modifier.size(152.dp)) {
                drawCircle(c.ok.copy(alpha = 0.4f), radius = size.minDimension * 0.4375f,
                    style = Stroke(2.dp.toPx()))
            }
        } else {
            LottieAnimation(
                composition, progress = progress, modifier = Modifier.size(152.dp),
                dynamicProperties = dynamic, asyncUpdates = AsyncUpdates.DISABLED,
            )
        }
        SuccessMark()
    }
}
