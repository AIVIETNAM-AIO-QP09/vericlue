package vn.vericlue.app.ui

import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableIntStateOf
import androidx.compose.runtime.setValue
import kotlinx.coroutines.delay

/** UI resend pacing only. Server limits remain authoritative. */
internal class OtpCooldown {
    var seconds by mutableIntStateOf(45)
        private set
    var generation by mutableIntStateOf(0)
        private set

    suspend fun run() {
        while (seconds > 0) {
            delay(1000)
            seconds--
        }
    }

    /** Synchronous guard also prevents two taps before Compose redraws. */
    fun restart(): Boolean {
        if (seconds > 0) return false
        seconds = 45
        generation++
        return true
    }
}
