package vn.vericlue.app

import java.security.KeyPairGenerator
import java.security.Signature
import java.security.spec.ECGenParameterSpec
import java.time.Instant
import java.util.Base64
import java.util.concurrent.TimeUnit
import kotlinx.coroutines.test.runTest
import okhttp3.mockwebserver.MockResponse
import okhttp3.mockwebserver.MockWebServer
import org.junit.Assert.*
import org.junit.Test
import vn.vericlue.app.data.AccountStore
import vn.vericlue.app.data.KeyValueStore
import vn.vericlue.app.data.api.AccountReceipt
import vn.vericlue.app.data.api.ApiError
import vn.vericlue.app.data.api.SessionApi
import vn.vericlue.app.flow.*
import vn.vericlue.app.security.AccountKeys
import vn.vericlue.app.security.MediaSigner

class AccountIntegrationTest {
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
        override fun sign(canonicalManifest: ByteArray) = Base64.getEncoder().encodeToString(
            Signature.getInstance("SHA256withECDSA").run {
                initSign(pair.private); update(canonicalManifest); sign()
            })
    }

    private class Keys : AccountKeys {
        val entries = mutableMapOf<String, MediaSigner>()
        val opened = mutableListOf<Pair<String, Boolean>>()
        val deleted = mutableListOf<String>()
        var onDelete: (String) -> Unit = {}
        override fun exists(alias: String) = entries.containsKey(alias)
        override fun open(alias: String, create: Boolean): MediaSigner {
            opened += alias to create
            if (create) entries.getOrPut(alias) { Signer() }
            return requireNotNull(entries[alias])
        }
        override fun delete(alias: String) { onDelete(alias); deleted += alias; entries.remove(alias) }
    }

    private val old = AccountReceipt("acc_old", "dev_old", "2030-01-01T00:00:00Z")
    private val fresh = old.copy(deviceId = "dev_new")
    private val oldAlias = "vericlue.media.old"
    private val newAlias = "vericlue.media.new"
    private val now = Instant.parse("2026-10-28T00:00:00Z")

    @Test fun receiptAndMatchingAliasSurviveRecreationAndExpireAtTheBoundary() {
        val memory = Memory()
        AccountStore(memory) { now }.save(old, oldAlias)
        val restored = AccountStore(memory) { now }.load()!!
        assertEquals(old, restored.receipt)
        assertEquals(oldAlias, restored.keyAlias)
        assertNull(AccountStore(memory) { Instant.parse(old.expiresAt) }.load())
    }

    @Test fun legacyReceiptWithoutAnAliasIsNeverAssignedAnInventedKey() {
        val memory = Memory()
        memory.values["account_receipt.v1"] = """{"account_id":"acc_old","device_id":"dev_old","expires_at":"2030-01-01T00:00:00Z"}"""
        assertNull(AccountStore(memory) { now }.load())
    }

    @Test fun missingAccountOrDisabledSigningStartsRegistrationWithAHint() {
        val memory = Memory()
        val store = AccountStore(memory) { now }
        val keys = Keys()
        fun start(enabled: Boolean) = AccountFlow(store, keys, enabled, newAlias = { newAlias }).begin(Purpose.Reauth)
        assertEquals(Purpose.Onboarding, start(true).purpose)
        assertFalse(start(true).hint.isNullOrBlank())
        store.save(old, oldAlias)
        keys.entries[oldAlias] = Signer()
        assertEquals(Purpose.Onboarding, start(false).purpose)
        assertNull(start(false).signer)
    }

    @Test fun reauthOpensOnlyTheStoredKeyAndNeverReplacesAMissingKey() {
        val store = AccountStore(Memory()) { now }.apply { save(old, oldAlias) }
        val keys = Keys()
        val accounts = AccountFlow(store, keys, true)
        assertEquals(Routes.RecoveryRequired, accounts.begin(Purpose.Reauth).route)
        assertTrue(keys.opened.isEmpty())
        keys.entries[oldAlias] = Signer()
        val entry = accounts.begin(Purpose.Reauth)
        assertEquals(old, entry.account)
        assertEquals(oldAlias, entry.keyAlias)
        assertEquals(listOf(oldAlias to false), keys.opened)
    }

    @Test fun noVoicePassFetchesAndPersistsReceiptBeforeReturningSuccess() = runTest {
        withServer { server ->
            val store = AccountStore(Memory()) { now }
            val accounts = AccountFlow(store, Keys(), true, newAlias = { newAlias })
            val entry = accounts.begin(Purpose.Onboarding)
            val live = start(server, entry)
            val next = passFace(server, live)
            // Longer than SuccessScreen's automatic 2.6-second departure.
            server.enqueue(json("""{"account_id":"acc_old","device_id":"dev_new","expires_at":"2030-01-01T00:00:00Z"}""")
                .setBodyDelay(2800, TimeUnit.MILLISECONDS))
            assertEquals(Next.To(Routes.Success), accounts.finish(entry, live, next))
            assertEquals(fresh, store.load()!!.receipt)
            assertEquals(newAlias, store.load()!!.keyAlias)
            repeat(4) { server.takeRequest() }
            val request = server.takeRequest()
            assertEquals("/v1/sessions/ses_1/account", request.path)
            assertEquals("Bearer tok_1", request.getHeader("Authorization"))
        }
    }

    @Test fun receiptFailureStillSucceedsAndOnlyLogsInternally() = runTest {
        withServer { server ->
            val store = AccountStore(Memory()) { now }
            val warnings = mutableListOf<String>()
            val accounts = AccountFlow(store, Keys(), true, newAlias = { newAlias }, warn = warnings::add)
            val entry = accounts.begin(Purpose.Onboarding)
            val live = start(server, entry)
            val next = passFace(server, live)
            server.enqueue(json("""{"error_code":"enrollment_not_available","message":"retry"}""", 409))
            assertEquals(Next.To(Routes.Success), accounts.finish(entry, live, next))
            assertNull(store.load())
            assertEquals(1, warnings.size)
        }
    }

    @Test fun recoveryPersistsNewReceiptBeforeDeletingTheOldKey() = runTest {
        recovery(writeFails = false)
    }

    @Test fun failedReceiptWriteKeepsTheOldKeyAndReceipt() = runTest {
        recovery(writeFails = true)
    }

    private suspend fun recovery(writeFails: Boolean) = withServer { server ->
        val memory = Memory()
        val store = AccountStore(memory) { now }.apply { save(old, oldAlias) }
        val keys = Keys().apply { entries[oldAlias] = Signer() }
        val accounts = AccountFlow(store, keys, true, newAlias = { newAlias })
        val entry = accounts.begin(Purpose.Recovery)
        assertEquals(old, entry.account)
        assertNotEquals(keys.entries[oldAlias]!!.publicKeySpki, entry.signer!!.publicKeySpki)
        val live = start(server, entry)
        server.enqueue(json("""{"step":"media","received":true}"""))
        server.enqueue(json("""{"step":"signals","received":true}"""))
        server.enqueue(json("""{"status":"voice_challenge","voice_prompt":"synthetic","voice_challenge_id":"vc_1"}"""))
        live.frontalJpeg = byteArrayOf(1)
        assertEquals(Next.To(Routes.Voice), live.submitFace(null, emptyList(), emptyMap()))
        server.enqueue(json("""{"status":"pass","account":{"account_id":"acc_old","device_id":"dev_new","expires_at":"2030-01-01T00:00:00Z"}}"""))
        val next = live.submitVoice(byteArrayOf(2))
        memory.failWrite = writeFails
        keys.onDelete = { assertEquals(newAlias, store.load()!!.keyAlias) }
        assertEquals(Next.To(Routes.Success), accounts.finish(entry, live, next))
        assertEquals(if (writeFails) old else fresh, store.load()!!.receipt)
        assertEquals(if (writeFails) emptyList<String>() else listOf(oldAlias), keys.deleted)
    }

    @Test fun recoveryRequiredAndUnavailableUseTheirOwnScreens() = runTest {
        withServer { server ->
            val live = LiveFlow(SessionApi(server.url("/").toString()), mediaSigner = null)
            server.enqueue(json("""{"error_code":"recovery_required","message":"retry"}""", 409))
            assertEquals(Routes.RecoveryRequired, errorRoute(live.ensureSession(null, "onboarding")!!))
            server.enqueue(json("""{"error_code":"flow_unavailable","message":"retry"}""", 503))
            assertEquals(Routes.ErrorService, errorRoute(live.ensureSession(null, "onboarding")!!))
            assertNull(live.session)
        }
    }

    private suspend fun start(server: MockWebServer, entry: AccountEntry): LiveFlow {
        val live = LiveFlow(SessionApi(server.url("/").toString()), entry.signer)
        live.boundAccount = entry.account
        server.enqueue(json("""{"session_id":"ses_1","token":"tok_1","expires_at":"2030-01-01T00:00:00Z","purpose":"${FlowRules.purposeCode(entry.purpose)}","nonce":"synthetic_nonce_1234","challenge":{"challenge_id":"ch_1","color_sequence":[],"media_nonce":"${"0".repeat(64)}"}}"""))
        assertNull(live.ensureSession(null, FlowRules.purposeCode(entry.purpose)))
        return live
    }

    private suspend fun passFace(server: MockWebServer, live: LiveFlow): Next {
        live.frontalJpeg = byteArrayOf(1)
        server.enqueue(json("""{"step":"media","received":true}"""))
        server.enqueue(json("""{"step":"signals","received":true}"""))
        server.enqueue(json("""{"status":"pass"}"""))
        return live.submitFace(null, emptyList(), emptyMap())
    }

    private fun json(body: String, code: Int = 200) = MockResponse().setResponseCode(code).setBody(body)

    private suspend fun withServer(block: suspend (MockWebServer) -> Unit) {
        val server = MockWebServer().apply { start() }
        try { block(server) } finally { server.shutdown() }
    }
}
