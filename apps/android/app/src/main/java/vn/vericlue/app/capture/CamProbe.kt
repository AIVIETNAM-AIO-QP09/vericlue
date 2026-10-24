package vn.vericlue.app.capture

import android.os.Build
import java.io.File
import kotlinx.serialization.SerialName
import kotlinx.serialization.Serializable
import kotlinx.serialization.json.JsonObject

/**
 * CamProbe for the native app (ADR-0014 consequence: no JavaScript to tamper with, so the
 * checks are device-level). Same JSON fields as the web (apps/web/src/lib/capture/camprobe.ts),
 * read by ml/src/vericlue_ml/presence/camprobe.py. The app only reports; the server decides.
 *
 * Without this object the server marks CamProbe as degraded, which can never pass (rule 4).
 */
@Serializable
data class CamProbe(
    @SerialName("api_tamper_flags") val apiTamperFlags: List<String>,
    @SerialName("constraint_probes") val constraintProbes: List<JsonObject> = emptyList(),
    @SerialName("device_label") val deviceLabel: String,
    @SerialName("duplicate_frame_ratio") val duplicateFrameRatio: Double? = null,
)

/** Facts about the device; collected on the phone, judged by pure rules (testable on the JVM). */
data class DeviceFacts(
    val fingerprint: String,
    val hardware: String,
    val product: String,
    val tags: String,
    val suPathFound: Boolean,
    val procMaps: String,
    val xposedLoaded: Boolean,
)

object CamProbeRules {
    // Flags use the web's "<api>:<reason>" shape so the server lists them as evidence.
    const val EMULATOR = "android:emulator"
    const val ROOT = "android:root"
    const val TEST_KEYS = "android:test_keys"
    const val HOOK_FRIDA = "android:hook_frida"
    const val HOOK_XPOSED = "android:hook_xposed"

    fun flags(f: DeviceFacts): List<String> = buildList {
        val fp = f.fingerprint.lowercase()
        if (fp.startsWith("generic") || "emulator" in fp || "sdk_gphone" in fp ||
            f.hardware in setOf("goldfish", "ranchu") || f.product.startsWith("sdk")
        ) add(EMULATOR)
        if (f.suPathFound) add(ROOT)
        if ("test-keys" in f.tags) add(TEST_KEYS)
        val maps = f.procMaps.lowercase()
        if ("frida" in maps || "gum-js" in maps) add(HOOK_FRIDA)
        if (f.xposedLoaded || "xposed" in maps || "lspd" in maps) add(HOOK_XPOSED)
    }
}

/**
 * Share of consecutive frames that are byte-identical after downscaling to 24×24 grey
 * (same measure as the web). A real sensor always has noise; a looped image does not.
 */
class DuplicateFrameMeter(private val window: Int = 30) {
    private var last: ByteArray? = null
    private var pairs = 0
    private var same = 0

    @Synchronized
    fun add(thumb: ByteArray) {
        if (pairs >= window) return
        val prev = last
        if (prev != null) {
            pairs++
            if (prev.contentEquals(thumb)) same++
        }
        last = thumb
    }

    @Synchronized
    fun ratio(): Double? = if (pairs == 0) null else same.toDouble() / pairs

    @Synchronized
    fun reset() {
        last = null
        pairs = 0
        same = 0
    }

    companion object {
        const val SIZE = 24

        /** 24×24 nearest-neighbour sample of a luma plane. */
        fun thumbnail(luma: ByteArray, width: Int, height: Int, rowStride: Int): ByteArray =
            ByteArray(SIZE * SIZE) { i ->
                val x = (i % SIZE) * width / SIZE
                val y = (i / SIZE) * height / SIZE
                luma[y * rowStride + x]
            }
    }
}

/** Reads the device facts. Each check is best-effort and never throws. */
object DeviceProbe {
    private val SU_PATHS = listOf(
        "/system/bin/su", "/system/xbin/su", "/sbin/su", "/su/bin/su",
        "/data/local/xbin/su", "/data/local/bin/su", "/system/sd/xbin/su", "/data/adb/magisk",
    )

    fun facts(): DeviceFacts = DeviceFacts(
        fingerprint = Build.FINGERPRINT.orEmpty(),
        hardware = Build.HARDWARE.orEmpty(),
        product = Build.PRODUCT.orEmpty(),
        tags = Build.TAGS.orEmpty(),
        suPathFound = SU_PATHS.any { runCatching { File(it).exists() }.getOrDefault(false) },
        procMaps = runCatching { File("/proc/self/maps").readText() }.getOrDefault(""),
        xposedLoaded = runCatching { Class.forName("de.robv.android.xposed.XposedBridge"); true }.getOrDefault(false),
    )

    fun label(cameraFacing: String): String = "${Build.MANUFACTURER} ${Build.MODEL} · camera $cameraFacing"
}
