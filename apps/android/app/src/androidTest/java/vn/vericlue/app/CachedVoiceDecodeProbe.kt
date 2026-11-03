package vn.vericlue.app

import android.app.Instrumentation
import android.os.Bundle
import android.os.SystemClock
import java.io.File
import org.json.JSONArray
import org.json.JSONObject
import vn.vericlue.app.capture.av.MuxedDecodeEvent
import vn.vericlue.app.capture.av.MuxedVoiceAudioDecoder
import vn.vericlue.app.capture.av.MuxedVoiceAudioException
import vn.vericlue.app.capture.av.MUXED_PCM_CAPTURE_POLICY

/** Explicit local replay of one app-owned recording; never captures, uploads, plays or deletes. */
internal object CachedVoiceDecodeProbe {
    fun run(instrumentation: Instrumentation, arguments: Bundle): Bundle {
        val output = Bundle()
        val report = JSONObject().put("mode", "cached-voice-decode").put("decoded", false)
            .put("sourcePolicy", MUXED_PCM_CAPTURE_POLICY)
            .put("pcmClockMap", "piecewise-pts-with-nominal-tail-v1")
            .put("pcmLocalRateRatioOpenRange", JSONArray(listOf(0.5, 2.0)))
        val blocks = JSONArray().also { report.put("pcmBlocks", it) }
        var directory: File? = null
        try {
            val name = requireNotNull(arguments.getString("cacheName"))
            require(Regex("voice_[0-9]+(?:_[0-9]+)?\\.mp4").matches(name))
            val cache = instrumentation.targetContext.cacheDir.canonicalFile
            val source = File(cache, name).canonicalFile
            require(source.parentFile == cache && source.isFile)
            val parent = File(cache, "voice-decode-diagnostic")
            require(parent.isDirectory || parent.mkdir())
            val target = File(parent, "run-${SystemClock.elapsedRealtimeNanos()}")
            require(target.mkdir())
            directory = target
            report.put("sourceBytes", source.length())
            val decoded = MuxedVoiceAudioDecoder.decode(source, observer = { event ->
                when (event) {
                    is MuxedDecodeEvent.Detail -> report.put(event.key, event.value ?: JSONObject.NULL)
                    is MuxedDecodeEvent.PcmBlock -> blocks.put(JSONObject().put("ptsUs", event.ptsUs)
                        .put("bytes", event.bytes).put("sampleRate", event.sampleRate).put("channels", event.channels))
                }
            })
            report.put("decoded", true).put("firstPcmPtsUs", decoded.firstPcmPtsUs)
                .put("firstVideoPtsUs", decoded.firstVideoPtsUs).put("audioOffsetUs", decoded.audioOffsetUs)
                .put("nativeFrames", decoded.decodedFrames).put("nativeRate", decoded.sampleRate)
                .put("nativeChannels", decoded.channels).put("uploadFrames", decoded.uploadFrames)
                .put("normalizationPolicy", decoded.normalizationPolicy).put("audioOffsetMs", decoded.audioOffsetMs)
                .put("mappedDurationUs", decoded.mappedDurationUs).put("clockAnchorCount", decoded.clockAnchorCount)
                .put("maximumInputRate", decoded.maximumInputRate)
                .put("minimumInputRate", decoded.minimumInputRate)
            val wav = File(target, "decoded.wav").also { it.writeBytes(decoded.wav) }
            report.put("wavPath", wav.absolutePath)
        } catch (error: Exception) {
            report.put("failure", if (error is MuxedVoiceAudioException) error.code else error.javaClass.simpleName)
        }
        directory?.let { target ->
            val path = File(target, "report.json").also { it.writeText(report.toString(2)) }
            output.putString("report_path", path.absolutePath)
        }
        output.putBoolean("decoded", report.getBoolean("decoded"))
        output.putString("failure", report.optString("failure", ""))
        output.putInt("accepted_pcm_blocks", blocks.length())
        return output
    }
}
