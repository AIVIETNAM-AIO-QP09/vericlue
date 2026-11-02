package vn.vericlue.app

import java.io.File
import java.security.MessageDigest
import kotlin.math.PI
import kotlin.math.roundToInt
import kotlin.math.sin
import kotlinx.serialization.json.Json
import kotlinx.serialization.json.JsonArray
import kotlinx.serialization.json.buildJsonObject
import kotlinx.serialization.json.put
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Assume.assumeTrue
import org.junit.Test
import vn.vericlue.app.capture.Wav
import vn.vericlue.app.capture.av.Pcm16MonoNormalizer

/** Opt-in synthetic export for independent DSP review; the default test suite writes nothing. */
class PcmNormalizerExportTest {
    private data class Signal(val name: String, val rate: Int, val channels: Int, val kind: String)

    @Test fun exportSyntheticWavsOnlyWhenAnExternalDirectoryIsExplicitlySet() {
        val requested = System.getenv("VERICLUE_PCM_EXPORT_DIR")
        assumeTrue("Set VERICLUE_PCM_EXPORT_DIR for private synthetic exports", !requested.isNullOrBlank())
        val requestedFile = File(requested!!)
        assertTrue("Export directory must be absolute", requestedFile.isAbsolute)
        val exportRoot = requestedFile.canonicalFile
        val repository = generateSequence(File(System.getProperty("user.dir")).canonicalFile) { it.parentFile }
            .firstOrNull { File(it, ".git").exists() }
        assertTrue("Export synthetic binaries outside the repository", repository == null || !exportRoot.toPath().startsWith(repository.toPath()))
        assertTrue(exportRoot.isDirectory || exportRoot.mkdirs())
        val directory = File(exportRoot, "jvm-run-${System.nanoTime()}")
        assertTrue("Each export retains a unique directory", directory.mkdir())
        val signals = buildList {
            for (rate in listOf(44_100, 48_000)) {
                for (kind in listOf("dc", "tone1000", "alias12000", "chirp200to14000", "impulse")) {
                    add(Signal("${rate}_stereo_$kind", rate, 2, kind))
                }
            }
            add(Signal("16000_mono_identity", 16_000, 1, "tone1000"))
        }
        val rows = signals.map { signal ->
            val source = synthetic(signal)
            val normalized = Pcm16MonoNormalizer.normalize(source, signal.rate, signal.channels)
            val inputFile = File(directory, "${signal.name}.input.wav")
            val outputFile = File(directory, "${signal.name}.normalized.wav")
            inputFile.writeBytes(Wav.encode(source, signal.rate, signal.channels))
            outputFile.writeBytes(Wav.encode(normalized.pcm, 16_000, 1))
            assertEquals(16_000, normalized.frames) // Every synthetic input contains exactly one second.
            buildJsonObject {
                put("name", signal.name)
                put("signal", signal.kind)
                put("sourceRate", signal.rate)
                put("sourceChannels", signal.channels)
                put("sourceFrames", signal.rate)
                put("normalizedRate", 16_000)
                put("normalizedChannels", 1)
                put("normalizedFrames", normalized.frames)
                put("inputWav", inputFile.absolutePath)
                put("normalizedWav", outputFile.absolutePath)
                put("inputSha256", sha256(inputFile.readBytes()))
                put("normalizedSha256", sha256(outputFile.readBytes()))
                if (signal.kind == "impulse") {
                    put("sourceImpulseFrame", signal.rate / 4)
                    put("expectedNormalizedPeakFrame", 4_000)
                }
                if (signal.kind == "chirp200to14000") { put("startHz", 200); put("endHz", 14_000) }
            }
        }
        val manifest = buildJsonObject {
            put("syntheticOnly", true)
            put("normalizationPolicy", Pcm16MonoNormalizer.POLICY)
            put("pcmEncoding", "signed-16-bit-little-endian")
            put("generation", "One second; stereo tone amplitudes 12000 / 8000, DC 12000 / -4000, impulse 24000 / 8000 at 250 ms, linear chirp 200 to 14000 Hz")
            put("fixtures", JsonArray(rows))
        }
        val manifestFile = File(directory, "jvm-normalizer.json")
        manifestFile.writeText(Json { prettyPrint = true }.encodeToString(kotlinx.serialization.json.JsonObject.serializer(), manifest))
        println("PCM_NORMALIZER_EXPORT_MANIFEST=${manifestFile.absolutePath}")
    }

    private fun synthetic(signal: Signal): ByteArray = ByteArray(signal.rate * signal.channels * 2).also { bytes ->
        for (frame in 0 until signal.rate) for (channel in 0 until signal.channels) {
            val amplitude = if (channel == 0) 12_000 else 8_000
            val time = frame.toDouble() / signal.rate
            val value = when (signal.kind) {
                "dc" -> if (channel == 0) 12_000 else -4_000
                "impulse" -> if (frame == signal.rate / 4) { if (channel == 0) 24_000 else 8_000 } else 0
                "chirp200to14000" -> (amplitude * sin(2 * PI * (200 * time + 0.5 * 13_800 * time * time))).roundToInt()
                else -> {
                    val frequency = if (signal.kind == "alias12000") 12_000 else 1_000
                    (amplitude * sin(2 * PI * frequency * time)).roundToInt()
                }
            }
            val index = (frame * signal.channels + channel) * 2
            bytes[index] = value.toByte(); bytes[index + 1] = (value shr 8).toByte()
        }
    }

    private fun sha256(bytes: ByteArray): String = MessageDigest.getInstance("SHA-256").digest(bytes).joinToString("") { "%02x".format(it.toInt() and 255) }
}
