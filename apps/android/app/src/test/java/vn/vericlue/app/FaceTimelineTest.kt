package vn.vericlue.app

import kotlinx.serialization.json.Json
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test
import vn.vericlue.app.capture.FaceTimeline
import vn.vericlue.app.capture.FaceTimeline.Phase
import vn.vericlue.app.data.api.CreateSessionResponse
import java.io.File

/** The FLOW-01 schedule runs on the server's marks, from the recording's first frame. */
class FaceTimelineTest {
    private val json = Json { ignoreUnknownKeys = true }

    /** The contract's own example (packages/contracts/examples), so the app follows the real shape. */
    private fun example(): FaceTimeline {
        val file = generateSequence(File("").absoluteFile) { it.parentFile }
            .map { File(it, "packages/contracts/examples/session.CreateSessionResponse.dynamic.json") }
            .first { it.exists() }
        val res = json.decodeFromString(CreateSessionResponse.serializer(), file.readText())
        return FaceTimeline.from(res.challenge) ?: error("example has no dynamic schedule")
    }

    @Test
    fun phasesFollowTheServerMarks() {
        val tl = example()
        assertEquals(Phase.Colour(0), tl.phaseAt(0.0))
        assertTrue(tl.phaseAt(tl.baselineEndMs + 1.0) is Phase.Colour)
        val first = tl.gaze.first()
        assertEquals(Phase.Gaze(first.x, first.y), tl.phaseAt(first.atMs.toDouble()))
        assertEquals(0, (tl.phaseAt(tl.headStartMs + 10.0) as Phase.Head).segment)
        assertEquals(Phase.Done, tl.phaseAt(tl.endMs.toDouble()))
    }

    @Test
    fun coloursEndWhereTheDotStarts() {
        val tl = example()
        // No grey tail: the server's dot starts right after the last colour step.
        assertEquals(tl.gaze.first().atMs, tl.coloursEndMs)
    }

    @Test
    fun dotMovesInAStraightLineBetweenMarks() {
        val tl = example()
        val a = tl.gaze[1]
        val b = tl.gaze[2]
        val mid = tl.phaseAt((a.atMs + b.atMs) / 2.0) as Phase.Gaze
        assertEquals((a.x + b.x) / 2, mid.x, 1e-9)
        assertEquals((a.y + b.y) / 2, mid.y, 1e-9)
    }

    @Test
    fun headTurnsKeepTheServerOrderAndEndLookingAhead() {
        val tl = example()
        val seg = tl.headDurationMs / tl.headTurns.size
        val seen = (0 until tl.headTurns.size).map { (tl.phaseAt(tl.headStartMs + it * seg + 10.0) as Phase.Head).dir }
        assertEquals(tl.headTurns, seen)
        assertNull(seen.last())
    }

    @Test
    fun passiveCaptureHasNoColourDotOrTurn() {
        val tl = FaceTimeline.passive()
        assertEquals(Phase.Colour(0), tl.phaseAt(100.0))
        assertEquals(Phase.Done, tl.phaseAt(3000.0))
        assertTrue(tl.gaze.isEmpty() && tl.headTurns.isEmpty())
    }
}
