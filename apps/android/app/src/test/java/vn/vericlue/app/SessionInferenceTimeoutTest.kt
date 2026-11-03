package vn.vericlue.app

import java.util.concurrent.TimeUnit
import kotlinx.coroutines.test.runTest
import okhttp3.OkHttpClient
import okhttp3.mockwebserver.MockResponse
import okhttp3.mockwebserver.MockWebServer
import org.junit.After
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Before
import org.junit.Test
import vn.vericlue.app.data.api.ApiError
import vn.vericlue.app.data.api.ApiResult
import vn.vericlue.app.data.api.SessionApi
import vn.vericlue.app.data.api.Signals

/** Server inference may outlast ordinary requests without making every API wait longer. */
class SessionInferenceTimeoutTest {
    private lateinit var server: MockWebServer
    private lateinit var http: OkHttpClient

    @Before fun setUp() { server = MockWebServer().apply { start() } }

    @After fun tearDown() {
        server.shutdown()
        if (::http.isInitialized) {
            http.connectionPool.evictAll()
            http.dispatcher.executorService.shutdown()
        }
    }

    private data class Budget(val path: String, val readMs: Int, val connectMs: Int, val writeMs: Int)

    private fun api(readTimeoutMs: Long = 60_000, observed: MutableList<Budget>? = null): SessionApi {
        http = OkHttpClient.Builder()
            .connectTimeout(15, TimeUnit.SECONDS)
            .readTimeout(readTimeoutMs, TimeUnit.MILLISECONDS)
            .writeTimeout(60, TimeUnit.SECONDS)
            .retryOnConnectionFailure(false)
            .addInterceptor { chain ->
                observed?.add(Budget(chain.request().url.encodedPath, chain.readTimeoutMillis(),
                    chain.connectTimeoutMillis(), chain.writeTimeoutMillis()))
                chain.proceed(chain.request())
            }.build()
        return SessionApi(server.url("/").toString(), http)
    }

    @Test fun onlyFinalizeAndVoiceUseTheLongerReadBudget() = runTest {
        val budgets = mutableListOf<Budget>()
        val api = api(observed = budgets)
        suspend fun check(path: String, readMs: Int, call: suspend () -> ApiResult<*>) {
            server.enqueue(MockResponse().setResponseCode(503)
                .setBody("""{"error_code":"unavailable","message":"retry"}"""))
            assertTrue(call() is ApiResult.Err)
            assertEquals(Budget(path, readMs, 15_000, 60_000), budgets.removeAt(0))
        }
        check("/v1/sessions/ses_test/finalize", 120_000) { api.finalize("ses_test", "token", "ch_test") }
        check("/v1/sessions/ses_test/voice", 120_000) { api.sendVoice("ses_test", "token", byteArrayOf(1), null) }
        check("/v1/sessions", 60_000) { api.createSession() }
        check("/v1/sessions/ses_test/media", 60_000) { api.uploadMedia("ses_test", "token", byteArrayOf(1), null) }
        check("/v1/sessions/ses_test/signals", 60_000) { api.sendSignals("ses_test", "token", Signals(emptyList(), emptyList())) }
        check("/v1/sessions/ses_test/challenge", 60_000) { api.refreshChallenge("ses_test", "token") }
        check("/v1/sessions/ses_test/privacy", 60_000) { api.sessionPrivacy("ses_test", "token") }
        check("/v1/sessions/ses_test/account", 60_000) { api.accountReceipt("ses_test", "token") }
        check("/v1/sessions/ses_test/result", 60_000) { api.signedResult("ses_test", "token") }
        assertTrue(budgets.isEmpty())
    }

    private fun slowDecision() = MockResponse().setBody("""{"status":"review"}""")
        .setHeadersDelay(250, TimeUnit.MILLISECONDS)

    @Test fun finalizeWaitsForASlowDecisionBeyondTheOrdinaryReadWindow() = runTest {
        val api = api(readTimeoutMs = 100)
        server.enqueue(slowDecision())
        val result = api.finalize("ses_test", "token", "ch_test")
        assertTrue("A slow inference response must be received: $result", result is ApiResult.Ok)
        assertEquals("review", (result as ApiResult.Ok).value.status)
        assertEquals(1, server.requestCount)
    }

    @Test fun voiceWaitsForASlowDecisionBeyondTheOrdinaryReadWindow() = runTest {
        val api = api(readTimeoutMs = 100)
        server.enqueue(slowDecision())
        val result = api.sendVoice("ses_test", "token", byteArrayOf(1), null)
        assertTrue("A slow inference response must be received: $result", result is ApiResult.Ok)
        assertEquals("review", (result as ApiResult.Ok).value.status)
        assertEquals(1, server.requestCount)
    }

    @Test fun ordinaryRequestsKeepTheirExistingReadTimeout() = runTest {
        val api = api(readTimeoutMs = 100)
        server.enqueue(slowDecision())
        assertEquals(ApiResult.Err(ApiError.Network), api.refreshChallenge("ses_test", "token"))
        assertEquals(1, server.requestCount)
    }
}
