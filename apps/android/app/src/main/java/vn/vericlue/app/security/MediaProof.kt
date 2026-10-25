package vn.vericlue.app.security

import java.io.File
import java.security.MessageDigest
import java.util.Locale
import kotlinx.serialization.json.JsonNull
import kotlinx.serialization.json.buildJsonObject
import kotlinx.serialization.json.put
import vn.vericlue.app.data.api.Challenge
import vn.vericlue.app.data.api.CreateSessionResponse

/** Keys stay in the signer; this layer only handles public keys and signature bytes. */
interface MediaSigner {
    val publicKeySpki: String
    fun sign(canonicalManifest: ByteArray): String
}

/** Fixed ASCII context and sorted JSON keys, shared with services/media_proof.py. */
object MediaProof {
    private const val MAX_BYTES = 64L * 1024 * 1024
    private val suffixes = setOf(".jpg", ".jpeg", ".png", ".webp", ".mp4", ".webm", ".mov", ".wav", ".mp3", ".m4a", ".ogg")

    data class FileDigest(val sha256: String, val size: Long, val suffix: String)

    private fun hex(bytes: ByteArray) = bytes.joinToString("") { "%02x".format(it.toInt() and 255) }
    private fun sha(bytes: ByteArray) = hex(MessageDigest.getInstance("SHA-256").digest(bytes))
    private fun suffix(name: String): String {
        val value = "." + name.substringAfterLast('.', "").lowercase(Locale.ROOT)
        return if (value in suffixes) value else ".bin"
    }

    fun digest(name: String, bytes: ByteArray): FileDigest {
        require(bytes.isNotEmpty() && bytes.size.toLong() <= MAX_BYTES)
        return FileDigest(sha(bytes), bytes.size.toLong(), suffix(name))
    }

    fun digest(file: File): FileDigest {
        val hash = MessageDigest.getInstance("SHA-256")
        var count = 0L
        file.inputStream().use { input ->
            val buffer = ByteArray(65536)
            while (true) {
                val read = input.read(buffer)
                if (read < 0) break
                count += read
                require(count <= MAX_BYTES)
                hash.update(buffer, 0, read)
            }
        }
        require(count > 0)
        return FileDigest(hex(hash.digest()), count, suffix(file.name))
    }

    fun manifest(
        session: CreateSessionResponse, challenge: Challenge, stage: String,
        attemptId: String, files: Map<String, FileDigest>, audioOffsetMs: Int? = null,
    ): ByteArray {
        val seed = requireNotNull(challenge.mediaNonce)
        require(seed.matches(Regex("[0-9a-f]{64}")))
        require(listOf(session.sessionId, challenge.challengeId, attemptId, session.nonce ?: "").all {
            it.matches(Regex("[A-Za-z0-9_-]+"))
        })
        require(session.purpose in setOf("onboarding", "recovery"))
        val allowed = if (stage == "face") setOf("image", "video") else setOf("audio", "video")
        require(stage in setOf("face", "voice") && files.keys.all { it in allowed })
        require((if (stage == "face") "image" else "audio") in files)
        require(audioOffsetMs == null || (stage == "voice" && "video" in files && audioOffsetMs in -5000..5000))
        val nonce = sha("$seed:$stage:$attemptId".toByteArray(Charsets.US_ASCII))
        return buildJsonObject {
            put("attempt_id", attemptId)
            if (audioOffsetMs == null) put("audio_offset_ms", JsonNull) else put("audio_offset_ms", audioOffsetMs)
            put("challenge_id", challenge.challengeId)
            put("client_nonce", requireNotNull(session.nonce))
            put("files", buildJsonObject {
                files.toSortedMap().forEach { (role, file) ->
                    require(file.sha256.matches(Regex("[0-9a-f]{64}")) && file.size in 1..MAX_BYTES && file.suffix in suffixes + ".bin")
                    put(role, buildJsonObject {
                        put("sha256", file.sha256)
                        put("size", file.size)
                        put("suffix", file.suffix)
                    })
                }
            })
            put("nonce", nonce)
            put("protocol", "vericlue-media-v1")
            put("purpose", requireNotNull(session.purpose))
            put("session_id", session.sessionId)
            put("stage", stage)
        }.toString().toByteArray(Charsets.US_ASCII)
    }
}
