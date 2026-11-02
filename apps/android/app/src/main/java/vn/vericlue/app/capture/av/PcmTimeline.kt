package vn.vericlue.app.capture.av

import java.io.ByteArrayOutputStream

class MuxedVoiceAudioException(val code: String, cause: Throwable? = null) : Exception(code, cause)
internal data class PcmFormat(val sampleRate: Int, val channels: Int, val encoding: Int)
internal data class PcmAudio(
    val format: PcmFormat,
    val pcm: ByteArray,
    val frames: Long,
    val firstPcmPtsUs: Long,
    val offsetUs: Long,
)

/** Validates decoded PCM without trimming, filling gaps or repairing timestamps. */
internal class PcmTimeline(
    private val format: PcmFormat,
    private val maxDurationUs: Long = 12_000_000,
) {
    init {
        if (format.sampleRate !in 8_000..192_000 || format.channels !in 1..2 || format.encoding != 2) {
            throw MuxedVoiceAudioException("unsupported_pcm_format")
        }
        if (maxDurationUs !in 1..12_000_000) throw MuxedVoiceAudioException("invalid_decode_bounds")
    }

    private val pcm = ByteArrayOutputStream()
    private var firstPtsUs: Long? = null
    private var frames = 0L

    fun append(ptsUs: Long, bytes: ByteArray) {
        val frameBytes = format.channels * 2
        if (bytes.isEmpty() || bytes.size % frameBytes != 0) throw MuxedVoiceAudioException("unaligned_pcm")
        val addedFrames = bytes.size / frameBytes
        if (frames + addedFrames > maxDurationUs * format.sampleRate / 1_000_000) throw MuxedVoiceAudioException("pcm_duration_limit")
        firstPtsUs?.let { first ->
            val expectedPts = addPts(first, frames * 1_000_000 / format.sampleRate)
            // Explicit two-sample tolerance; larger gaps are never repaired or filled with silence.
            val toleranceUs = 2L * ((1_000_000L + format.sampleRate - 1) / format.sampleRate)
            if (subtractPts(ptsUs, expectedPts) !in -toleranceUs..toleranceUs) throw MuxedVoiceAudioException("audio_pts_discontinuity")
        }
        if (firstPtsUs == null) firstPtsUs = ptsUs
        pcm.write(bytes)
        frames += addedFrames
    }

    fun finish(sawOutputEos: Boolean, videoPtsUs: Long): PcmAudio {
        if (frames == 0L) throw MuxedVoiceAudioException("empty_pcm")
        if (!sawOutputEos) throw MuxedVoiceAudioException("missing_output_eos")
        val first = firstPtsUs ?: throw MuxedVoiceAudioException("empty_pcm")
        return PcmAudio(format, pcm.toByteArray(), frames, first, subtractPts(first, videoPtsUs))
    }
}

internal fun subtractPts(left: Long, right: Long): Long = try {
    Math.subtractExact(left, right)
} catch (error: ArithmeticException) {
    throw MuxedVoiceAudioException("pts_arithmetic_overflow", error)
}

internal fun addPts(left: Long, right: Long): Long = try {
    Math.addExact(left, right)
} catch (error: ArithmeticException) {
    throw MuxedVoiceAudioException("pts_arithmetic_overflow", error)
}
