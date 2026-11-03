package vn.vericlue.app.capture.av

import android.media.AudioFormat
import android.media.MediaCodec
import android.media.MediaExtractor
import android.media.MediaFormat
import android.os.SystemClock
import java.io.File
import java.nio.ByteOrder
import java.util.concurrent.CancellationException
import vn.vericlue.app.capture.Wav

/** Canonical WAV plus original decoder diagnostics, all anchored to the same MP4 presentation clock. */
data class MuxedVoiceAudio(
    val wav: ByteArray,
    val audioOffsetMs: Int,
    val audioOffsetUs: Long,
    val sampleRate: Int,
    val channels: Int,
    val decodedFrames: Long,
    val firstPcmPtsUs: Long,
    val firstVideoPtsUs: Long,
    val uploadFrames: Int,
    val uploadSampleRate: Int = 16_000,
    val uploadChannels: Int = 1,
    val normalizationPolicy: String = Pcm16MonoNormalizer.CLOCK_POLICY,
    val source: String = MUXED_PCM_CAPTURE_POLICY,
    val mappedDurationUs: Double,
    val clockAnchorCount: Int,
    val maximumInputRate: Double,
    val minimumInputRate: Double,
)

/** Opt-in diagnostics; raw accepted PCM is delivered synchronously only to the supplied observer. */
sealed interface MuxedDecodeEvent {
    data class Detail(val key: String, val value: Any?) : MuxedDecodeEvent
    data class PcmBlock(val ptsUs: Long, val bytes: Int, val sampleRate: Int, val channels: Int, val pcm: ByteArray) : MuxedDecodeEvent
}

/** Bounded blocking decoder. Call on IO; cancellation and native failures never return a partial WAV. */
object MuxedVoiceAudioDecoder {
    private const val MAX_FILE_BYTES = 32L * 1024 * 1024
    private const val MAX_DURATION_US = 12_000_000L
    private const val MAX_PCM_BYTES = 192_000 * 2 * 2 * 12
    private const val TIMEOUT_MS = 15_000L

    fun decode(
        file: File,
        checkCancelled: () -> Unit = {},
        observer: (MuxedDecodeEvent) -> Unit = {},
    ): MuxedVoiceAudio {
        checkCancelled()
        if (!file.isFile || file.length() <= 0) throw MuxedVoiceAudioException("invalid_source_file")
        if (file.length() > MAX_FILE_BYTES) throw MuxedVoiceAudioException("source_size_limit")
        // A diagnostic observer cannot interrupt finally blocks or leak native resources.
        fun emit(event: MuxedDecodeEvent) { runCatching { observer(event) } }
        fun detail(key: String, value: Any?) = emit(MuxedDecodeEvent.Detail(key, value))
        try {
            val firstVideoPts = firstVideoPts(file, checkCancelled, ::detail)
            detail("firstVideoPtsUs", firstVideoPts)
            val audio = decodeAudio(file, firstVideoPts, checkCancelled, ::detail, ::emit)
            checkCancelled()
            val canonical = Pcm16MonoNormalizer.normalize(audio.pcm, audio.format.sampleRate, audio.format.channels,
                clock = audio.clock, checkCancelled = checkCancelled)
            val offsetMs = audio.offsetUs / 1_000
            if (offsetMs !in Int.MIN_VALUE.toLong()..Int.MAX_VALUE.toLong()) throw MuxedVoiceAudioException("audio_offset_range_limit")
            return MuxedVoiceAudio(
                wav = Wav.encode(canonical.pcm, Pcm16MonoNormalizer.SAMPLE_RATE, 1),
                audioOffsetMs = offsetMs.toInt(),
                audioOffsetUs = audio.offsetUs,
                sampleRate = audio.format.sampleRate,
                channels = audio.format.channels,
                decodedFrames = audio.frames,
                firstPcmPtsUs = audio.firstPcmPtsUs,
                firstVideoPtsUs = firstVideoPts,
                uploadFrames = canonical.frames,
                mappedDurationUs = audio.clock.durationUs,
                clockAnchorCount = audio.anchors.size,
                maximumInputRate = audio.clock.maximumInputRate,
                minimumInputRate = audio.clock.minimumInputRate,
            )
        } catch (error: CancellationException) {
            throw error
        } catch (error: MuxedVoiceAudioException) {
            throw error
        } catch (error: Exception) {
            throw MuxedVoiceAudioException("native_decode_failed", error)
        }
    }

    private fun firstVideoPts(file: File, checkCancelled: () -> Unit, detail: (String, Any?) -> Unit): Long {
        val extractor = MediaExtractor()
        try {
            extractor.setDataSource(file.absolutePath)
            val videoTracks = tracks(extractor, "video/")
            if (videoTracks.size != 1 || tracks(extractor, "audio/").size != 1) throw MuxedVoiceAudioException("expected_one_audio_one_video")
            extractor.selectTrack(videoTracks.single())
            var minimum: Long? = null
            var maximum: Long? = null
            var samples = 0
            val deadline = SystemClock.elapsedRealtime() + TIMEOUT_MS
            while (extractor.sampleTrackIndex >= 0) {
                checkDeadline(deadline, checkCancelled)
                if (++samples > 2_400) throw MuxedVoiceAudioException("video_sample_limit")
                val pts = extractor.sampleTime
                minimum = minimum?.let { minOf(it, pts) } ?: pts
                maximum = maximum?.let { maxOf(it, pts) } ?: pts
                if (subtractPts(maximum, minimum) > MAX_DURATION_US) throw MuxedVoiceAudioException("video_duration_limit")
                if (!extractor.advance()) break
            }
            detail("videoSamples", samples)
            return minimum ?: throw MuxedVoiceAudioException("empty_video")
        } finally {
            val released = runCatching { extractor.release() }.isSuccess
            detail("videoExtractorReleased", released)
            if (!released) throw MuxedVoiceAudioException("native_cleanup_failed")
        }
    }

    private fun decodeAudio(
        file: File,
        videoPtsUs: Long,
        checkCancelled: () -> Unit,
        detail: (String, Any?) -> Unit,
        emit: (MuxedDecodeEvent) -> Unit,
    ): PcmAudio {
        val extractor = MediaExtractor()
        var codec: MediaCodec? = null
        var started = false
        var cleanupFailed = false
        var decoded: PcmAudio? = null
        var failure: Exception? = null
        try {
            checkCancelled()
            if (ByteOrder.nativeOrder() != ByteOrder.LITTLE_ENDIAN) throw MuxedVoiceAudioException("pcm_byte_order_unsupported")
            extractor.setDataSource(file.absolutePath)
            val audioTrack = tracks(extractor, "audio/").singleOrNull() ?: throw MuxedVoiceAudioException("expected_one_audio_track")
            val inputFormat = extractor.getTrackFormat(audioTrack)
            val mime = inputFormat.getString(MediaFormat.KEY_MIME) ?: throw MuxedVoiceAudioException("missing_audio_mime")
            if (inputFormat.containsKey(MediaFormat.KEY_DURATION) && inputFormat.getLong(MediaFormat.KEY_DURATION) > MAX_DURATION_US) throw MuxedVoiceAudioException("audio_duration_limit")
            detail("inputAudioFormat", inputFormat.toString())
            detail("encoderDelayFrames", optionalInt(inputFormat, "encoder-delay"))
            detail("encoderPaddingFrames", optionalInt(inputFormat, "encoder-padding"))
            if ((optionalInt(inputFormat, "encoder-delay") ?: 0) < 0 || (optionalInt(inputFormat, "encoder-padding") ?: 0) < 0) throw MuxedVoiceAudioException("invalid_gapless_metadata")
            // Android receives the original trim metadata once. No manual priming/padding removal.
            inputFormat.setInteger(MediaFormat.KEY_PCM_ENCODING, AudioFormat.ENCODING_PCM_16BIT)
            extractor.selectTrack(audioTrack)
            val decoder = MediaCodec.createDecoderByType(mime).also { codec = it }
            detail("decoderName", decoder.name)
            decoder.configure(inputFormat, null, null, 0)
            decoder.start()
            started = true
            val info = MediaCodec.BufferInfo()
            var inputEos = false
            var outputEos = false
            var inputSamples = 0
            var outputBuffers = 0
            var lastInputPts = 0L
            var timeline: PcmTimeline? = null
            var pcmFormat: PcmFormat? = null
            val deadline = SystemClock.elapsedRealtime() + TIMEOUT_MS
            fun acceptFormat(format: MediaFormat) {
                val current = PcmFormat(format.getInteger(MediaFormat.KEY_SAMPLE_RATE), format.getInteger(MediaFormat.KEY_CHANNEL_COUNT), optionalInt(format, MediaFormat.KEY_PCM_ENCODING) ?: AudioFormat.ENCODING_PCM_16BIT)
                if (pcmFormat != null && current != pcmFormat) throw MuxedVoiceAudioException("midstream_pcm_format_change")
                if (timeline == null) {
                    pcmFormat = current
                    timeline = PcmTimeline(current)
                    detail("outputAudioFormat", format.toString())
                }
            }
            while (!outputEos) {
                checkDeadline(deadline, checkCancelled)
                if (!inputEos) {
                    val inputIndex = decoder.dequeueInputBuffer(10_000)
                    if (inputIndex >= 0) {
                        if (extractor.sampleTrackIndex < 0) {
                            decoder.queueInputBuffer(inputIndex, 0, 0, lastInputPts, MediaCodec.BUFFER_FLAG_END_OF_STREAM)
                            inputEos = true
                        } else {
                            if (++inputSamples > 8_192) throw MuxedVoiceAudioException("audio_sample_limit")
                            val flags = extractor.sampleFlags
                            if (flags and (MediaExtractor.SAMPLE_FLAG_ENCRYPTED or MediaExtractor.SAMPLE_FLAG_PARTIAL_FRAME) != 0) throw MuxedVoiceAudioException("unsupported_encoded_sample_flags")
                            val input = decoder.getInputBuffer(inputIndex) ?: throw MuxedVoiceAudioException("missing_input_buffer")
                            input.clear()
                            val size = extractor.sampleSize
                            if (size <= 0 || size > input.capacity() || size > 1_048_576) throw MuxedVoiceAudioException("encoded_sample_size_limit")
                            val count = extractor.readSampleData(input, 0)
                            if (count.toLong() != size) throw MuxedVoiceAudioException("encoded_sample_truncated")
                            val pts = extractor.sampleTime
                            if (inputSamples > 1 && pts <= lastInputPts) throw MuxedVoiceAudioException("nonmonotonic_encoded_audio")
                            if (inputSamples == 1) detail("firstEncodedAudioPtsUs", pts)
                            lastInputPts = pts
                            decoder.queueInputBuffer(inputIndex, 0, count, pts, 0)
                            extractor.advance()
                        }
                    }
                }
                val outputIndex = decoder.dequeueOutputBuffer(info, 10_000)
                when {
                    outputIndex >= 0 -> {
                        try {
                            if (info.size < 0 || info.offset < 0) throw MuxedVoiceAudioException("invalid_output_range")
                            if (info.size > 0 && info.flags and MediaCodec.BUFFER_FLAG_CODEC_CONFIG == 0) {
                                if (++outputBuffers > 4_096) throw MuxedVoiceAudioException("output_buffer_limit")
                                acceptFormat(decoder.getOutputFormat(outputIndex))
                                val buffer = decoder.getOutputBuffer(outputIndex) ?: throw MuxedVoiceAudioException("missing_output_buffer")
                                if (info.size > MAX_PCM_BYTES || info.offset.toLong() + info.size > buffer.capacity()) throw MuxedVoiceAudioException("invalid_output_range")
                                val bytes = ByteArray(info.size)
                                buffer.duplicate().apply { clear(); position(info.offset); limit(info.offset + info.size) }.get(bytes)
                                timeline!!.append(info.presentationTimeUs, bytes)
                                val format = pcmFormat!!
                                emit(MuxedDecodeEvent.PcmBlock(info.presentationTimeUs, info.size, format.sampleRate, format.channels, bytes))
                            }
                            if (info.flags and MediaCodec.BUFFER_FLAG_END_OF_STREAM != 0) outputEos = true
                        } finally {
                            decoder.releaseOutputBuffer(outputIndex, false)
                        }
                    }
                    outputIndex == MediaCodec.INFO_OUTPUT_FORMAT_CHANGED -> acceptFormat(decoder.outputFormat)
                    outputIndex == MediaCodec.INFO_TRY_AGAIN_LATER || outputIndex == MediaCodec.INFO_OUTPUT_BUFFERS_CHANGED -> Unit
                    else -> throw MuxedVoiceAudioException("unexpected_codec_status")
                }
            }
            detail("inputEos", inputEos)
            detail("outputEos", outputEos)
            detail("inputSamples", inputSamples)
            detail("outputBuffers", outputBuffers)
            if (!inputEos) throw MuxedVoiceAudioException("output_eos_before_input_eos")
            decoded = (timeline ?: throw MuxedVoiceAudioException("empty_pcm")).finish(outputEos, videoPtsUs)
        } catch (error: Exception) {
            failure = error
        } finally {
            if (started) {
                val stopped = runCatching { codec?.stop() }.isSuccess
                detail("decoderStopped", stopped)
                cleanupFailed = cleanupFailed || !stopped
            }
            if (codec != null) {
                val released = runCatching { codec?.release() }.isSuccess
                detail("decoderReleased", released)
                cleanupFailed = cleanupFailed || !released
            }
            val extractorReleased = runCatching { extractor.release() }.isSuccess
            detail("audioExtractorReleased", extractorReleased)
            cleanupFailed = cleanupFailed || !extractorReleased
        }
        failure?.let { throw it }
        if (cleanupFailed) throw MuxedVoiceAudioException("native_cleanup_failed")
        return decoded ?: throw MuxedVoiceAudioException("empty_pcm")
    }

    private fun tracks(extractor: MediaExtractor, prefix: String): List<Int> = (0 until extractor.trackCount).filter {
        extractor.getTrackFormat(it).getString(MediaFormat.KEY_MIME)?.startsWith(prefix) == true
    }

    private fun optionalInt(format: MediaFormat, key: String): Int? = if (format.containsKey(key)) format.getInteger(key) else null

    private fun checkDeadline(deadline: Long, checkCancelled: () -> Unit) {
        checkCancelled()
        if (Thread.currentThread().isInterrupted) throw CancellationException("Voice decoding interrupted")
        if (SystemClock.elapsedRealtime() > deadline) throw MuxedVoiceAudioException("native_decode_timeout")
    }
}
