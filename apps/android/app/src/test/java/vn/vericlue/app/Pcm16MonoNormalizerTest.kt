package vn.vericlue.app

import java.util.concurrent.CancellationException
import kotlin.math.PI
import kotlin.math.abs
import kotlin.math.atan2
import kotlin.math.cos
import kotlin.math.roundToInt
import kotlin.math.sin
import kotlin.math.sqrt
import org.junit.Assert.assertEquals
import org.junit.Assert.assertThrows
import org.junit.Assert.assertTrue
import org.junit.Test
import vn.vericlue.app.capture.av.MuxedVoiceAudioException
import vn.vericlue.app.capture.av.Pcm16MonoNormalizer

class Pcm16MonoNormalizerTest {
    @Test fun stereoDownmixPreservesDcWithoutIntegerOverflow() {
        val source = pcm(4_800, channels = 2) { _, channel -> if (channel == 0) 12_000 else -4_000 }
        val result = Pcm16MonoNormalizer.normalize(source, 48_000, 2)
        assertEquals(1_600, result.frames)
        assertEquals(3_200, result.pcm.size)
        assertTrue(samples(result.pcm).all { abs(it - 4_000) <= 1 })
        val maximum = pcm(1_600, 2) { _, _ -> 32_767 }
        assertTrue(samples(Pcm16MonoNormalizer.normalize(maximum, 16_000, 2).pcm).all { it == 32_767 })
    }

    @Test fun alreadyCanonicalPcmIsByteExact() {
        val source = pcm(5) { index, _ -> listOf(-32_768, -12_345, 0, 12_345, 32_767)[index] }
        val result = Pcm16MonoNormalizer.normalize(source, 16_000, 1)
        assertEquals(5, result.frames)
        assertTrue(source.contentEquals(result.pcm))
    }

    @Test fun passbandToneRetainsAmplitudePitchAndPhaseAtCommonRates() {
        for (rate in listOf(44_100, 48_000, 16_000)) {
            val output = samples(Pcm16MonoNormalizer.normalize(tone(rate, 1_000.0), rate, 1).pcm)
            assertEquals(16_000, output.size)
            val (sine, cosine) = components(output, 1_000.0)
            assertEquals(12_000.0, sqrt(sine * sine + cosine * cosine), 120.0)
            val shiftInOutputSamples = atan2(cosine, sine) * 16_000 / (2 * PI * 1_000)
            assertTrue("phase shift at $rate: $shiftInOutputSamples samples", abs(shiftInOutputSamples) <= 1.0)
            assertTrue(abs(components(output, 500.0).first) < 120)
            assertTrue(abs(components(output, 1_500.0).first) < 120)
        }
    }

    @Test fun twelveKilohertzInputCannotAliasToFourKilohertzAfterDownsampling() {
        val output = samples(Pcm16MonoNormalizer.normalize(tone(48_000, 12_000.0), 48_000, 1).pcm)
        assertEquals(16_000, output.size)
        val steady = output.drop(512).dropLast(512)
        val rms = sqrt(steady.sumOf { it.toDouble() * it } / steady.size)
        // Naive decimation would produce ~8485 PCM RMS at the 4 kHz alias.
        assertTrue("alias RMS: $rms", rms < 12.0)
    }

    @Test fun centeredImpulseDoesNotAcquireAFirDelay() {
        for (rate in listOf(44_100, 48_000)) {
            val source = pcm(rate) { index, _ -> if (index == rate / 10) 20_000 else 0 }
            val output = samples(Pcm16MonoNormalizer.normalize(source, rate, 1).pcm)
            val peak = output.indices.maxBy { abs(output[it]) }
            assertTrue("impulse peak at $rate: $peak", abs(peak - 1_600) <= 1)
        }
    }

    @Test fun frameCountsPreserveDurationWithinOneOutputSample() {
        for ((rate, inputFrames, expected) in listOf(
            Triple(44_100, 4_411, 1_600), Triple(48_000, 4_801, 1_600),
            Triple(16_000, 1_601, 1_601), Triple(8_000, 801, 1_602), Triple(192_000, 19_201, 1_600),
        )) {
            val result = Pcm16MonoNormalizer.normalize(pcm(inputFrames) { _, _ -> 1_000 }, rate, 1)
            assertEquals(expected, result.frames)
            assertEquals(expected * 2, result.pcm.size)
            assertTrue(abs(result.frames / 16_000.0 - inputFrames / rate.toDouble()) <= 1 / 16_000.0)
        }
    }

    @Test fun invalidFormatsAndOversizedInputFailBeforeDsp() {
        for ((rate, channels) in listOf(0 to 1, Int.MAX_VALUE to 1, 48_000 to 0, 48_000 to 3)) {
            assertThrows(MuxedVoiceAudioException::class.java) { Pcm16MonoNormalizer.normalize(byteArrayOf(0, 0), rate, channels) }
        }
        assertThrows(MuxedVoiceAudioException::class.java) { Pcm16MonoNormalizer.normalize(byteArrayOf(0), 48_000, 1) }
        assertThrows(MuxedVoiceAudioException::class.java) { Pcm16MonoNormalizer.normalize(pcm(96_001) { _, _ -> 0 }, 8_000, 1) }
    }

    @Test fun cancellationDuringDspNeverReturnsPartialPcm() {
        var checks = 0
        assertThrows(CancellationException::class.java) {
            Pcm16MonoNormalizer.normalize(tone(48_000, 1_000.0), 48_000, 1) {
                if (++checks >= 3) throw CancellationException("test cancellation")
            }
        }
        assertTrue(checks >= 3)
    }

    private fun tone(rate: Int, frequency: Double) = pcm(rate) { index, _ -> (12_000 * sin(2 * PI * frequency * index / rate)).roundToInt() }

    private fun pcm(frames: Int, channels: Int = 1, sample: (Int, Int) -> Int): ByteArray = ByteArray(frames * channels * 2).also { bytes ->
        for (frame in 0 until frames) for (channel in 0 until channels) {
            val value = sample(frame, channel)
            val offset = (frame * channels + channel) * 2
            bytes[offset] = value.toByte(); bytes[offset + 1] = (value shr 8).toByte()
        }
    }

    private fun samples(pcm: ByteArray): List<Int> = (pcm.indices step 2).map { ((pcm[it].toInt() and 255) or (pcm[it + 1].toInt() shl 8)).toShort().toInt() }

    private fun components(signal: List<Int>, frequency: Double): Pair<Double, Double> {
        var sine = 0.0
        var cosine = 0.0
        for (index in 512 until signal.size - 512) {
            val angle = 2 * PI * frequency * index / 16_000
            sine += signal[index] * sin(angle)
            cosine += signal[index] * cos(angle)
        }
        val count = signal.size - 1_024
        return 2 * sine / count to 2 * cosine / count
    }
}
