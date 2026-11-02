package vn.vericlue.app

import java.io.File
import java.io.RandomAccessFile
import java.util.concurrent.CancellationException
import org.junit.Assert.assertEquals
import org.junit.Assert.assertThrows
import org.junit.Rule
import org.junit.Test
import org.junit.rules.TemporaryFolder
import vn.vericlue.app.capture.av.MuxedVoiceAudioDecoder
import vn.vericlue.app.capture.av.MuxedVoiceAudioException

/** JVM tests cover pre-native gates only; MediaCodec proof comes from the device fixture probe. */
class MuxedVoiceAudioDecoderTest {
    @get:Rule val temporary = TemporaryFolder()

    @Test fun missingAndEmptyInputsFailBeforeOpeningAndroidResources() {
        val missing = File(temporary.root, "missing.dat")
        val empty = temporary.newFile("empty.dat")
        for (file in listOf(missing, empty)) {
            assertEquals("invalid_source_file", assertThrows(MuxedVoiceAudioException::class.java) {
                MuxedVoiceAudioDecoder.decode(file)
            }.code)
        }
    }

    @Test fun sourceBeyondThirtyTwoMebibytesFailsBeforeOpeningAndroidResources() {
        val oversized = temporary.newFile("oversized.dat")
        RandomAccessFile(oversized, "rw").use { it.setLength(33_554_433) }
        assertEquals("source_size_limit", assertThrows(MuxedVoiceAudioException::class.java) {
            MuxedVoiceAudioDecoder.decode(oversized)
        }.code)
    }

    @Test fun cancellationPropagatesBeforeFileOrNativeOperations() {
        val missing = File(temporary.root, "missing.dat")
        assertThrows(CancellationException::class.java) {
            MuxedVoiceAudioDecoder.decode(missing, checkCancelled = { throw CancellationException("test cancellation") })
        }
    }
}
