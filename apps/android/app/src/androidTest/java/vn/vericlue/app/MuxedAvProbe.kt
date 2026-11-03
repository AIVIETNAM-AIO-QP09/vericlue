package vn.vericlue.app

import android.app.Instrumentation
import android.os.Bundle
import android.os.SystemClock
import java.io.File
import java.io.ByteArrayOutputStream
import java.nio.ByteBuffer
import java.nio.ByteOrder
import java.security.MessageDigest
import kotlin.math.abs
import org.json.JSONArray
import org.json.JSONObject
import vn.vericlue.app.capture.av.MuxedDecodeEvent
import vn.vericlue.app.capture.av.MuxedVoiceAudio
import vn.vericlue.app.capture.av.MuxedVoiceAudioDecoder
import vn.vericlue.app.capture.av.MuxedVoiceAudioException

private class ProbeFailure(val code: String) : Exception(code)

/** Synthetic assets only. No camera/microphone, playback, upload, model or capture-flow changes. */
internal object MuxedAvProbe {
    private const val MAX_FILE_BYTES = 32L * 1024 * 1024
    private val safeName = Regex("[A-Za-z0-9][A-Za-z0-9._-]{0,99}")

    fun run(instrumentation: Instrumentation, arguments: Bundle): Bundle {
        val output = Bundle()
        try {
            val manifestName = arguments.getString("manifest") ?: "muxed-av.json"
            if (!safeName.matches(manifestName)) throw ProbeFailure("invalid_manifest_name")
            val assets = instrumentation.context.assets
            val manifestBytes = assets.open(manifestName).use { input ->
                val bytes = ByteArrayOutputStream()
                val buffer = ByteArray(4_096)
                while (bytes.size() <= 65_536) {
                    val count = input.read(buffer)
                    if (count < 0) break
                    bytes.write(buffer, 0, count)
                }
                bytes.toByteArray()
            }
            if (manifestBytes.size > 65_536) throw ProbeFailure("manifest_size_limit")
            val fixtures = JSONObject(String(manifestBytes, Charsets.UTF_8)).getJSONArray("fixtures")
            if (fixtures.length() !in 1..8) throw ProbeFailure("fixture_count_limit")
            val parent = File(instrumentation.targetContext.cacheDir, "shared-av-probe")
            if (!parent.isDirectory && !parent.mkdirs()) throw ProbeFailure("probe_directory_failed")
            val directory = File(parent, "run-${SystemClock.elapsedRealtimeNanos()}")
            if (!directory.mkdir()) throw ProbeFailure("probe_run_directory_failed")
            val report = JSONObject().put("mode", "shared-av").put("probeOnly", true)
                .put("trimPolicy", "original-decoder-format-no-manual-trim")
                .put("videoPtsBasis", "minimum-extractor-sample-presentationTimeUs")
                .put("pcmClockMap", "piecewise-pts-with-nominal-tail-v1")
                .put("pcmLocalRateRatioOpenRange", JSONArray(listOf(0.5, 2.0)))
                .put("pcmPtsStrictlyIncreasing", true)
                .put("nativePcmValidation", "unchanged-decoder-format")
                .put("nativePtsUnchanged", true)
                .put("canonicalWavNormalization", "pcm16-mono16k-pts-sinc-v2")
                .put("hardwareClockVerified", false)
            val results = JSONArray()
            val summary = JSONArray()
            var passed = true
            val names = mutableSetOf<String>()
            val cancelArgument = arguments.getString("cancelAfterBuffers")
            val cancelAfter = cancelArgument?.toIntOrNull() ?: if (cancelArgument == null) -1 else throw ProbeFailure("invalid_cancel_argument")
            for (index in 0 until fixtures.length()) {
                val fixture = fixtures.getJSONObject(index)
                val name = fixture.getString("asset")
                if (!safeName.matches(name) || !name.endsWith(".mp4") || !names.add(name)) throw ProbeFailure("invalid_fixture_name")
                val details = JSONObject().put("asset", name).put("passed", false)
                val source = File(directory, name)
                val wavFile = File(directory, "$name.wav")
                try {
                    assets.open(name).use { input ->
                        source.outputStream().use { destination ->
                            val buffer = ByteArray(65_536)
                            var total = 0L
                            while (true) {
                                val count = input.read(buffer)
                                if (count < 0) break
                                total += count
                                if (total > MAX_FILE_BYTES) throw ProbeFailure("fixture_size_limit")
                                destination.write(buffer, 0, count)
                            }
                        }
                    }
                    details.put("fixtureSha256", sha256(source.readBytes()))
                    var outputBuffers = 0
                    var nativeTonePts: Long? = null
                    val threshold = fixture.optInt("toneThresholdPcm16", 1_024)
                    if (threshold !in 1..32_767) throw ProbeFailure("invalid_tone_threshold")
                    val nativePcmHash = MessageDigest.getInstance("SHA-256")
                    val blocks = JSONArray().also { details.put("pcmBlocks", it) }
                    val decoded = MuxedVoiceAudioDecoder.decode(source,
                        checkCancelled = {
                            if (cancelAfter >= 0 && outputBuffers >= cancelAfter) throw MuxedVoiceAudioException("cancelled_by_probe")
                        }, observer = { event ->
                            when (event) {
                                is MuxedDecodeEvent.Detail -> details.put(event.key, event.value ?: JSONObject.NULL)
                                is MuxedDecodeEvent.PcmBlock -> {
                                    outputBuffers++
                                    blocks.put(JSONObject().put("ptsUs", event.ptsUs).put("bytes", event.bytes))
                                    nativePcmHash.update(event.pcm)
                                    if (nativeTonePts == null) nativeTonePts = tonePts(event, threshold)
                                }
                            }
                        })
                    details.put("sampleRate", decoded.sampleRate).put("channels", decoded.channels)
                        .put("pcmEncoding", 2).put("decodedFrames", decoded.decodedFrames)
                        .put("capturePolicy", decoded.source)
                        .put("firstKeptPcmPtsUs", decoded.firstPcmPtsUs).put("observedOffsetUs", decoded.audioOffsetUs)
                        .put("toneFromVideoUs", nativeTonePts?.minus(decoded.firstVideoPtsUs) ?: JSONObject.NULL)
                        .put("pcmSha256", hex(nativePcmHash.digest()))
                        .put("uploadSampleRate", decoded.uploadSampleRate).put("uploadChannels", decoded.uploadChannels)
                        .put("uploadFrames", decoded.uploadFrames).put("normalizationPolicy", decoded.normalizationPolicy)
                        .put("mappedDurationUs", decoded.mappedDurationUs).put("clockAnchorCount", decoded.clockAnchorCount)
                        .put("maximumInputRate", decoded.maximumInputRate)
                        .put("minimumInputRate", decoded.minimumInputRate)
                    val failures = validate(fixture, decoded, nativeTonePts, details)
                    details.put("validationFailures", failures)
                    // Unique run directories retain diagnostics; failed fixtures never write a WAV.
                    if (failures.length() == 0) {
                        wavFile.writeBytes(decoded.wav)
                        details.put("wavPath", wavFile.absolutePath).put("passed", true)
                    }
                } catch (error: Exception) {
                    details.put("failure", when (error) {
                        is ProbeFailure -> error.code
                        is MuxedVoiceAudioException -> error.code
                        else -> "native_${error.javaClass.simpleName}"
                    })
                } finally {
                    details.put("sourceRetainedForDiagnostics", source.isFile)
                        .put("sourcePath", source.absolutePath)
                }
                if (!details.getBoolean("passed")) passed = false
                results.put(details)
                summary.put(JSONObject().put("asset", name).put("passed", details.getBoolean("passed"))
                    .put("failure", details.opt("failure") ?: JSONObject.NULL)
                    .put("validationFailures", details.opt("validationFailures") ?: JSONObject.NULL)
                    .put("observedOffsetUs", details.opt("observedOffsetUs") ?: JSONObject.NULL))
            }
            report.put("passed", passed).put("fixtures", results)
            val reportFile = File(directory, "report.json")
            reportFile.writeText(report.toString(2))
            output.putBoolean("passed", passed)
            output.putString("report_path", reportFile.absolutePath)
            output.putString("fixture_summary", summary.toString())
        } catch (error: Exception) {
            output.putBoolean("passed", false)
            output.putString("failure", if (error is ProbeFailure) error.code else "probe_${error.javaClass.simpleName}")
        }
        return output
    }

    private fun validate(expected: JSONObject, actual: MuxedVoiceAudio, tonePts: Long?, details: JSONObject): JSONArray {
        val failures = JSONArray()
        val expectedOffset = expected.getLong("expectedOffsetUs")
        val expectedTone = expected.getLong("expectedToneFromVideoUs")
        val tolerance = expected.getLong("toleranceUs")
        val toneTolerance = expected.getLong("toneToleranceUs")
        if (tolerance !in 0..100_000 || toneTolerance !in 0..100_000) throw ProbeFailure("invalid_fixture_tolerance")
        if (expectedOffset !in -60_000_000..60_000_000 || expectedTone !in -60_000_000..60_000_000) throw ProbeFailure("invalid_fixture_pts")
        details.put("expected", expected)
        if (actual.sampleRate != expected.getInt("sampleRate")) failures.put("sample_rate_mismatch")
        if (actual.channels != expected.getInt("channels")) failures.put("channel_count_mismatch")
        if (actual.decodedFrames != expected.getLong("expectedFrames")) failures.put("decoded_frame_count_mismatch")
        if (abs(actual.audioOffsetUs - expectedOffset) > tolerance) failures.put("pcm_pts_offset_mismatch")
        if (tonePts == null) failures.put("tone_not_found")
        else if (abs(tonePts - actual.firstVideoPtsUs - expectedTone) > toneTolerance) failures.put("tone_onset_mismatch")
        val header = ByteBuffer.wrap(actual.wav).order(ByteOrder.LITTLE_ENDIAN)
        if (actual.wav.size < 44 || header.getInt(24) != 16_000 || header.getShort(22).toInt() != 1 ||
            header.getShort(34).toInt() != 16 || header.getInt(40) != actual.wav.size - 44 ||
            actual.uploadFrames * 2 != actual.wav.size - 44 || actual.uploadSampleRate != 16_000 || actual.uploadChannels != 1 ||
            actual.normalizationPolicy != "pcm16-mono16k-pts-sinc-v2") failures.put("canonical_wav_format_mismatch")
        if (abs(actual.uploadFrames / 16_000.0 - actual.mappedDurationUs / 1_000_000.0) > 1.0 / 16_000) failures.put("canonical_duration_mismatch")
        return failures
    }

    /** Content marker is a fixture assertion only; it never changes production audio or timestamps. */
    private fun tonePts(block: MuxedDecodeEvent.PcmBlock, threshold: Int): Long? {
        for (index in 0 until block.pcm.size - 1 step 2) {
            val sample = ((block.pcm[index].toInt() and 255) or (block.pcm[index + 1].toInt() shl 8)).toShort().toInt()
            if (abs(sample) >= threshold) {
                return block.ptsUs + (index / (block.channels * 2)) * 1_000_000L / block.sampleRate
            }
        }
        return null
    }

    private fun hex(bytes: ByteArray): String = bytes.joinToString("") { "%02x".format(it.toInt() and 255) }
    private fun sha256(bytes: ByteArray): String = hex(MessageDigest.getInstance("SHA-256").digest(bytes))
}
