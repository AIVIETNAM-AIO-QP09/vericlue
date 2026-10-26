package vn.vericlue.app

import kotlinx.coroutines.test.runTest
import okhttp3.mockwebserver.MockResponse
import okhttp3.mockwebserver.MockWebServer
import org.junit.Assert.*
import org.junit.Test
import vn.vericlue.app.data.api.ApiResult
import vn.vericlue.app.data.api.SessionApi
import vn.vericlue.app.data.api.SignedResult

class SignedResultApiTest {
    @Test fun forwardsOpaqueResultWithSessionBearerAndNoCache() = runTest {
        val server = MockWebServer().apply { start() }
        try {
            server.enqueue(MockResponse().setBody("""{"algorithm":"Ed25519","key_id":"key","payload":"opaque","signature":"signed"}"""))
            val api = SessionApi(server.url("/").toString())
            val result = api.signedResult("ses_test", "token") as ApiResult.Ok<SignedResult>
            assertEquals("opaque", result.value.payload)
            val request = server.takeRequest()
            assertEquals("GET", request.method)
            assertEquals("/v1/sessions/ses_test/result", request.path)
            assertEquals("Bearer token", request.getHeader("Authorization"))
            assertEquals("no-store", request.getHeader("Cache-Control"))
        } finally { server.shutdown() }
    }

    @Test fun unavailableResultIsAnError() = runTest {
        val server = MockWebServer().apply { start() }
        try {
            server.enqueue(MockResponse().setResponseCode(409).setBody("""{"error_code":"result_not_available","message":"retry"}"""))
            val result = SessionApi(server.url("/").toString()).signedResult("ses_test", "token")
            assertTrue(result is ApiResult.Err)
        } finally { server.shutdown() }
    }
}
