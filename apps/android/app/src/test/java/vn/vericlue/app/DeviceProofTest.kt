package vn.vericlue.app

import java.security.KeyPairGenerator
import java.security.Signature
import java.security.spec.ECGenParameterSpec
import java.time.Instant
import java.util.Base64
import kotlinx.coroutines.test.runTest
import kotlinx.serialization.json.Json
import kotlinx.serialization.json.buildJsonObject
import kotlinx.serialization.json.jsonObject
import kotlinx.serialization.json.jsonPrimitive
import kotlinx.serialization.json.put
import okhttp3.mockwebserver.MockResponse
import okhttp3.mockwebserver.MockWebServer
import org.junit.Assert.*
import org.junit.Test
import vn.vericlue.app.data.api.*
import vn.vericlue.app.flow.LiveFlow
import vn.vericlue.app.security.DeviceProof
import vn.vericlue.app.security.MediaSigner

class DeviceProofTest {
    private val account = AccountReceipt("acct_" + "a".repeat(32), "dev_" + "b".repeat(32), "2030-01-01T00:00:00Z")
    private val now = Instant.parse("2026-10-26T00:00:00Z")

    private fun response(nonce: String, contextAccount: String = account.accountId, expiry: Instant = now.plusSeconds(60)): CreateSessionResponse {
        val payload = buildJsonObject {
            put("version", "vericlue-device-auth-v1"); put("session_id", "ses_test")
            put("account_id", contextAccount); put("device_id", account.deviceId)
            put("purpose", "reauth"); put("nonce", nonce)
            put("server_nonce", "c".repeat(64)); put("expires_at_ms", expiry.toEpochMilli())
        }.toString().toByteArray(Charsets.US_ASCII)
        return CreateSessionResponse("ses_test", "token", account.expiresAt,
            Challenge("ch_test", colorSequence = emptyList(), mediaNonce = "d".repeat(64)), "reauth", nonce,
            DeviceChallenge(Base64.getEncoder().encodeToString(payload), Instant.ofEpochMilli(expiry.toEpochMilli()).toString()))
    }

    @Test fun validatesContextButSignsExactServerBytes() {
        val session = response("synthetic_nonce_123456")
        assertArrayEquals(Base64.getDecoder().decode(session.deviceChallenge!!.message),
            DeviceProof.payload(session, account, session.nonce!!, now))
        for (bad in listOf(response("wrong_nonce_12345678"), response(session.nonce!!, "acct_other"),
            response(session.nonce!!, expiry = now))) {
            assertTrue(runCatching { DeviceProof.payload(bad, account, session.nonce!!, now) }.isFailure)
        }
    }

    @Test fun liveFlowProvesRegisteredKeyBeforePublishingSession() = runTest {
        val pair = KeyPairGenerator.getInstance("EC").run {
            initialize(ECGenParameterSpec("secp256r1")); generateKeyPair()
        }
        val signer = object : MediaSigner {
            override val publicKeySpki: String get() = error("Reauth must not submit a new key")
            override fun sign(canonicalManifest: ByteArray): String = Base64.getEncoder().encodeToString(
                Signature.getInstance("SHA256withECDSA").run {
                    initSign(pair.private); update(canonicalManifest); sign()
                })
        }
        val server = MockWebServer().apply { start() }
        try {
            var expected: CreateSessionResponse? = null
            server.dispatcher = object : okhttp3.mockwebserver.Dispatcher() {
                override fun dispatch(request: okhttp3.mockwebserver.RecordedRequest): MockResponse {
                    if (request.path == "/v1/sessions") {
                        val body = Json.parseToJsonElement(request.body.readUtf8()).jsonObject
                        assertFalse(body.containsKey("device_public_key_spki"))
                        assertEquals(account.accountId, body["account_id"]!!.jsonPrimitive.content)
                        expected = response(body["nonce"]!!.jsonPrimitive.content, expiry = Instant.now().plusSeconds(60))
                        return MockResponse().setBody(Json.encodeToString(CreateSessionResponse.serializer(), expected!!))
                    }
                    assertEquals("/v1/sessions/ses_test/device-proof", request.path)
                    assertEquals("Bearer token", request.getHeader("Authorization"))
                    val signature = Json.parseToJsonElement(request.body.readUtf8()).jsonObject["signature"]!!.jsonPrimitive.content
                    assertTrue(Signature.getInstance("SHA256withECDSA").run {
                        initVerify(pair.public); update(Base64.getDecoder().decode(expected!!.deviceChallenge!!.message))
                        verify(Base64.getDecoder().decode(signature))
                    })
                    return MockResponse().setBody("""{"received":true}""")
                }
            }
            val flow = LiveFlow(SessionApi(server.url("/").toString()), signer)
            assertNull(flow.ensureSession(null, "reauth", account))
            assertEquals("ses_test", flow.session!!.sessionId)
        } finally { server.shutdown() }
    }

    @Test fun rejectedProofDoesNotLeaveUsableSession() = runTest {
        val server = MockWebServer().apply { start() }
        val signer = object : MediaSigner {
            override val publicKeySpki = "unused"
            override fun sign(canonicalManifest: ByteArray) = "synthetic-signature"
        }
        try {
            server.dispatcher = object : okhttp3.mockwebserver.Dispatcher() {
                override fun dispatch(request: okhttp3.mockwebserver.RecordedRequest): MockResponse {
                    if (request.path == "/v1/sessions") {
                        val nonce = Json.parseToJsonElement(request.body.readUtf8()).jsonObject["nonce"]!!.jsonPrimitive.content
                        return MockResponse().setBody(Json.encodeToString(CreateSessionResponse.serializer(),
                            response(nonce, expiry = Instant.now().plusSeconds(60))))
                    }
                    return MockResponse().setResponseCode(409).setBody("""{"error_code":"recovery_required","message":"retry"}""")
                }
            }
            val flow = LiveFlow(SessionApi(server.url("/").toString()), signer)
            assertEquals(ApiError.RecoveryRequired, flow.ensureSession(null, "reauth", account))
            assertNull(flow.session)
        } finally { server.shutdown() }
    }
}
