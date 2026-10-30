package vn.vericlue.app.capture

import vn.vericlue.app.flow.TurnDir

typealias HeadTurnDirection = TurnDir

sealed interface PresenceDebugEvent {
    val recordingRelMs: Long

    data class FaceSample(
        override val recordingRelMs: Long,
        val yaw: Float?,
        val pitch: Float?,
        val roll: Float?,
        val expectedDirection: TurnDir?,
        val holdMs: Long,
    ) : PresenceDebugEvent

    data class GazeTarget(
        override val recordingRelMs: Long,
        val dotX: Float,
        val dotY: Float,
    ) : PresenceDebugEvent

    data class PhaseBoundary(
        override val recordingRelMs: Long,
        val phase: String,
        val segmentIndex: Int = -1,
        val direction: TurnDir? = null,
    ) : PresenceDebugEvent
}

class PresenceDebugTrace(
    val enabled: Boolean = false,
    private val maxSamples: Int = 1024,
    private val minSampleGapMs: Long = 100L,
) {
    private val lock = Any()
    private val buffer = ArrayDeque<PresenceDebugEvent>()
    private var lastFaceSampleMs: Long = Long.MIN_VALUE
    private var lastGazeSampleMs: Long = Long.MIN_VALUE

    fun recordFaceSample(
        recordingRelMs: Long,
        yaw: Float?,
        pitch: Float?,
        roll: Float?,
        expectedDirection: TurnDir?,
        holdMs: Long,
    ): PresenceDebugEvent.FaceSample? {
        if (!enabled) return null
        synchronized(lock) {
            if (minSampleGapMs > 0L && lastFaceSampleMs != Long.MIN_VALUE &&
                recordingRelMs - lastFaceSampleMs < minSampleGapMs
            ) {
                return null
            }
            lastFaceSampleMs = recordingRelMs
            val event = PresenceDebugEvent.FaceSample(
                recordingRelMs = recordingRelMs,
                yaw = yaw,
                pitch = pitch,
                roll = roll,
                expectedDirection = expectedDirection,
                holdMs = holdMs,
            )
            appendLocked(event)
            return event
        }
    }

    fun recordFaceSampleForWindow(
        recordingRelMs: Long,
        windowStartRelMs: Long,
        windowEndRelMs: Long,
        yaw: Float?,
        pitch: Float?,
        roll: Float?,
        expectedDirection: TurnDir?,
        holdMs: Long,
    ): PresenceDebugEvent.FaceSample? {
        if (!enabled) return null
        if (recordingRelMs < windowStartRelMs || recordingRelMs >= windowEndRelMs) {
            return null
        }
        return recordFaceSample(
            recordingRelMs = recordingRelMs,
            yaw = yaw,
            pitch = pitch,
            roll = roll,
            expectedDirection = expectedDirection,
            holdMs = holdMs,
        )
    }

    fun recordGazeTarget(
        recordingRelMs: Long,
        dotX: Float,
        dotY: Float,
    ): PresenceDebugEvent.GazeTarget? {
        if (!enabled) return null
        synchronized(lock) {
            if (minSampleGapMs > 0L && lastGazeSampleMs != Long.MIN_VALUE &&
                recordingRelMs - lastGazeSampleMs < minSampleGapMs
            ) {
                return null
            }
            lastGazeSampleMs = recordingRelMs
            val event = PresenceDebugEvent.GazeTarget(
                recordingRelMs = recordingRelMs,
                dotX = dotX,
                dotY = dotY,
            )
            appendLocked(event)
            return event
        }
    }

    fun recordPhaseBoundary(
        recordingRelMs: Long,
        phase: String,
        segmentIndex: Int = -1,
        direction: TurnDir? = null,
    ): PresenceDebugEvent.PhaseBoundary? {
        if (!enabled) return null
        synchronized(lock) {
            val event = PresenceDebugEvent.PhaseBoundary(
                recordingRelMs = recordingRelMs,
                phase = phase,
                segmentIndex = segmentIndex,
                direction = direction,
            )
            appendLocked(event)
            return event
        }
    }

    fun snapshot(): List<PresenceDebugEvent> = synchronized(lock) {
        buffer.toList()
    }

    fun clear() {
        synchronized(lock) {
            buffer.clear()
            lastFaceSampleMs = Long.MIN_VALUE
            lastGazeSampleMs = Long.MIN_VALUE
        }
    }

    private fun appendLocked(event: PresenceDebugEvent) {
        if (maxSamples <= 0) return
        while (buffer.size >= maxSamples) {
            buffer.removeFirst()
        }
        buffer.addLast(event)
    }
}
