package vn.vericlue.app.capture.av

import kotlin.math.PI
import kotlin.math.abs
import kotlin.math.ceil
import kotlin.math.cos
import kotlin.math.floor
import kotlin.math.max
import kotlin.math.min
import kotlin.math.roundToInt
import kotlin.math.sin

internal data class NormalizedPcm(val pcm: ByteArray, val frames: Int)

/** Centered Blackman-windowed sinc on the declared clock; no VAD, initial shift or silence insertion. */
internal object Pcm16MonoNormalizer {
    const val SAMPLE_RATE = 16_000
    const val POLICY = "pcm16-mono16k-sinc-v1"
    const val CLOCK_POLICY = "pcm16-mono16k-pts-sinc-v2"

    fun normalize(pcm: ByteArray, sourceRate: Int, channels: Int, clock: PcmPresentationClock? = null, checkCancelled: () -> Unit = {}): NormalizedPcm {
        checkCancelled()
        if (sourceRate !in 8_000..192_000 || channels !in 1..2) throw MuxedVoiceAudioException("unsupported_normalization_format")
        if (pcm.isEmpty() || pcm.size % (channels * 2) != 0) throw MuxedVoiceAudioException("unaligned_pcm")
        val inputFrames = pcm.size / (channels * 2)
        if (inputFrames > sourceRate * 12) throw MuxedVoiceAudioException("pcm_duration_limit")
        if (clock != null && (clock.sampleRate != sourceRate || clock.frames != inputFrames.toLong())) throw MuxedVoiceAudioException("pcm_clock_mismatch")
        val nominalFrames = ((inputFrames.toLong() * SAMPLE_RATE + sourceRate / 2) / sourceRate).toInt()
        val outputFrames = clock?.outputFrames ?: nominalFrames
        if (outputFrames <= 0) throw MuxedVoiceAudioException("empty_normalized_pcm")
        // At most 1 us of nominal quantization may reuse v1 only if actual-duration rounding agrees.
        val mappedClock = clock?.takeUnless { it.uniformNominal && it.outputFrames == nominalFrames }
        if (sourceRate == SAMPLE_RATE && channels == 1 && mappedClock == null) {
            checkCancelled()
            val copy = pcm.copyOf()
            checkCancelled()
            return NormalizedPcm(copy, inputFrames)
        }
        val mono = DoubleArray(inputFrames)
        for (frame in mono.indices) {
            if (frame % 2_048 == 0) checkCancelled()
            var sum = 0.0
            for (channel in 0 until channels) {
                val index = (frame * channels + channel) * 2
                sum += ((pcm[index].toInt() and 255) or (pcm[index + 1].toInt() shl 8)).toShort().toInt()
            }
            mono[frame] = sum / channels
        }
        val output = ByteArray(outputFrames * 2)
        if (sourceRate == SAMPLE_RATE && mappedClock == null) {
            for (index in 0 until outputFrames) {
                if (index % 256 == 0) checkCancelled()
                writeSample(output, index, mono[index])
            }
        } else {
            val maximumInputRate = mappedClock?.maximumInputRate ?: sourceRate.toDouble()
            val halfWidth = ceil(32 * max(1.0, maximumInputRate / SAMPLE_RATE)).toInt()
            val phases = if (mappedClock == null) min(SAMPLE_RATE / gcd(sourceRate, SAMPLE_RATE), 1_024) else 1_024
            // Six percent transition margin below the smaller Nyquist; taps grow with decimation.
            val cutoff = 0.47 * min(1.0, SAMPLE_RATE / maximumInputRate)
            val kernels = Array(phases) { phase ->
                checkCancelled()
                val fraction = phase.toDouble() / phases
                val weights = DoubleArray(2 * halfWidth + 1) { tap ->
                    val distance = tap - halfWidth - fraction
                    if (abs(distance) > halfWidth) 0.0 else {
                        val sinc = if (abs(distance) < 1e-12) 2 * cutoff else sin(2 * PI * cutoff * distance) / (PI * distance)
                        val window = 0.42 + 0.5 * cos(PI * distance / halfWidth) + 0.08 * cos(2 * PI * distance / halfWidth)
                        sinc * window
                    }
                }
                val gain = weights.sum()
                for (tap in weights.indices) weights[tap] /= gain
                weights
            }
            for (index in 0 until outputFrames) {
                if (index % 256 == 0) checkCancelled()
                val integerPosition = index.toLong() * sourceRate
                val position = mappedClock?.sourcePositionAtOutputFrame(index)
                var center = if (position == null) (integerPosition / SAMPLE_RATE).toInt() else floor(position).toInt()
                var phase = if (position == null) (((integerPosition % SAMPLE_RATE) * phases + SAMPLE_RATE / 2) / SAMPLE_RATE).toInt()
                    else ((position - center) * phases).roundToInt()
                if (phase == phases) { phase = 0; center++ }
                var sample = 0.0
                val weights = kernels[phase]
                for (tap in weights.indices) {
                    // Constant edge extension preserves DC without adding a leading filter delay.
                    val source = (center + tap - halfWidth).coerceIn(0, inputFrames - 1)
                    sample += mono[source] * weights[tap]
                }
                writeSample(output, index, sample)
            }
        }
        checkCancelled()
        return NormalizedPcm(output, outputFrames)
    }

    private fun writeSample(output: ByteArray, index: Int, value: Double) {
        val sample = value.coerceIn(-32_768.0, 32_767.0).roundToInt()
        output[index * 2] = sample.toByte()
        output[index * 2 + 1] = (sample shr 8).toByte()
    }

    private fun gcd(left: Int, right: Int): Int {
        var a = left
        var b = right
        while (b != 0) { val next = a % b; a = b; b = next }
        return a
    }
}
