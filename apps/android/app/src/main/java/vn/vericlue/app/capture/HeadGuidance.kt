package vn.vericlue.app.capture

import vn.vericlue.app.flow.TurnDir

/** Bounded engine search: prefer installed offline Vietnamese before network fallback. */
class HeadVoiceSearch {
    private var networkEngine: String? = null
    private var networkPass = false
    fun accept(engine: String?, hasOffline: Boolean, hasNetwork: Boolean): Boolean {
        if (hasOffline) return true
        if (networkPass) return hasNetwork
        if (hasNetwork && networkEngine == null) networkEngine = engine
        return false
    }
    fun fallback(): String? {
        if (networkPass) return null
        networkPass = true
        return networkEngine
    }
}

enum class HeadCue(val text: String, val beeps: List<Long>, val warning: Boolean = false) {
    Left("Quay chậm sang trái", listOf(45)),
    Right("Quay chậm sang phải", listOf(45)),
    Hold("Dừng xoay, giữ yên", listOf(45, 45)),
    Center("Nhìn thẳng", listOf(150)),
    EaseBack("Quay nhẹ lại", listOf(40, 40, 40), true),
    Straighten("Giữ đầu thẳng", listOf(40, 40, 40), true),
    FindFace("Giữ yên, đưa mặt vào khung", listOf(40, 40, 40), true),
    Ready("Tập xong", listOf(110, 110)),
}

class HeadCuePolicy {
    private var phase = Int.MIN_VALUE
    private var observedCue: HeadCue? = null
    private var observedSinceMs = 0L
    private var spokenCue: HeadCue? = null
    private var playingCue: HeadCue? = null
    private var spokenAtMs = 0L
    private var recovering = false
    private val warnings = mutableMapOf<HeadCue, Long>()

    fun dispatch(phase: Int, cue: HeadCue, nowMs: Long, stop: () -> Unit, say: (HeadCue) -> Unit) {
        val phaseChanged = phase != this.phase
        val warningChanged = cue.warning && cue != observedCue
        val replacement = poll(phase, cue, nowMs)
        // A throttled warning still cancels an unsafe Hold. Ordinary jitter must not
        // flush a useful utterance unless a stable replacement will actually play.
        val obsoleteSpeech = warningChanged && playingCue != null && playingCue != cue
        if (phaseChanged || obsoleteSpeech || replacement != null) {
            stop()
            playingCue = null
        }
        replacement?.let {
            say(it)
            playingCue = it
        }
    }

    fun poll(phase: Int, cue: HeadCue, nowMs: Long): HeadCue? {
        val phaseChanged = this.phase != phase
        if (phaseChanged) {
            this.phase = phase
            observedCue = null
            spokenCue = null
            recovering = false
            warnings.clear()
        }
        val changed = cue != observedCue
        if (changed) {
            observedCue = cue
            observedSinceMs = nowMs
        }
        if (cue.warning) {
            recovering = true
            // dispatch cancels the previous cue even when replay is rate-limited.
            if (changed) spokenCue = null
            if (warnings[cue]?.let { nowMs - it < 2500L } == true) return null
            warnings[cue] = nowMs
        } else {
            if (!recovering && cue == spokenCue) return null
            val turn = cue == HeadCue.Left || cue == HeadCue.Right
            val needsStableRecovery = recovering && (turn || cue == HeadCue.Hold)
            if (!phaseChanged && (turn || needsStableRecovery) && nowMs - observedSinceMs < 300L) return null
            if (!phaseChanged && turn && nowMs - spokenAtMs < 1000L) return null
            recovering = false
        }
        spokenCue = cue
        spokenAtMs = nowMs
        return cue
    }
}

fun headCue(dir: TurnDir?, face: FaceSignal?, completed: Boolean, waitingForNext: Boolean = false): HeadCue {
    if (face == null || face.faces != 1 || listOf(face.yaw, face.pitch, face.roll).any { !it.isFinite() }) return HeadCue.FindFace
    if (kotlin.math.abs(face.pitch) > HeadTurnGuide.MAX_TILT_DEG || kotlin.math.abs(face.roll) > HeadTurnGuide.MAX_TILT_DEG) return HeadCue.Straighten
    if (kotlin.math.abs(face.yaw) > HeadTurnGuide.TURN_MAX_SAFE_DEG && dir != null) return HeadCue.EaseBack
    if (HeadTurnGuide.evaluatePose(dir, face, completed) == TurnPoseState.Warn) return HeadCue.FindFace
    if (completed || waitingForNext || dir == null) return HeadCue.Center
    if (HeadTurnGuide.evaluatePose(dir, face) == TurnPoseState.Hold) return HeadCue.Hold
    return if (dir == TurnDir.Left) HeadCue.Left else HeadCue.Right
}

/** Guidance only: a return after one side excursion must not request the same side again. */
class SegmentReturnTracker(private val segmentStartMs: Long) {
    private var sawRequestedSide = false
    private var lastFrameMs: Long? = null
    var waitingForNext = false
        private set

    fun update(dir: TurnDir?, face: FaceSignal?, nowMs: Long) {
        if (waitingForNext || dir == null) return
        val current = HeadTurnGuide.freshFace(face, nowMs, segmentStartMs)
        if (current == null || current.faces != 1 ||
            listOf(current.yaw, current.pitch, current.roll, current.centerX, current.centerY).any { !it.isFinite() } ||
            HeadTurnGuide.evaluatePose(dir, current) == TurnPoseState.Warn) {
            return
        }
        val at = current.timestampNs / 1_000_000L
        val previous = lastFrameMs
        if (previous != null && at <= previous) {
            return
        }
        lastFrameMs = at
        when {
            HeadTurnGuide.evaluatePose(dir, current) == TurnPoseState.Hold -> sawRequestedSide = true
            kotlin.math.abs(current.yaw) <= HeadTurnGuide.CENTER_MAX_DEG && sawRequestedSide -> waitingForNext = true
        }
    }
}

/** Local rehearsal only: this never records, starts an API attempt or decides verification. */
class HeadTurnPractice {
    var step = 0
        private set
    val direction: TurnDir? get() = when (step) { 1 -> TurnDir.Left; 3 -> TurnDir.Right; else -> null }
    val ready: Boolean get() = step == 5
    private var since: Long? = null
    private var previous: Long? = null
    fun update(face: FaceSignal?, nowMs: Long): Boolean {
        if (ready) return false
        val fresh = HeadTurnGuide.freshFace(face, nowMs, 0)
        val at = fresh?.timestampNs?.takeIf { it > 0L }?.div(1_000_000L) ?: nowMs
        if (fresh == null || HeadTurnGuide.evaluatePose(direction, fresh) != TurnPoseState.Hold) {
            since = null; previous = null
            return false
        }
        if (previous?.let { at <= it || at - it > 300L } == true) since = null
        previous = at
        val start = since ?: at.also { since = it }
        val duration = if (direction == null) 500L else HeadTurnGuide.HOLD_COMPLETE_MS
        if (at - start < duration) return false
        step++
        since = null; previous = null
        return true
    }
    fun reset() { step = 0; since = null; previous = null }
}
