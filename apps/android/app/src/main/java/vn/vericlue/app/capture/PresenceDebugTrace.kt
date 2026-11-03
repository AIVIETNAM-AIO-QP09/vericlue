package vn.vericlue.app.capture

import vn.vericlue.app.flow.TurnDir
import kotlinx.serialization.json.*

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
        val frameRelMs: Long? = null,
        val frameAgeMs: Long? = null,
        val faces: Int? = null,
        val segmentIndex: Int = -1,
    ) : PresenceDebugEvent

    data class Guidance(
        override val recordingRelMs: Long,
        val segmentIndex: Int,
        val state: String,
        val completed: Boolean,
        val frameRelMs: Long? = null,
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
    private var lastGuidanceSampleMs: Long = Long.MIN_VALUE
    private var attemptDigest: String? = null

    fun bindAttempt(challengeId: String?) {
        if (!enabled) return
        synchronized(lock) {
            attemptDigest = challengeId?.let { id ->
                java.security.MessageDigest.getInstance("SHA-256").digest(id.toByteArray(Charsets.UTF_8))
                    .joinToString("") { (it.toInt() and 255).toString(16).padStart(2, '0') }
            }
        }
    }

    fun recordFaceSample(
        recordingRelMs: Long,
        yaw: Float?,
        pitch: Float?,
        roll: Float?,
        expectedDirection: TurnDir?,
        holdMs: Long,
        frameRelMs: Long? = null,
        frameAgeMs: Long? = null,
        faces: Int? = null,
        segmentIndex: Int = -1,
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
                frameRelMs = frameRelMs,
                frameAgeMs = frameAgeMs,
                faces = faces,
                segmentIndex = segmentIndex,
            )
            appendLocked(event)
            return event
        }
    }

    /** Record delivery and capture clocks separately; never assign an old frame to the new phase. */
    fun recordAnalyzerFrame(face: FaceSignal?, timeline: FaceTimeline, originMs: Double,
        observedMs: Double): PresenceDebugEvent.FaceSample? {
        if (!enabled || !originMs.isFinite() || !observedMs.isFinite()) return null
        val capturedMs = face?.timestampNs?.takeIf { it > 0L }?.div(1e6)
        val frameRel = capturedMs?.minus(originMs)?.toLong()
        val phase = if (timeline.adaptiveHead) {
            // Adaptive cues use observed boundaries, attributed on capture time.
            frameRel?.let { capturedRel ->
                synchronized(lock) {
                    buffer.filterIsInstance<PresenceDebugEvent.PhaseBoundary>()
                        .lastOrNull { it.recordingRelMs <= capturedRel }
                        ?.takeIf { it.phase == "head" && it.segmentIndex in timeline.headTurns.indices }
                        ?.let { FaceTimeline.Phase.Head(it.segmentIndex, it.direction) }
                }
            }
        } else frameRel?.let { timeline.phaseAt(it.toDouble()) } as? FaceTimeline.Phase.Head
        return recordFaceSample((observedMs - originMs).toLong(), face?.yaw, face?.pitch,
            face?.roll, phase?.dir, 0, frameRel, capturedMs?.let { (observedMs - it).toLong() },
            face?.faces, phase?.segment ?: -1)
    }

    fun recordGuidance(atMs: Long, segmentIndex: Int, state: String,
        completed: Boolean, frameRelMs: Long? = null): PresenceDebugEvent.Guidance? {
        if (!enabled) return null
        synchronized(lock) {
            if (lastGuidanceSampleMs != Long.MIN_VALUE && atMs - lastGuidanceSampleMs < minSampleGapMs) return null
            lastGuidanceSampleMs = atMs
            return PresenceDebugEvent.Guidance(atMs, segmentIndex, state, completed, frameRelMs).also { appendLocked(it) }
        }
    }

    /** Numeric diagnostic only: no session identifiers, media, credentials, or embeddings. */
    fun toJson(): String = buildJsonObject {
        put("schema_version", 1)
        synchronized(lock) { attemptDigest?.let { put("attempt_sha256", it) } }
        put("events", buildJsonArray {
            for (event in snapshot()) add(buildJsonObject {
                put("at_ms", event.recordingRelMs)
                fun number(key: String, value: Float?) {
                    put(key, value?.takeIf { it.isFinite() }?.let { JsonPrimitive(it) } ?: JsonNull)
                }
                when (event) {
                    is PresenceDebugEvent.FaceSample -> {
                        put("kind", "face"); number("yaw", event.yaw); number("pitch", event.pitch); number("roll", event.roll)
                        put("frame_ms", event.frameRelMs?.let { JsonPrimitive(it) } ?: JsonNull)
                        put("age_ms", event.frameAgeMs?.let { JsonPrimitive(it) } ?: JsonNull)
                        put("faces", event.faces?.let { JsonPrimitive(it) } ?: JsonNull)
                        put("segment", event.segmentIndex)
                        put("direction", event.expectedDirection?.name?.let { JsonPrimitive(it) } ?: JsonNull)
                    }
                    is PresenceDebugEvent.GazeTarget -> {
                        put("kind", "dot"); number("x", event.dotX); number("y", event.dotY)
                    }
                    is PresenceDebugEvent.Guidance -> {
                        put("kind", "guidance"); put("segment", event.segmentIndex)
                        put("state", event.state); put("completed", event.completed)
                        put("frame_ms", event.frameRelMs?.let { JsonPrimitive(it) } ?: JsonNull)
                    }
                    is PresenceDebugEvent.PhaseBoundary -> {
                        put("kind", "phase"); put("phase", event.phase); put("segment", event.segmentIndex)
                    }
                }
            })
        })
    }.toString()

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
            lastGuidanceSampleMs = Long.MIN_VALUE
            attemptDigest = null
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
