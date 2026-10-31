package vn.vericlue.app

import android.app.Activity
import android.app.Instrumentation
import android.os.Bundle
import android.os.Handler
import android.os.Looper
import android.speech.tts.TextToSpeech
import java.util.concurrent.CountDownLatch
import java.util.concurrent.TimeUnit
import vn.vericlue.app.capture.HeadCue
import vn.vericlue.app.capture.HeadSpeech

/** Opt-in native smoke runner: never opens camera, submits data or plays audible sound. */
class HeadSpeechProbe : Instrumentation() {
    override fun onCreate(arguments: Bundle?) { super.onCreate(arguments); start() }
    override fun onStart() {
        val ready = CountDownLatch(1)
        val done = CountDownLatch(1)
        var available = false
        var completed = false
        var speech: HeadSpeech? = null
        val output = Bundle()
        try {
            runOnMainSync {
                speech = HeadSpeech(targetContext, volume = 0f,
                    onReady = { available = it; ready.countDown() },
                    onFinished = { completed = it; done.countDown() })
            }
            output.putBoolean("initialized", ready.await(25, TimeUnit.SECONDS))
            output.putBoolean("vietnamese_available", available)
            output.putBoolean("offline_vietnamese", available && speech?.networkRequired == false)
            output.putBoolean("network_required", available && speech?.networkRequired == true)
            if (available) {
                runOnMainSync { speech?.say(HeadCue.Hold) }
                output.putBoolean("silent_utterance_callback", done.await(8, TimeUnit.SECONDS) && completed)
            } else output.putString("mode", "distinct_soft_beep_fallback")
            runOnMainSync { speech?.pause(); speech?.close() }
            if (!available) {
                val inventory = mutableListOf<String>()
                val engines = mutableSetOf<String?>()
                engines.add(null)
                var index = 0
                while (index < engines.size && index < 4) {
                    val pkg = engines.toList()[index++]
                    val loaded = CountDownLatch(1)
                    var probe: TextToSpeech? = null
                    runOnMainSync {
                        probe = TextToSpeech(targetContext, { status -> Handler(Looper.getMainLooper()).post {
                            runCatching {
                                val tts = probe ?: return@runCatching
                                engines.addAll(tts.engines.map { it.name })
                                val vi = tts.voices.orEmpty().filter { it.locale.language in setOf("vi", "vie") }
                                inventory.add("${pkg ?: "default"}:status=$status,vi=${vi.size},offline=${vi.count { !it.isNetworkConnectionRequired }}")
                            }
                            loaded.countDown()
                        } }, pkg)
                    }
                    loaded.await(10, TimeUnit.SECONDS)
                    runOnMainSync { probe?.shutdown() }
                }
                output.putString("voice_inventory", inventory.joinToString(";"))
            }
            output.putBoolean("closed", true)
            finish(Activity.RESULT_OK, output)
        } catch (error: Exception) {
            runOnMainSync { speech?.close() }
            output.putString("failure", error.javaClass.simpleName)
            finish(Activity.RESULT_CANCELED, output)
        }
    }
}
