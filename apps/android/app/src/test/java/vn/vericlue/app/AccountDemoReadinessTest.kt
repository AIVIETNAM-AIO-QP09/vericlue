package vn.vericlue.app

import java.security.KeyPairGenerator
import java.security.Signature
import java.security.spec.ECGenParameterSpec
import java.time.Instant
import java.util.Base64
import kotlinx.coroutines.test.runTest
import kotlinx.serialization.json.Json
import kotlinx.serialization.json.jsonObject
import kotlinx.serialization.json.jsonPrimitive
import okhttp3.mockwebserver.MockResponse
import okhttp3.mockwebserver.MockWebServer
import org.junit.Assert.*
import org.junit.Test
import vn.vericlue.app.data.AccountStore
import vn.vericlue.app.data.StoredAccount
import vn.vericlue.app.data.KeyValueStore
import vn.vericlue.app.data.api.AccountReceipt
import vn.vericlue.app.data.api.ApiError
import vn.vericlue.app.data.api.SessionApi
import vn.vericlue.app.flow.*
import vn.vericlue.app.security.AccountKeys
import vn.vericlue.app.security.MediaSigner
import vn.vericlue.app.ui.FlowState

/** Synthetic HTTP fixtures verify flow guards, not model accuracy or phone readiness. */
class AccountDemoReadinessTest {
    private class Memory : KeyValueStore {
        val values = mutableMapOf<String, String>()
        var failWrite = false
        override fun get(key: String) = values[key]
        override fun put(key: String, value: String) {
            check(!failWrite) { "synthetic write failure" }
            values[key] = value
        }
        override fun remove(key: String) { values.remove(key) }
    }

    private class Signer : MediaSigner {
        private val pair = KeyPairGenerator.getInstance("EC").run {
            initialize(ECGenParameterSpec("secp256r1")); generateKeyPair()
        }
        override val publicKeySpki = Base64.getEncoder().encodeToString(pair.public.encoded)
        override fun sign(canonicalManifest: ByteArray): String = Base64.getEncoder().encodeToString(
            Signature.getInstance("SHA256withECDSA").run {
                initSign(pair.private); update(canonicalManifest); sign()
            })
    }

    private class Keys : AccountKeys {
        val entries = mutableMapOf<String, MediaSigner>()
        val deleted = mutableListOf<String>()
        override fun exists(alias: String) = entries.containsKey(alias)
        override fun open(alias: String, create: Boolean): MediaSigner {
            if (create) entries.getOrPut(alias) { Signer() }
            return requireNotNull(entries[alias])
        }
        override fun delete(alias: String) { deleted += alias; entries.remove(alias) }
    }

    private val policy = "a".repeat(64)
    private val receipt = AccountReceipt("acc_old", "dev_old", "2030-01-01T00:00:00Z")
    private val oldAlias = "vericlue.media.old"
    private val newAlias = "vericlue.media.new"
    private val now = Instant.parse("2026-11-01T00:00:00Z")

    @Test fun freshFlowUsesTheConfiguredApiDefault() {
        assertEquals(BuildConfig.LIVE_API_DEFAULT, FlowState().live)
    }

    @Test fun legacyMetadataCannotBeGuessedDuringLoginOrRecovery() {
        for (purpose in listOf(Purpose.Reauth, Purpose.Recovery)) {
            val memory = Memory()
            val store = AccountStore(memory) { now }.apply { save(receipt, oldAlias) }
            val raw = memory.values.toMap()
            val keys = Keys().apply { entries[oldAlias] = Signer() }
            val entry = AccountFlow(store, keys, true, newAlias = { newAlias }).begin(purpose)
            assertEquals(purpose, entry.purpose)
            assertEquals(Routes.ErrorService, entry.route)
            assertFalse(entry.hint.isNullOrBlank())
            assertEquals(raw, memory.values)
            assertEquals(setOf(oldAlias), keys.entries.keys)
            assertTrue(keys.deleted.isEmpty())
        }
    }

    @Test fun inspectingExpiredOrUnreadableStorageNeverDeletesTheOriginalBinding() {
        for (raw in listOf("{not json", """{"receipt":{"account_id":"acc_old","device_id":"dev_old","expires_at":"2020-01-01T00:00:00Z"},"keyAlias":"$oldAlias"}""")) {
            val memory = Memory().apply {
                values["account_binding.v2"] = raw
                values["account_receipt.v1"] = "legacy receipt without alias"
            }
            assertNull(AccountStore(memory) { now }.load())
            assertEquals(raw, memory.values["account_binding.v2"])
            assertEquals("legacy receipt without alias", memory.values["account_receipt.v1"])
        }
    }

    @Test fun restoredDemoBindingRetainsItsModePolicyAndEntryContext() {
        val memory = Memory()
        AccountStore(memory) { now }.save(receipt, oldAlias, "manual_full_demo", policy)
        val restored = AccountStore(memory) { now }.load()!!
        assertTrue(restored.manualFullDemo)
        assertEquals("manual_full_demo", restored.evaluationMode)
        assertEquals(policy, restored.demoPolicyId)
        val keys = Keys().apply { entries[oldAlias] = Signer() }
        for (purpose in listOf(Purpose.Reauth, Purpose.Recovery)) {
            val entry = AccountFlow(AccountStore(memory) { now }, keys, true, newAlias = { newAlias }).begin(purpose)
            assertEquals(Routes.Terms, entry.route)
            assertEquals(restored, entry.previous)
        }
    }

    @Test fun newDemoRegistrationBacksUpTheOldBindingInTheSameRecord() {
        val memory = Memory()
        val store = AccountStore(memory) { now }
        store.save(receipt, oldAlias)
        store.save(receipt.copy(accountId = "acc_demo", deviceId = "dev_demo"), newAlias,
            "manual_full_demo", policy, preserveExisting = true)
        val restored = AccountStore(memory) { now }.load()!!
        assertEquals("acc_demo", restored.receipt.accountId)
        assertEquals(receipt, restored.previousBindings.single().receipt)
        assertEquals(oldAlias, restored.previousBindings.single().keyAlias)
        assertNull(restored.previousBindings.single().evaluationMode)
    }

    @Test fun failedReplacementWritePreservesTheExactOldBinding() {
        val memory = Memory()
        val store = AccountStore(memory) { now }
        store.save(receipt, oldAlias, "manual_full_demo", policy)
        val original = memory.values.toMap()
        memory.failWrite = true
        assertTrue(runCatching {
            store.save(receipt.copy(deviceId = "dev_new"), newAlias, "manual_full_demo", policy)
        }.isFailure)
        assertEquals(original, memory.values)
        assertEquals(oldAlias, store.load()!!.keyAlias)
    }

    @Test fun manualRecoveryPersistsPolicyBeforeRetiringTheOldKey() = runTest {
        recoveryFinish(writeFails = false)
    }

    @Test fun manualRecoveryWriteFailureKeepsTheOldReceiptKeyAndPolicy() = runTest {
        recoveryFinish(writeFails = true)
    }

    private suspend fun recoveryFinish(writeFails: Boolean) = withServer { server ->
        val memory = Memory()
        val store = AccountStore(memory) { now }.apply { save(receipt, oldAlias, "manual_full_demo", policy) }
        val keys = Keys().apply { entries[oldAlias] = Signer() }
        val accounts = AccountFlow(store, keys, true, newAlias = { newAlias })
        val entry = accounts.begin(Purpose.Recovery)
        val live = LiveFlow(SessionApi(server.url("/").toString()), entry.signer)
        live.bindAccount(entry.previous)
        server.enqueue(json(session("recovery")))
        assertNull(live.ensureSession(null, "recovery"))
        challengeVoice(server, live)
        server.enqueue(json("""{"status":"pass","evaluation_mode":"manual_full_demo","demo_policy_id":"$policy","account":{"account_id":"acc_old","device_id":"dev_new","expires_at":"2030-01-01T00:00:00Z"}}"""))
        val next = live.submitVoice(byteArrayOf(2))
        memory.failWrite = writeFails
        assertEquals(Next.To(Routes.Success), accounts.finish(entry, live, next))
        assertEquals(!writeFails, accounts.accountSaved)
        assertEquals(if (writeFails) oldAlias else newAlias, store.load()!!.keyAlias)
        assertEquals(if (writeFails) receipt else receipt.copy(deviceId = "dev_new"), store.load()!!.receipt)
        assertEquals(policy, store.load()!!.demoPolicyId)
        assertEquals(if (writeFails) emptyList<String>() else listOf(oldAlias), keys.deleted)
    }

    @Test fun receiptContextMismatchDoesNotReplaceAccountOrDeleteKey() = runTest {
        withServer { server ->
            val memory = Memory()
            val store = AccountStore(memory) { now }.apply { save(receipt, oldAlias, "manual_full_demo", policy) }
            val original = memory.values.toMap()
            val keys = Keys().apply { entries[oldAlias] = Signer() }
            val accounts = AccountFlow(store, keys, true, newAlias = { newAlias })
            val entry = accounts.begin(Purpose.Recovery)
            val live = LiveFlow(SessionApi(server.url("/").toString()), entry.signer)
            live.bindAccount(entry.previous)
            server.enqueue(json(session("recovery")))
            assertNull(live.ensureSession(null, "recovery"))
            challengeVoice(server, live)
            server.enqueue(json("""{"status":"pass","evaluation_mode":"manual_full_demo","demo_policy_id":"$policy","account":{"account_id":"acc_unrelated","device_id":"dev_new","expires_at":"2030-01-01T00:00:00Z"}}"""))
            val next = live.submitVoice(byteArrayOf(2))
            assertEquals(Next.Fail(ApiError.BadResponse), accounts.finish(entry, live, next))
            assertEquals(original, memory.values)
            assertTrue(keys.deleted.isEmpty())
            assertFalse(accounts.accountSaved)
        }
    }

    @Test fun accountSessionsRejectChangedModePolicyAndUnknownMetadataBeforeDeviceProof() = runTest {
        for (purpose in listOf("reauth", "recovery")) {
            for ((savedMode, savedPolicy, mode, responsePolicy) in listOf(
                listOf("manual_full_demo", policy, "standard", null),
                listOf("standard", null, "manual_full_demo", policy),
                listOf("manual_full_demo", policy, "manual_full_demo", "b".repeat(64)),
                listOf(null, null, "manual_full_demo", policy),
            )) {
                withServer { server ->
                    val live = LiveFlow(SessionApi(server.url("/").toString()), Signer())
                    live.bindAccount(StoredAccount(receipt, oldAlias, savedMode, savedPolicy))
                    server.enqueue(json(session(purpose, mode!!, responsePolicy)))
                    assertEquals(ApiError.BadResponse, live.ensureSession(null, purpose))
                    assertNull(live.session)
                    assertTrue(server.requestCount <= 1) // No proof signed for the wrong mode/policy.
                }
            }
        }
    }

    @Test fun voiceRejectsChangedPolicyAndServerFailuresForAllThreePurposes() = runTest {
        for (purpose in listOf("onboarding", "reauth", "recovery")) {
            for (reply in listOf(
                json("""{"status":"pass","evaluation_mode":"manual_full_demo","demo_policy_id":"${"b".repeat(64)}"}"""),
                json("""{"status":"pass"}"""),
                json("""{"error_code":"inference_failed","message":"retry"}""", 500),
            )) {
                withServer { server ->
                    val live = started(server, purpose)
                    challengeVoice(server, live)
                    server.enqueue(reply)
                    assertTrue(live.submitVoice(byteArrayOf(2)) is Next.Fail)
                    assertFalse(live.voiceChecked)
                    assertNull(live.accountReceipt)
                }
            }
        }
    }

    @Test fun matchingDemoModeAndPolicyCanCompleteAllThreePurposes() = runTest {
        for (purpose in listOf("onboarding", "reauth", "recovery")) {
            withServer { server ->
                val live = started(server, purpose)
                challengeVoice(server, live)
                server.enqueue(json("""{"status":"pass","evaluation_mode":"manual_full_demo","demo_policy_id":"$policy"}"""))
                assertEquals(Next.To(Routes.Success), live.submitVoice(byteArrayOf(2)))
                assertTrue(live.manualFullDemo)
                assertTrue(live.voiceChecked)
            }
        }
    }

    @Test fun finalizeServerErrorNeverUsesTheOfflinePassOutcome() = runTest {
        withServer { server ->
            val live = started(server, "onboarding")
            live.frontalJpeg = byteArrayOf(1)
            server.enqueue(json("""{"step":"media","received":true}"""))
            server.enqueue(json("""{"step":"signals","received":true}"""))
            server.enqueue(json("""{"error_code":"inference_failed","message":"retry"}""", 500))
            assertEquals(Next.Fail(ApiError.Server), live.submitFace(null, emptyList(), emptyMap()))
            assertEquals(Routes.ErrorService, errorRoute(ApiError.Server))
        }
    }

    @Test fun finalizeRejectsChangedModeAndPolicyForAllThreePurposes() = runTest {
        for (purpose in listOf("onboarding", "reauth", "recovery")) {
            for (response in listOf(
                """{"status":"pass"}""",
                """{"status":"pass","evaluation_mode":"manual_full_demo","demo_policy_id":"${"b".repeat(64)}"}""",
            )) {
                withServer { server ->
                    val live = started(server, purpose)
                    live.frontalJpeg = byteArrayOf(1)
                    server.enqueue(json("""{"step":"media","received":true}"""))
                    server.enqueue(json("""{"step":"signals","received":true}"""))
                    server.enqueue(json(response))
                    assertEquals(Next.Fail(ApiError.BadResponse), live.submitFace(null, emptyList(), emptyMap()))
                }
            }
        }
    }

    @Test fun onboardingPersistsTheValidatedDemoModeAndPolicy() = runTest {
        withServer { server ->
            val memory = Memory()
            val store = AccountStore(memory) { now }
            val legacyReceipt = receipt.copy(accountId = "acc_legacy", deviceId = "dev_legacy")
            store.save(legacyReceipt, oldAlias)
            val keys = Keys().apply { entries[oldAlias] = Signer() }
            val originalPublicKey = keys.entries.getValue(oldAlias).publicKeySpki
            val accounts = AccountFlow(store, keys, true, newAlias = { newAlias })
            val entry = accounts.begin(Purpose.Onboarding)
            val live = LiveFlow(SessionApi(server.url("/").toString()), entry.signer)
            server.enqueue(json(session("onboarding")))
            assertNull(live.ensureSession(null, "onboarding"))
            live.frontalJpeg = byteArrayOf(1)
            server.enqueue(json("""{"step":"media","received":true}"""))
            server.enqueue(json("""{"step":"signals","received":true}"""))
            server.enqueue(json("""{"status":"voice_challenge","voice_prompt":"synthetic","voice_challenge_id":"vc_1","evaluation_mode":"manual_full_demo","demo_policy_id":"$policy"}"""))
            assertEquals(Next.To(Routes.Voice), live.submitFace(null, emptyList(), emptyMap()))
            server.enqueue(json("""{"status":"pass","evaluation_mode":"manual_full_demo","demo_policy_id":"$policy","account":{"account_id":"acc_old","device_id":"dev_old","expires_at":"2030-01-01T00:00:00Z"}}"""))
            val next = live.submitVoice(byteArrayOf(2))
            assertEquals(Next.To(Routes.Success), accounts.finish(entry, live, next))
            assertTrue(accounts.accountSaved)
            val persisted = Json.parseToJsonElement(memory.values.getValue("account_binding.v2")).jsonObject
            assertEquals("manual_full_demo", persisted["evaluationMode"]?.jsonPrimitive?.content)
            assertEquals(policy, persisted["demoPolicyId"]?.jsonPrimitive?.content)
            val restored = AccountStore(memory) { now }.load()!!
            assertEquals(receipt, restored.receipt)
            assertEquals(newAlias, restored.keyAlias)
            val archived = restored.previousBindings.single()
            assertEquals(legacyReceipt, archived.receipt)
            assertEquals(oldAlias, archived.keyAlias)
            assertNull(archived.evaluationMode)
            assertNull(archived.demoPolicyId)
            assertEquals(originalPublicKey, keys.open(archived.keyAlias, create = false).publicKeySpki)
            assertTrue(keys.deleted.isEmpty())
        }
    }

    private suspend fun started(server: MockWebServer, purpose: String): LiveFlow {
        val live = LiveFlow(SessionApi(server.url("/").toString()), Signer())
        if (purpose != "onboarding") live.bindAccount(StoredAccount(receipt, oldAlias, "manual_full_demo", policy))
        if (purpose == "reauth") {
            // L0 needs the request nonce and exact server bytes, so generate the challenge from it.
            server.dispatcher = object : okhttp3.mockwebserver.Dispatcher() {
                override fun dispatch(request: okhttp3.mockwebserver.RecordedRequest): MockResponse {
                    if (request.path != "/v1/sessions") return json("""{"received":true}""")
                    val nonce = Json.parseToJsonElement(request.body.readUtf8()).jsonObject.getValue("nonce").jsonPrimitive.content
                    val expiry = Instant.now().plusSeconds(60)
                    val message = """{"version":"vericlue-device-auth-v1","session_id":"ses_1","account_id":"acc_old","device_id":"dev_old","purpose":"reauth","nonce":"$nonce","server_nonce":"${"c".repeat(64)}","expires_at_ms":${expiry.toEpochMilli()}}"""
                    val encoded = Base64.getEncoder().encodeToString(message.toByteArray(Charsets.US_ASCII))
                    return json(session(purpose).replace("\"nonce\":\"synthetic_nonce_1234\"", "\"nonce\":\"$nonce\"").dropLast(1) + ",\"device_challenge\":{\"message\":\"$encoded\",\"expires_at\":\"${Instant.ofEpochMilli(expiry.toEpochMilli())}\"}}")
                }
            }
        } else server.enqueue(json(session(purpose)))
        assertNull(live.ensureSession(null, purpose))
        if (purpose == "reauth") server.dispatcher = okhttp3.mockwebserver.QueueDispatcher()
        return live
    }

    private suspend fun challengeVoice(server: MockWebServer, live: LiveFlow) {
        live.frontalJpeg = byteArrayOf(1)
        server.enqueue(json("""{"step":"media","received":true}"""))
        server.enqueue(json("""{"step":"signals","received":true}"""))
        server.enqueue(json("""{"status":"voice_challenge","voice_prompt":"synthetic","voice_challenge_id":"vc_1","evaluation_mode":"manual_full_demo","demo_policy_id":"$policy"}"""))
        assertEquals(Next.To(Routes.Voice), live.submitFace(null, emptyList(), emptyMap()))
    }

    private fun session(purpose: String, mode: String = "manual_full_demo", responsePolicy: String? = policy) = """{"session_id":"ses_1","token":"tok_1","expires_at":"2030-01-01T00:00:00Z","purpose":"$purpose","nonce":"synthetic_nonce_1234","evaluation_mode":"$mode","demo_policy_id":${responsePolicy?.let { "\"$it\"" } ?: "null"},"challenge":{"challenge_id":"ch_1","color_sequence":[],"media_nonce":"${"0".repeat(64)}"}}"""
    private fun json(body: String, code: Int = 200) = MockResponse().setResponseCode(code).setBody(body)
    private suspend fun withServer(block: suspend (MockWebServer) -> Unit) {
        val server = MockWebServer().apply { start() }
        try { block(server) } finally { server.shutdown() }
    }
}
