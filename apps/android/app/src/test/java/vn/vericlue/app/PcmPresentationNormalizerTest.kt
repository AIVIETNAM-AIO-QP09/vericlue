package vn.vericlue.app

import java.util.concurrent.CancellationException
import kotlin.math.PI
import kotlin.math.abs
import kotlin.math.roundToInt
import kotlin.math.sin
import kotlin.math.sqrt
import org.junit.Assert.assertEquals
import org.junit.Assert.assertThrows
import org.junit.Assert.assertTrue
import org.junit.Test
import vn.vericlue.app.capture.av.MuxedVoiceAudioException
import vn.vericlue.app.capture.av.Pcm16MonoNormalizer
import vn.vericlue.app.capture.av.PcmClockAnchor
import vn.vericlue.app.capture.av.PcmPresentationClock

class PcmPresentationNormalizerTest {
    @Test fun quantizedUniformClocksPreserveClocklessBytesAtCommonRates() {
        for (rate in listOf(16_000, 44_100, 48_000)) {
            val frames = rate / 5 + 1
            val anchors = (0L until frames step 1_024).map { PcmClockAnchor(it, 9_000_000_000L + (it * 1_000_000 + rate / 2) / rate) }
            val clock = PcmPresentationClock(rate, frames.toLong(), anchors)
            assertTrue(clock.uniformNominal)
            val pcm = pcm(frames, 2) { frame, channel -> ((8_000 + channel * 4_000) * sin(2 * PI * 1_000 * frame / rate)).roundToInt() }
            val old = Pcm16MonoNormalizer.normalize(pcm, rate, 2)
            val mapped = Pcm16MonoNormalizer.normalize(pcm, rate, 2, clock)
            assertTrue("rate $rate", old.pcm.contentEquals(mapped.pcm))
        }
    }

    @Test fun actualClockDurationWinsWhenSubMicrosecondQuantizationChangesRounding() {
        val clock = PcmPresentationClock(44_100, 277, listOf(PcmClockAnchor(0, 0), PcmClockAnchor(276, 6_259)))
        assertTrue(clock.uniformNominal)
        assertEquals(101, clock.outputFrames)
        assertEquals(101, Pcm16MonoNormalizer.normalize(pcm(277) { _, _ -> 4_000 }, 44_100, 1, clock).frames)
    }

    @Test fun nonuniformSixteenKilohertzCannotUseTheIdentityShortcutOrShiftTheFirstAxis() {
        val clock = smallClock()
        val source = pcm(4_000) { frame, _ -> if (frame == 0) 24_000 else if (frame == 2_000) 16_000 else 0 }
        val output = samples(Pcm16MonoNormalizer.normalize(source, 16_000, 1, clock).pcm)
        assertEquals(4_024, output.size)
        assertEquals(0, (0 until 64).maxBy { abs(output[it]) })
        assertTrue(abs((2_000 until 2_050).maxBy { abs(output[it]) } - 2_024) <= 1)
    }

    @Test fun collinearPacketSplitsDoNotChangeTheNormalizedSignal() {
        val coarse = smallClock()
        val split = PcmPresentationClock(16_000, 4_000, listOf(
            PcmClockAnchor(0, 0), PcmClockAnchor(1_000, 62_500), PcmClockAnchor(1_500, 94_500),
            PcmClockAnchor(2_000, 126_500), PcmClockAnchor(3_000, 189_000),
        ))
        val source = pcm(4_000) { frame, _ -> (12_000 * sin(frame * 0.13)).roundToInt() }
        val first = Pcm16MonoNormalizer.normalize(source, 16_000, 1, coarse)
        val second = Pcm16MonoNormalizer.normalize(source, 16_000, 1, split)
        assertEquals(4_024, first.frames)
        assertTrue(first.pcm.contentEquals(second.pcm))
    }

    @Test fun knownPresentationToneAndImpulseFollowThePtsStepWithoutAFilterDelay() {
        val clock = steppedClock()
        val tone = pcm(96_000) { frame, _ -> (12_000 * sin(2 * PI * 1_000 * steppedTime(frame))).roundToInt() }
        val output = samples(Pcm16MonoNormalizer.normalize(tone, 48_000, 1, clock).pcm)
        assertEquals(32_023, output.size)
        for ((start, count) in listOf(1_600 to 1_600, 16_080 to 160, 19_200 to 1_600)) {
            val error = sqrt((start until start + count).sumOf { index ->
                val difference = output[index] - 12_000 * sin(2 * PI * 1_000 * index / 16_000)
                difference * difference
            } / count)
            assertTrue("known-time tone error $error", error < 100)
        }
        val impulses = pcm(96_000) { frame, _ -> if (frame in listOf(24_000, 72_000)) 24_000 else 0 }
        val impulseOut = samples(Pcm16MonoNormalizer.normalize(impulses, 48_000, 1, clock).pcm)
        assertTrue(abs((7_950..8_050).maxBy { abs(impulseOut[it]) } - 8_000) <= 1)
        assertTrue(abs((23_970..24_070).maxBy { abs(impulseOut[it]) } - 24_023) <= 1)
    }

    @Test fun positiveAndNegativeDriftPreserveKnownToneTimingAndDuration() {
        for (anchorUs in listOf(480_000L, 520_000L)) {
            val clock = PcmPresentationClock(48_000, 48_000, listOf(PcmClockAnchor(0, 0), PcmClockAnchor(24_000, anchorUs)))
            val source = pcm(48_000) { frame, _ ->
                val seconds = if (frame < 24_000) frame * anchorUs / 24_000_000_000.0 else anchorUs / 1_000_000.0 + (frame - 24_000) / 48_000.0
                (12_000 * sin(2 * PI * 1_000 * seconds)).roundToInt()
            }
            val output = samples(Pcm16MonoNormalizer.normalize(source, 48_000, 1, clock).pcm)
            assertEquals(if (anchorUs == 480_000L) 15_680 else 16_320, output.size)
            for (start in listOf(1_600, 11_200)) {
                val error = sqrt((start until start + 1_600).sumOf { index ->
                    val difference = output[index] - 12_000 * sin(2 * PI * 1_000 * index / 16_000)
                    difference * difference
                } / 1_600)
                assertTrue("drift tone error $error", error < 100)
            }
        }
    }

    @Test fun mappedDownmixPreservesDcAndSuppressesAnOutOfBandTone() {
        val clock = PcmPresentationClock(48_000, 48_000, listOf(PcmClockAnchor(0, 0), PcmClockAnchor(24_000, 480_000)))
        val dc = pcm(48_000, 2) { _, channel -> if (channel == 0) 12_000 else -4_000 }
        assertTrue(samples(Pcm16MonoNormalizer.normalize(dc, 48_000, 2, clock).pcm).all { abs(it - 4_000) <= 1 })
        val alias = pcm(48_000, 2) { frame, channel ->
            val seconds = if (frame < 24_000) frame / 50_000.0 else 0.48 + (frame - 24_000) / 48_000.0
            ((if (channel == 0) 12_000 else 8_000) * sin(2 * PI * 12_000 * seconds)).roundToInt()
        }
        val output = samples(Pcm16MonoNormalizer.normalize(alias, 48_000, 2, clock).pcm)
        for (start in listOf(1_600, 11_200)) assertTrue(sqrt((start until start + 1_600).sumOf { output[it].toDouble() * output[it] } / 1_600) < 12)
    }

    @Test fun mismatchedClocksAndCancellationCannotReturnPcm() {
        val clock = smallClock()
        assertThrows(MuxedVoiceAudioException::class.java) { Pcm16MonoNormalizer.normalize(pcm(4_001) { _, _ -> 0 }, 16_000, 1, clock) }
        assertThrows(MuxedVoiceAudioException::class.java) { Pcm16MonoNormalizer.normalize(pcm(4_000) { _, _ -> 0 }, 48_000, 1, clock) }
        var checks = 0
        assertThrows(CancellationException::class.java) {
            Pcm16MonoNormalizer.normalize(pcm(4_000) { _, _ -> 0 }, 16_000, 1, clock) { if (++checks >= 20) throw CancellationException("test") }
        }
    }

    private fun smallClock() = PcmPresentationClock(16_000, 4_000, listOf(PcmClockAnchor(0, 0), PcmClockAnchor(1_000, 62_500), PcmClockAnchor(2_000, 126_500)))
    private fun steppedClock() = PcmPresentationClock(48_000, 96_000, listOf(PcmClockAnchor(0, 0), PcmClockAnchor(48_000, 1_000_000), PcmClockAnchor(49_024, 1_022_750), PcmClockAnchor(94_976, 1_980_083)))
    private fun steppedTime(frame: Int): Double = when {
        frame < 48_000 -> frame / 48_000.0
        frame < 49_024 -> 1.0 + (frame - 48_000) * 0.02275 / 1_024
        else -> 1.02275 + (frame - 49_024) / 48_000.0
    }
    private fun pcm(frames: Int, channels: Int = 1, sample: (Int, Int) -> Int) = ByteArray(frames * channels * 2).also { bytes ->
        for (frame in 0 until frames) for (channel in 0 until channels) {
            val value = sample(frame, channel)
            val index = (frame * channels + channel) * 2
            bytes[index] = value.toByte(); bytes[index + 1] = (value shr 8).toByte()
        }
    }
    private fun samples(pcm: ByteArray) = (pcm.indices step 2).map { ((pcm[it].toInt() and 255) or (pcm[it + 1].toInt() shl 8)).toShort().toInt() }
}
