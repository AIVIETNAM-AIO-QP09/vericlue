package vn.vericlue.app

import java.util.concurrent.CancellationException
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertThrows
import org.junit.Assert.assertTrue
import org.junit.Test
import vn.vericlue.app.capture.av.MuxedVoiceAudioException
import vn.vericlue.app.capture.av.PcmClockAnchor
import vn.vericlue.app.capture.av.PcmPresentationClock

class PcmPresentationClockTest {
    @Test fun inverseUsesFirstPtsAxisAndNominalFinalTail() {
        val origin = -9_000_000_000_000L
        val clock = PcmPresentationClock(16_000, 4_000, listOf(
            PcmClockAnchor(0, origin), PcmClockAnchor(1_000, origin + 62_500), PcmClockAnchor(2_000, origin + 126_500),
        ))
        assertEquals(251_500.0, clock.durationUs, 1e-9)
        assertEquals(4_024, clock.outputFrames)
        assertEquals(0.0, clock.sourcePositionAtOutputFrame(0), 0.0)
        assertEquals(1_000.0, clock.sourcePositionAtOutputFrame(1_000), 1e-9)
        assertEquals(1_976.5625, clock.sourcePositionAtOutputFrame(2_000), 1e-9)
        assertEquals(2_000.0, clock.sourcePositionAtOutputFrame(2_024), 1e-9)
        assertEquals(3_999.0, clock.sourcePositionAtOutputFrame(4_023), 1e-9)
        assertEquals(1_000.0, clock.sourcePositionAtOutputFrame(500, 8_000), 1e-9)
        assertFalse(clock.uniformNominal)
    }

    @Test fun localRatesAndDurationsFollowPositiveAndNegativeDrift() {
        val fast = PcmPresentationClock(48_000, 4_096, listOf(PcmClockAnchor(0, 10_000), PcmClockAnchor(2_048, 50_000)))
        val slow = PcmPresentationClock(48_000, 4_096, listOf(PcmClockAnchor(0, 10_000), PcmClockAnchor(2_048, 55_000)))
        assertEquals(51_200.0, fast.maximumInputRate, 1e-9)
        assertEquals(48_000.0, slow.maximumInputRate, 1e-9)
        assertEquals(1_323, fast.outputFrames)
        assertEquals(1_403, slow.outputFrames)
        assertEquals(2_048.0, fast.sourcePositionAtOutputFrame(640), 1e-9)
        assertEquals(2_048.0, slow.sourcePositionAtOutputFrame(720), 1e-9)
    }

    @Test fun conservativeIntegerBoundsRejectBothRoundingSidesOfHalfAndDoubleRate() {
        val origin = 8_640_000_000_000L
        for (duration in listOf(10_666L, 10_667L, 42_666L, 42_667L)) {
            assertThrows("duration $duration", MuxedVoiceAudioException::class.java) {
                PcmPresentationClock(48_000, 2_048, listOf(PcmClockAnchor(0, origin), PcmClockAnchor(1_024, origin + duration)))
            }
        }
        for (duration in listOf(10_668L, 42_665L)) {
            PcmPresentationClock(48_000, 2_048, listOf(PcmClockAnchor(0, origin), PcmClockAnchor(1_024, origin + duration)))
        }
    }

    @Test fun invalidAnchorsCannotDefineAPresentationClock() {
        val invalid = listOf(
            emptyList(), listOf(PcmClockAnchor(1, 0)), listOf(PcmClockAnchor(0, 0), PcmClockAnchor(0, 1)),
            listOf(PcmClockAnchor(0, 0), PcmClockAnchor(4_096, 85_333)),
            listOf(PcmClockAnchor(0, 1), PcmClockAnchor(1_024, 1)),
            listOf(PcmClockAnchor(0, 1), PcmClockAnchor(1_024, 0)),
        )
        for (anchors in invalid) assertThrows(MuxedVoiceAudioException::class.java) { PcmPresentationClock(48_000, 4_096, anchors) }
        for ((rate, frames) in listOf(0 to 1L, 192_001 to 1L, 48_000 to 0L, 48_000 to Long.MAX_VALUE)) {
            assertThrows(MuxedVoiceAudioException::class.java) { PcmPresentationClock(rate, frames, listOf(PcmClockAnchor(0, 0))) }
        }
    }

    @Test fun nominalAndActualDurationLimitsIncludeTheFinalBlock() {
        assertEquals(192_000, PcmPresentationClock(16_000, 192_000, listOf(PcmClockAnchor(0, 0))).outputFrames)
        assertThrows(MuxedVoiceAudioException::class.java) { PcmPresentationClock(16_000, 192_001, listOf(PcmClockAnchor(0, 0))) }
        assertThrows(MuxedVoiceAudioException::class.java) {
            PcmPresentationClock(16_000, 160_000, listOf(PcmClockAnchor(0, 0), PcmClockAnchor(80_000, 9_000_000)))
        }
        val tail = PcmPresentationClock(16_000, 16_000, listOf(PcmClockAnchor(0, 0), PcmClockAnchor(8_000, 600_000)))
        assertEquals(1_100_000.0, tail.durationUs, 1e-9)
        assertEquals(17_600, tail.outputFrames)
        assertEquals(15_999.0, tail.sourcePositionAtOutputFrame(17_599), 1e-9)
    }

    @Test fun largeOriginsAreAcceptedButRelativePtsOverflowIsRejected() {
        val origin = Long.MAX_VALUE - 1_000_000
        val clock = PcmPresentationClock(48_000, 4_096, listOf(PcmClockAnchor(0, origin), PcmClockAnchor(1_024, origin + 21_333)))
        assertTrue(clock.uniformNominal)
        assertThrows(MuxedVoiceAudioException::class.java) {
            PcmPresentationClock(48_000, 4_096, listOf(PcmClockAnchor(0, Long.MIN_VALUE), PcmClockAnchor(1_024, Long.MAX_VALUE)))
        }
    }

    @Test fun tinyQuantizedBlocksRemainNominalWithoutRelaxingWholeFrameBounds() {
        val anchors = (0L until 96).map { PcmClockAnchor(it, (it * 1_000_000 + 24_000) / 48_000) }
        val clock = PcmPresentationClock(48_000, 96, anchors)
        assertTrue(clock.uniformNominal)
        assertEquals(32, clock.outputFrames)
        for (duration in listOf(10L, 11L, 41L, 42L)) {
            assertThrows(MuxedVoiceAudioException::class.java) {
                PcmPresentationClock(48_000, 96, listOf(PcmClockAnchor(0, 1_000_000), PcmClockAnchor(1, 1_000_000 + duration)))
            }
        }
    }

    @Test fun constructionAndIndexValidationAreBoundedAndCancellable() {
        var checks = 0
        val anchors = (0L until 400).map { PcmClockAnchor(it * 1_024, it * 1_024_000_000 / 48_000) }
        assertThrows(CancellationException::class.java) {
            PcmPresentationClock(48_000, 409_600, anchors) { if (++checks >= 3) throw CancellationException("test") }
        }
        val clock = PcmPresentationClock(48_000, 4_800, listOf(PcmClockAnchor(0, 0)))
        for (index in listOf(-1, 1_600, Int.MAX_VALUE)) assertThrows(MuxedVoiceAudioException::class.java) { clock.sourcePositionAtOutputFrame(index) }
        assertThrows(MuxedVoiceAudioException::class.java) { clock.sourcePositionAtOutputFrame(0, 0) }
    }
}
