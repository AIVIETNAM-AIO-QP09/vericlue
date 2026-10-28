package vn.vericlue.app

import java.security.KeyPairGenerator
import java.security.Signature
import java.security.spec.ECGenParameterSpec
import java.time.Instant
import java.util.Base64
import kotlinx.coroutines.test.runTest
import okhttp3.mockwebserver.MockResponse
import okhttp3.mockwebserver.MockWebServer
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test
import vn.vericlue.app.data.AccountStore
import vn.vericlue.app.data.KeyValueStore
import vn.vericlue.app.data.api.AccountReceipt
import vn.vericlue.app.data.api.SessionApi
import vn.vericlue.app.flow.LiveFlow
import vn.vericlue.app.flow.Next
import vn.vericlue.app.flow.Routes
import vn.vericlue.app.security.MediaSigner

class AccountStoreTest {
    private class MapStore : KeyValueStore {
        val map = mutableMapOf<String, String>()
        override fun get(key: String) = map[key]
        override fun put(key: String, value: String) { map[key] = value }
        override fun remove(key: String) { map.remove(key) }
    }

    private class Signer : MediaSigner {
        private val pair = KeyPairGenerator.getInstance("EC").run {
            initialize(ECGenParameterSpec("secp256r1")); generateKeyPair()
        }
        override val publicKeySpki = Base64.getEncoder().encodeToString(pair.public.encoded)
        override fun sign(canonicalManifest: ByteArray): String =
            Base64.getEncoder().encodeToString(Signature.getInstance("SHA256withECDSA").run {
                initSign(pair.private); update(canonicalManifest); sign()
            })
    }

    private val receipt = AccountReceipt("acc_1", "dev_1", "2026-11-27T10:00:00Z")
    private val now = Instant.parse("2026-10-27T10:00:00Z")

    @Test
    fun savesAndLoadsAReceipt() {
        val store = AccountStore(MapStore()) { now }
        assertNull(store.load())
        store.save(receipt, "vericlue.media.test")
        assertEquals(receipt, store.load()?.receipt)
        store.clear()
        assertNull(store.load())
    }

    @Test
    fun expiredOrBrokenReceiptCountsAsNoAccount() {
        val map = MapStore()
        AccountStore(map) { now }.save(receipt, "vericlue.media.test")
        val store = AccountStore(map) { Instant.parse("2026-11-28T00:00:00Z") }
        assertNull(store.load())
        assertTrue(map.map.isEmpty())
        map.put("account_binding.v2", "{not json")
        assertNull(store.load())
        assertTrue(map.map.isEmpty())
    }

    @Test
    fun onboardingPassAtFinalizeFetchesTheReceipt() = runTest {
        val server = MockWebServer().apply { start() }
        try {
            val flow = LiveFlow(SessionApi(server.url("/").toString()), mediaSigner = null)
            server.enqueue(MockResponse().setBody(
                """{"session_id":"ses_1","token":"tok_1","expires_at":"x","purpose":"onboarding",
                   "challenge":{"challenge_id":"ch_1","color_sequence":[]}}"""))
            assertNull(flow.ensureSession(null, "onboarding"))
            flow.frontalJpeg = byteArrayOf(1)
            server.enqueue(MockResponse().setBody("""{"step":"media","received":true}"""))
            server.enqueue(MockResponse().setBody("""{"step":"signals","received":true}"""))
            server.enqueue(MockResponse().setBody("""{"status":"pass"}"""))
            assertEquals(Next.To(Routes.Success), flow.submitFace(null, emptyList(), emptyMap()))
            server.enqueue(MockResponse().setBody("""{"account_id":"acc_1","device_id":"dev_1","expires_at":"2026-11-27T10:00:00Z"}"""))
            assertEquals(receipt, flow.receiptAfterPass())
            repeat(4) { server.takeRequest() }
            assertEquals("/v1/sessions/ses_1/account", server.takeRequest().path)
        } finally { server.shutdown() }
    }

    @Test
    fun recoverySendsTheSavedAccount() = runTest {
        val server = MockWebServer().apply { start() }
        try {
            val flow = LiveFlow(SessionApi(server.url("/").toString()), Signer())
            flow.boundAccount = receipt
            server.enqueue(MockResponse().setBody(
                """{"session_id":"ses_1","token":"tok_1","expires_at":"x","purpose":"recovery",
                   "challenge":{"challenge_id":"ch_1","color_sequence":[],"media_nonce":"${"0".repeat(64)}"}}"""))
            assertNull(flow.ensureSession(null, "recovery"))
            val body = server.takeRequest().body.readUtf8()
            assertTrue(body.contains("\"account_id\":\"acc_1\""))
            assertTrue(!body.contains("dev_1"))
            flow.reset()
            assertNull(flow.boundAccount)
        } finally { server.shutdown() }
    }
}
