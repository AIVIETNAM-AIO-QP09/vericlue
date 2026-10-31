package vn.vericlue.app.ui.screens

import androidx.compose.foundation.background
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.outlined.ArrowBack
import androidx.compose.material.icons.automirrored.outlined.ArrowForward
import androidx.compose.material3.Icon
import androidx.compose.material3.Text
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.draw.clipToBounds
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import kotlinx.coroutines.delay
import vn.vericlue.app.capture.*
import vn.vericlue.app.flow.TurnDir
import vn.vericlue.app.ui.components.*
import vn.vericlue.app.ui.theme.Palette
import vn.vericlue.app.ui.theme.VcType

@Composable
fun HeadPracticeScreen(face: FaceSignal?, onExit: () -> Unit, onContinue: () -> Unit) {
    val practice = remember { HeadTurnPractice() }
    val policy = remember { HeadCuePolicy() }
    val speech = rememberHeadSpeech()
    var epoch by remember { mutableIntStateOf(0) }
    var step by remember { mutableIntStateOf(0) }
    var clock by remember { mutableStateOf(android.os.SystemClock.elapsedRealtime()) }
    LaunchedEffect(Unit) { while (true) { clock = android.os.SystemClock.elapsedRealtime(); delay(100) } }
    val now = maxOf(clock, android.os.SystemClock.elapsedRealtime())
    val fresh = HeadTurnGuide.freshFace(face, now, 0)
    LaunchedEffect(face, epoch) {
        if (practice.update(face, android.os.SystemClock.elapsedRealtime())) step = practice.step
    }
    val cue = if (practice.ready) HeadCue.Ready else headCue(practice.direction, fresh, false)
    LaunchedEffect(cue, clock, step, epoch) {
        policy.dispatch(epoch * 10 + step, cue, now, stop = { speech?.stop() }, say = { speech?.say(it) })
    }
    HeadPracticeContent(step, cue, HeadTurnGuide.evaluatePose(practice.direction, fresh),
        onExit = onExit,
        onContinue = { speech?.stop(); onContinue() },
        onRestart = { speech?.stop(); practice.reset(); step = 0; epoch++ },
    )
}

/** No camera work, recording or API calls: presentation can be snapshotted independently. */
@Composable
fun HeadPracticeContent(step: Int, cue: HeadCue, pose: TurnPoseState,
    onExit: () -> Unit, onContinue: () -> Unit, onRestart: () -> Unit) {
    val ready = step >= 5
    val dir = when (step) { 1 -> TurnDir.Left; 3 -> TurnDir.Right; else -> null }
    CameraScaffold(onExit) {
        Column(Modifier.fillMaxSize()) {
            Text(if (ready) "Tập xong" else "Tập quay đầu", style = VcType.titleMedium, color = Color.White,
                textAlign = TextAlign.Center, modifier = Modifier.fillMaxWidth().padding(top = 16.dp))
            Text("Tập thử · chưa ghi hình", style = VcType.body, color = Color.White,
                textAlign = TextAlign.Center, modifier = Modifier.fillMaxWidth().padding(12.dp))
            Box(Modifier.weight(1f).fillMaxWidth().clipToBounds()) {
                FullCamera(fitHeight = true, ringWidth = 1.5.dp,
                    ringColor = if (pose == TurnPoseState.Hold || ready) Palette.OkOnDark else Color.White.copy(alpha = .65f))
                if (dir != null && pose == TurnPoseState.TurnMore) Icon(
                    if (dir == TurnDir.Left) Icons.AutoMirrored.Outlined.ArrowBack else Icons.AutoMirrored.Outlined.ArrowForward,
                    contentDescription = null, tint = Color.White,
                    modifier = Modifier.align(if (dir == TurnDir.Left) Alignment.CenterStart else Alignment.CenterEnd)
                        .padding(24.dp).size(40.dp),
                )
            }
            Column(Modifier.fillMaxWidth().heightIn(max = 310.dp).verticalScroll(rememberScrollState()).padding(20.dp),
                verticalArrangement = Arrangement.spacedBy(12.dp), horizontalAlignment = Alignment.CenterHorizontally) {
                if (!ready) Text(cue.text, style = VcType.titleMedium, color = Color.White, textAlign = TextAlign.Center)
                Text(if (ready) "Tiếp theo mới là lượt xác minh. Giữ điện thoại ngang tầm mắt."
                    else "Quay nhẹ theo lời nhắc. Hai bíp ngắn: dừng và giữ. Một bíp dài: nhìn thẳng.",
                    style = VcType.body, color = Color.White, textAlign = TextAlign.Center)
                if (ready) {
                    PrimaryButton("Bắt đầu xác minh", onContinue)
                    LinkButton("Tập lại", onRestart)
                } else LinkButton("Bỏ qua phần tập", onContinue)
            }
        }
    }
}
