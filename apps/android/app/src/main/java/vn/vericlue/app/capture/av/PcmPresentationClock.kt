package vn.vericlue.app.capture.av

import kotlin.math.max
import kotlin.math.min
import kotlin.math.roundToInt

internal data class PcmClockAnchor(val frameIndex: Long, val ptsUs: Long)

/** Container presentation clock; the unanchored final block uses its nominal sample-rate duration. */
internal class PcmPresentationClock(
    val sampleRate: Int,
    val frames: Long,
    anchors: List<PcmClockAnchor>,
    checkCancelled: () -> Unit = {},
) {
    val durationUs: Double
    val outputFrames: Int
    val maximumInputRate: Double
    val minimumInputRate: Double
    val uniformNominal: Boolean
    private val positions: LongArray
    private val timesUs: LongArray

    init {
        checkCancelled()
        if (sampleRate !in 8_000..192_000 || frames <= 0 || frames > sampleRate * 12L) throw MuxedVoiceAudioException("pcm_clock_format")
        if (anchors.isEmpty() || anchors.size > frames || anchors.first().frameIndex != 0L) throw MuxedVoiceAudioException("pcm_clock_anchor")
        positions = LongArray(anchors.size)
        timesUs = LongArray(anchors.size)
        val origin = anchors.first().ptsUs
        var fastest = sampleRate.toDouble()
        var slowest = sampleRate.toDouble()
        var nominal = true
        for ((index, anchor) in anchors.withIndex()) {
            checkCancelled()
            if (anchor.frameIndex < 0 || anchor.frameIndex >= frames) throw MuxedVoiceAudioException("pcm_clock_anchor")
            val relative = subtractPts(anchor.ptsUs, origin)
            if (index > 0) {
                val deltaFrames = anchor.frameIndex - positions[index - 1]
                val deltaUs = subtractPts(relative, timesUs[index - 1])
                if (deltaFrames <= 0 || deltaUs <= 0) throw MuxedVoiceAudioException("pcm_clock_anchor")
                val numerator = deltaFrames * 1_000_000L // Frames are already bounded to 12 nominal seconds.
                val lower = (numerator + 2L * sampleRate - 1) / (2L * sampleRate)
                val upper = 2 * numerator / sampleRate
                // Open integer bounds refuse both rounded representations of the half/double-rate limits.
                if (deltaUs <= lower || deltaUs >= upper) throw MuxedVoiceAudioException("pcm_clock_rate_limit")
                val rate = numerator.toDouble() / deltaUs
                fastest = max(fastest, rate)
                slowest = min(slowest, rate)
            }
            val nominalError = relative * sampleRate - anchor.frameIndex * 1_000_000L
            if (nominalError !in -sampleRate.toLong()..sampleRate.toLong()) nominal = false
            positions[index] = anchor.frameIndex
            timesUs[index] = relative
        }
        checkCancelled()
        // No timestamp exists for the unanchored endpoint: retain the last block's nominal tail.
        durationUs = timesUs.last() + (frames - positions.last()) * 1_000_000.0 / sampleRate
        if (!durationUs.isFinite() || durationUs <= 0 || durationUs > 12_000_000) throw MuxedVoiceAudioException("pcm_duration_limit")
        outputFrames = (durationUs * 16_000 / 1_000_000).roundToInt()
        if (outputFrames !in 1..192_000) throw MuxedVoiceAudioException("pcm_duration_limit")
        maximumInputRate = fastest
        minimumInputRate = slowest
        uniformNominal = nominal
    }

    fun sourcePositionAtOutputFrame(index: Int, targetRate: Int = 16_000): Double {
        if (targetRate !in 8_000..192_000 || index < 0 || index >= (durationUs * targetRate / 1_000_000).roundToInt()) throw MuxedVoiceAudioException("pcm_clock_index")
        val time = index * 1_000_000.0 / targetRate
        var low = 0
        var high = timesUs.lastIndex
        while (low < high) {
            val middle = (low + high + 1) / 2
            if (timesUs[middle] <= time) low = middle else high = middle - 1
        }
        return if (low == timesUs.lastIndex) {
            positions[low] + (time - timesUs[low]) * sampleRate / 1_000_000
        } else {
            positions[low] + (time - timesUs[low]) * (positions[low + 1] - positions[low]) / (timesUs[low + 1] - timesUs[low])
        }
    }
}
