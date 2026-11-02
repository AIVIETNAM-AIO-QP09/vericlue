package vn.vericlue.app

import kotlinx.serialization.json.Json
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test
import vn.vericlue.app.capture.FaceTimeline
import vn.vericlue.app.capture.FaceTimeline.Phase
import vn.vericlue.app.data.api.CreateSessionResponse
import vn.vericlue.app.data.api.Challenge
import vn.vericlue.app.flow.TurnDir
import java.io.File

/** The FLOW-01 schedule runs on the server's marks, from the recording's first frame. */
class FaceTimelineTest {
    @Test fun offlineTimelineHasAllPhasesAndReturnsToCenter() {
        val order = listOf(vn.vericlue.app.flow.TurnDir.Right, vn.vericlue.app.flow.TurnDir.Left)
        val tl = FaceTimeline.demo(order)
        assertTrue(vn.vericlue.app.capture.ColorSchedule.isSafe(tl.slots))
        assertEquals(8, tl.gaze.size)
        assertEquals(tl.coloursEndMs, tl.gaze.first().atMs)
        assertTrue(tl.gaze.zipWithNext().all { (a, b) -> a.atMs < b.atMs })
        assertTrue(tl.phaseAt(tl.gaze[1].atMs.toDouble()) is Phase.Gaze)
        assertEquals(order + listOf(null), tl.headTurns)
        assertEquals(Phase.Head(2, null), tl.phaseAt(tl.endMs - 1.0))
        assertEquals(Phase.Done, tl.phaseAt(tl.endMs.toDouble()))
    }

    private val json = Json { ignoreUnknownKeys = true }

    /** The contract's own example (packages/contracts/examples), so the app follows the real shape. */
    private fun exampleChallenge(): Challenge {
        val file = generateSequence(File("").absoluteFile) { it.parentFile }
            .map { File(it, "packages/contracts/examples/session.CreateSessionResponse.dynamic.json") }
            .first { it.exists() }
        val res = json.decodeFromString(CreateSessionResponse.serializer(), file.readText())
        return res.challenge
    }

    private fun example(): FaceTimeline = FaceTimeline.from(exampleChallenge()) ?: error("example has no dynamic schedule")

    @Test fun longScheduleHasFourSecondsPerDirectionAndCountdown() {
        for (order in listOf(listOf("left", "right", "center"), listOf("right", "left", "center"))) {
            val ch = exampleChallenge()
            val tl = FaceTimeline.from(ch.copy(dynamic = ch.dynamic!!.copy(headTurns = order)))!!
            val start = tl.headStartMs.toDouble()
            assertEquals(12000, tl.headDurationMs)
            for ((offset, segment) in listOf(0 to 0, 3999 to 0, 4000 to 1, 7999 to 1, 8000 to 2, 11999 to 2)) {
                assertEquals(segment, (tl.phaseAt(start + offset) as Phase.Head).segment)
            }
            assertEquals(Phase.Done, tl.phaseAt(start + 12000))
            assertEquals(4, tl.headRemainingSeconds(start))
            assertEquals(1, tl.headRemainingSeconds(start + 3999))
            assertEquals(4, tl.headRemainingSeconds(start + 4000))
            assertNull(tl.headRemainingSeconds(start - 1))
            assertNull(tl.headRemainingSeconds(start + 12000))
            assertEquals(if (order[1] == "left") TurnDir.Left else TurnDir.Right, tl.nextHeadDirection(start))
            assertNull(tl.nextHeadDirection(start + 4000)) // Next is center, never a fourth segment.
            assertNull(tl.nextHeadDirection(start + 12000))
        }
    }

    @Test fun oldScheduleRemainsTwoSecondsPerDirection() {
        val ch = exampleChallenge()
        val d = ch.dynamic!!
        val tl = FaceTimeline.from(ch.copy(dynamic = d.copy(version = 1, headDurationMs = 6000, voiceStartAtMs = d.headStartAtMs + 6000)))!!
        assertEquals(0, (tl.phaseAt(tl.headStartMs + 1999.0) as Phase.Head).segment)
        assertEquals(1, (tl.phaseAt(tl.headStartMs + 2000.0) as Phase.Head).segment)
    }

    @Test fun invalidServerHeadScheduleCannotBecomeAnOfflineTimeline() {
        val ch = exampleChallenge()
        val d = ch.dynamic!!
        val invalid = listOf(d.copy(version = 1), d.copy(version = 3), d.copy(headDurationMs = 6000),
            d.copy(headStartAtMs = 19000, voiceStartAtMs = 31000), d.copy(voiceStartAtMs = 1),
            d.copy(headTurns = listOf("left", "left", "center")), d.copy(headTurns = listOf("left", "right")))
        invalid.forEach { assertNull(FaceTimeline.from(ch.copy(dynamic = it))) }
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
