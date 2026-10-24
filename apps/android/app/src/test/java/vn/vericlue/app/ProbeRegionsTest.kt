package vn.vericlue.app

import org.junit.Assert.assertEquals
import org.junit.Assert.assertNotEquals
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test
import vn.vericlue.app.capture.Box
import vn.vericlue.app.capture.CamProbeRules
import vn.vericlue.app.capture.DeviceFacts
import vn.vericlue.app.capture.DuplicateFrameMeter
import vn.vericlue.app.capture.Regions

class ProbeRegionsTest {
    private val clean = DeviceFacts(
        fingerprint = "google/oriole/oriole:14/UP1A/1:user/release-keys",
        hardware = "oriole",
        product = "oriole",
        tags = "release-keys",
        suPathFound = false,
        procMaps = "",
        xposedLoaded = false,
    )

    @Test
    fun cleanPhoneHasNoFlags() = assertEquals(emptyList<String>(), CamProbeRules.flags(clean))

    @Test
    fun emulatorRootAndHooksAreFlagged() {
        val f = clean.copy(
            fingerprint = "google/sdk_gphone64_x86_64/emu64x:14/UE1A/1:userdebug/dev-keys",
            hardware = "ranchu",
            tags = "test-keys",
            suPathFound = true,
            procMaps = "7f00 r-xp /data/local/tmp/frida-agent-64.so",
            xposedLoaded = true,
        )
        assertEquals(
            listOf(CamProbeRules.EMULATOR, CamProbeRules.ROOT, CamProbeRules.TEST_KEYS, CamProbeRules.HOOK_FRIDA, CamProbeRules.HOOK_XPOSED),
            CamProbeRules.flags(f),
        )
    }

    @Test
    fun identicalFramesRaiseTheDuplicateRatio() {
        val m = DuplicateFrameMeter()
        assertNull(m.ratio())
        val a = ByteArray(576) { 1 }
        val b = ByteArray(576) { 2 }
        listOf(a, a, b, b, a).forEach(m::add)
        assertEquals(0.5, m.ratio()!!, 1e-9)
    }

    @Test
    fun regionsMeasureTheRightColours() {
        // 100×100 frame: the face box is skin-coloured, everything else blue.
        val face = Box(30f, 30f, 70f, 80f)
        val skin = (200 shl 16) or (150 shl 8) or 120
        val blue = 0x2040C0
        val stats = Regions.measure(face, 100, 100, step = 1) { x, y ->
            if (x in 30 until 70 && y in 30 until 80) skin else blue
        }
        assertEquals(setOf("forehead", "left_cheek", "right_cheek", "nose", "chin", "background"), stats.keys)
        assertEquals(listOf(200, 150, 120), stats["nose"]!!.rgbAll)
        assertEquals(listOf(0x20, 0x40, 0xC0), stats["background"]!!.rgbAll)
        assertTrue(stats["forehead"]!!.pixels > 0)
    }

    @Test
    fun backgroundSquareTouchingTheFaceIsDropped() {
        assertTrue(Regions.backgroundBoxes(Box(5f, 5f, 95f, 95f), 100, 100).isEmpty())
        assertEquals(2, Regions.backgroundBoxes(Box(40f, 40f, 60f, 60f), 100, 100).size)
    }

    @Test
    fun tooDarkPixelsAreTrimmed() {
        val stats = Regions.measure(Box(0f, 0f, 10f, 10f), 10, 10, step = 1) { _, _ -> 0x000000 }
        assertNull(stats["nose"]!!.rgbTrim)
        assertEquals(1.0, stats["nose"]!!.excludedFraction, 1e-9)
    }

    @Test
    fun uprightPixelsMapBackToTheSensor() {
        // Sensor 4×3 rotated 90° clockwise gives an upright 3×4 image.
        assertEquals(0 to 2, Regions.sensorXY(0, 0, 90, 4, 3))
        assertEquals(3 to 0, Regions.sensorXY(2, 3, 90, 4, 3))
        assertEquals(3 to 2, Regions.sensorXY(0, 0, 180, 4, 3))
        assertEquals(3 to 0, Regions.sensorXY(0, 0, 270, 4, 3))
        assertEquals(1 to 2, Regions.sensorXY(1, 2, 0, 4, 3))
    }

    @Test
    fun greyYuvIsGreyRgb() {
        assertEquals((128 shl 16) or (128 shl 8) or 128, Regions.yuvToRgb(128, 128, 128))
        assertNotEquals(Regions.yuvToRgb(128, 128, 128), Regions.yuvToRgb(128, 128, 255))
    }
}
