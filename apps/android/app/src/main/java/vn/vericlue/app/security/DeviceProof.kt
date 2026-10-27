package vn.vericlue.app.security

import java.time.Instant
import java.util.Base64
import kotlinx.serialization.json.Json
import kotlinx.serialization.json.jsonObject
import kotlinx.serialization.json.jsonPrimitive
import kotlinx.serialization.json.long
import vn.vericlue.app.data.api.AccountReceipt
import vn.vericlue.app.data.api.CreateSessionResponse

/** L0 proves a registered P-256 key, not FIDO2, camera origin or biometric acceptance. */
object DeviceProof {
    fun payload(session: CreateSessionResponse, account: AccountReceipt, nonce: String, now: Instant = Instant.now()): ByteArray {
        val challenge = requireNotNull(session.deviceChallenge)
        require(challenge.message.length <= 2048)
        val bytes = Base64.getDecoder().decode(challenge.message)
        require(bytes.all { it.toInt() in 32..126 })
        require(Base64.getEncoder().encodeToString(bytes) == challenge.message)
        val fields = Json.parseToJsonElement(bytes.toString(Charsets.US_ASCII)).jsonObject
        require(fields.keys == setOf("version", "session_id", "account_id", "device_id", "purpose", "nonce", "server_nonce", "expires_at_ms"))
        fun text(name: String) = fields.getValue(name).jsonPrimitive.content
        require(text("version") == "vericlue-device-auth-v1" && text("purpose") == "reauth")
        require(text("session_id") == session.sessionId && text("account_id") == account.accountId)
        require(text("device_id") == account.deviceId && text("nonce") == nonce && session.nonce == nonce)
        require(text("server_nonce").matches(Regex("[0-9a-f]{64}")))
        val expiry = Instant.ofEpochMilli(fields.getValue("expires_at_ms").jsonPrimitive.long)
        require(expiry == Instant.parse(challenge.expiresAt) && expiry > now)
        require(expiry <= Instant.parse(session.expiresAt) && expiry <= Instant.parse(account.expiresAt))
        return bytes // Sign the exact server bytes; do not re-encode JSON.
    }
}
