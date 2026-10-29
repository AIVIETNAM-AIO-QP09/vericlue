package vn.vericlue.app.capture

import vn.vericlue.app.data.api.Challenge
import vn.vericlue.app.flow.TurnDir

/**
 * The face part as one recording (FLOW-01/LIVE-01, docs/architecture/dynamic-session-api.md):
 * grey baseline → colour steps → dot path → head turns. Every time is in ms from the first frame
 * of that recording (t = 0), exactly as the server scheduled it; the server cuts the video on the
 * same marks to check gaze (LIVE-02) and head turns (FLOW-04), so nothing here is re-timed.
 * Pure Kotlin, unit-tested.
 */
class FaceTimeline(
    /** Baseline slot then the server's steps, back to back from t = 0. */
    val slots: List<ColorSlot>,
    val frontalAtMs: Int,
    val gaze: List<GazeMark>,
    /** Server order, `null` = look straight ahead (the last segment). */
    val headTurns: List<TurnDir?>,
    val headStartMs: Int,
    val headDurationMs: Int,
) {
    data class GazeMark(val x: Double, val y: Double, val atMs: Int)

    sealed interface Phase {
        data class Colour(val slot: Int) : Phase
        /** Between the last colour step and the first dot mark: plain screen, nothing to do. */
        data object Gap : Phase
        data class Gaze(val x: Double, val y: Double) : Phase
        data class Head(val segment: Int, val dir: TurnDir?) : Phase
        data object Done : Phase
    }

    private val slotEnds = slots.runningFold(0) { acc, s -> acc + s.durationMs }.drop(1)
    val coloursEndMs: Int = slotEnds.lastOrNull() ?: 0
    val baselineEndMs: Int = slotEnds.firstOrNull() ?: 0
    val endMs: Int = headStartMs + headDurationMs
    private val segmentMs = if (headTurns.isEmpty()) headDurationMs else headDurationMs / headTurns.size

    fun phaseAt(t: Double): Phase = when {
        t < coloursEndMs -> Phase.Colour(slotEnds.indexOfFirst { t < it })
        gaze.isNotEmpty() && t < gaze.first().atMs -> Phase.Gap
        gaze.isNotEmpty() && t < gaze.last().atMs -> gazeAt(t)
        t < headStartMs -> gaze.lastOrNull()?.let { Phase.Gaze(it.x, it.y) } ?: Phase.Gap
        t < endMs -> ((t - headStartMs) / segmentMs).toInt().coerceIn(0, headTurns.lastIndex.coerceAtLeast(0))
            .let { Phase.Head(it, headTurns.getOrNull(it)) }
        else -> Phase.Done
    }

    /** Straight, even movement between marks, arriving on each mark's time. */
    private fun gazeAt(t: Double): Phase.Gaze {
        val i = gaze.indexOfLast { it.atMs <= t }.coerceAtLeast(0)
        val a = gaze[i]
        val b = gaze.getOrNull(i + 1) ?: return Phase.Gaze(a.x, a.y)
        val f = ((t - a.atMs) / (b.atMs - a.atMs)).coerceIn(0.0, 1.0)
        return Phase.Gaze(a.x + (b.x - a.x) * f, a.y + (b.y - a.y) * f)
    }

    companion object {
        /** Offline preview only. Never used to replace a missing/invalid server challenge. */
        fun demo(order: List<TurnDir>): FaceTimeline {
            val slots = ColorSchedule.demo().dropLast(1)
            val start = slots.sumOf { it.durationMs }
            val random = kotlin.random.Random.Default
            val marks = List(8) { i ->
                GazeMark(random.nextDouble(0.15, 0.85), random.nextDouble(0.3, 0.7), start + i * 850)
            }
            return FaceTimeline(slots, 500, marks, order + listOf(null),
                marks.last().atMs, (order.size + 1) * 2000)
        }

        /**
         * Re-auth (FLOW-01): the server sends no schedule and wants passive capture only: no colour,
         * dot or head turn. A short steady recording with the frontal still at 0.5 s.
         */
        fun passive(): FaceTimeline = FaceTimeline(
            slots = listOf(ColorSlot(null, "#ffffff", 3000)),
            frontalAtMs = 500,
            gaze = emptyList(),
            headTurns = emptyList(),
            headStartMs = 3000,
            headDurationMs = 0,
        )

        /** The live schedule, or null when the challenge has no `dynamic` pack (MVP / re-auth). */
        fun from(challenge: Challenge): FaceTimeline? {
            val d = challenge.dynamic ?: return null
            val turns = d.headTurns.map {
                when (it) {
                    "left" -> TurnDir.Left
                    "right" -> TurnDir.Right
                    "center" -> null
                    else -> return null
                }
            }
            if (d.gazePoints.size < 2 || turns.isEmpty()) return null
            return FaceTimeline(
                slots = ColorSchedule.from(challenge).dropLast(1), // no grey tail: the dot starts right after
                frontalAtMs = d.frontalCaptureAtMs,
                gaze = d.gazePoints.map { GazeMark(it.x, it.y, it.atMs) },
                headTurns = turns,
                headStartMs = d.headStartAtMs,
                headDurationMs = d.headDurationMs,
            )
        }
    }
}
