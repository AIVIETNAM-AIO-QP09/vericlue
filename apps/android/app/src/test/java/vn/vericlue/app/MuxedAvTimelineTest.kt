package vn.vericlue.app

import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Assert.assertThrows
import org.junit.Test
import vn.vericlue.app.capture.av.PcmTimeline
import vn.vericlue.app.capture.av.MuxedVoiceAudioException
import vn.vericlue.app.capture.av.PcmFormat

class MuxedAvTimelineTest {
    @Test fun firstKeptPcmPtsDefinesOffsetIndependentlyOfTheSignalSamples() {
        val timeline = PcmTimeline(PcmFormat(48_000, 2, 2))
        timeline.append(250_000, byteArrayOf(0, 0, 0, 0, 0, 8, 0, 0))
        timeline.append(250_042, byteArrayOf(0, 0, 0, 0))
        val result = timeline.finish(true, videoPtsUs = 0)
        assertEquals(250_000L, result.offsetUs)
        assertEquals(3L, result.frames)
        assertEquals(12, result.pcm.size)
    }

    @Test fun timestampRoundingDoesNotAccumulateIntoFalseGaps() {
        val timeline = PcmTimeline(PcmFormat(44_100, 1, 2))
        repeat(100) { index ->
            timeline.append(1_000_000L + index * 1_024_000_000L / 44_100, ByteArray(2_048))
        }
        val result = timeline.finish(true, 500_000)
        assertEquals(102_400L, result.frames)
        assertEquals(500_000L, result.offsetUs)
    }

    @Test fun gapOrOverlapIsRejectedInsteadOfConcatenatingOrAddingSilence() {
        for (secondPts in listOf(25_000L, 15_000L)) {
            val timeline = PcmTimeline(PcmFormat(48_000, 1, 2))
            timeline.append(0, ByteArray(1_920)) // exactly 20 ms
            val error = assertThrows(MuxedVoiceAudioException::class.java) { timeline.append(secondPts, ByteArray(1_920)) }
            assertEquals("audio_pts_discontinuity", error.code)
        }
    }

    @Test fun unsupportedFormatAndMisalignedPcmCannotBecomeAWav() {
        for (format in listOf(PcmFormat(7_999, 1, 2), PcmFormat(192_001, 1, 2), PcmFormat(48_000, 3, 2), PcmFormat(48_000, 1, 4))) {
            assertThrows(MuxedVoiceAudioException::class.java) { PcmTimeline(format) }
        }
        val timeline = PcmTimeline(PcmFormat(48_000, 2, 2))
        assertEquals("unaligned_pcm", assertThrows(MuxedVoiceAudioException::class.java) { timeline.append(0, byteArrayOf(1, 2)) }.code)
    }

    @Test fun missingEosOrEmptyDecodeNeverReturnsUsablePcm() {
        val timeline = PcmTimeline(PcmFormat(48_000, 1, 2))
        assertEquals("empty_pcm", assertThrows(MuxedVoiceAudioException::class.java) { timeline.finish(true, 0) }.code)
        timeline.append(0, byteArrayOf(0, 0))
        assertEquals("missing_output_eos", assertThrows(MuxedVoiceAudioException::class.java) { timeline.finish(false, 0) }.code)
    }

    @Test fun durationLimitRejectsOversizedPcmBeforeAppending() {
        val timeline = PcmTimeline(PcmFormat(8_000, 1, 2), maxDurationUs = 1_000)
        timeline.append(0, ByteArray(16)) // eight frames = 1 ms
        assertEquals("pcm_duration_limit", assertThrows(MuxedVoiceAudioException::class.java) { timeline.append(1_000, byteArrayOf(0, 0)) }.code)
        assertEquals(8L, timeline.finish(true, 0).frames)
    }

    @Test fun negativeOffsetIsReportedWithoutClampingOrContentBasedCorrection() {
        val timeline = PcmTimeline(PcmFormat(48_000, 1, 2))
        timeline.append(-21_333, byteArrayOf(0, 8))
        val result = timeline.finish(true, 0)
        assertEquals(-21_333L, result.offsetUs)
        assertTrue(result.pcm.contentEquals(byteArrayOf(0, 8)))
    }

    @Test fun sharedLargeClockOriginDoesNotChangeRelativeOffset() {
        val origin = 86_400_000_000L
        val timeline = PcmTimeline(PcmFormat(48_000, 1, 2))
        timeline.append(origin + 160_000, ByteArray(1_920))
        timeline.append(origin + 180_000, ByteArray(1_920))
        assertEquals(160_000L, timeline.finish(true, origin).offsetUs)
    }

    @Test fun overflowingTimestampArithmeticCannotReturnAnOffset() {
        val timeline = PcmTimeline(PcmFormat(48_000, 1, 2))
        timeline.append(Long.MAX_VALUE - 10, byteArrayOf(0, 0))
        assertEquals("pts_arithmetic_overflow", assertThrows(MuxedVoiceAudioException::class.java) { timeline.finish(true, Long.MIN_VALUE + 10) }.code)
    }
}
