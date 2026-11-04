package vn.vericlue.app

import java.util.concurrent.TimeUnit
import kotlinx.coroutines.test.runTest
import kotlinx.serialization.json.Json
import kotlinx.serialization.json.boolean
import kotlinx.serialization.json.jsonObject
import kotlinx.serialization.json.jsonPrimitive
import okhttp3.mockwebserver.MockResponse
import okhttp3.mockwebserver.MockWebServer
import okhttp3.mockwebserver.SocketPolicy
import org.junit.Assert.*
import org.junit.Test
import vn.vericlue.app.data.api.AccountAccessSession
import vn.vericlue.app.data.api.AccountAccessSetupRequest
import vn.vericlue.app.data.api.AccountProfile
import vn.vericlue.app.data.api.ApiError
import vn.vericlue.app.data.api.ApiResult
import vn.vericlue.app.data.api.SessionApi

/** Real HTTP wire tests. All identifiers, credentials and profile fields are synthetic. */
class AccountAccessApiTest {
    private val profile = """{"account_id":"acct_${"a".repeat(32)}","username":"synthetic.user","full_name":"Synthetic User","masked_id_number":"********1234","created_at":"2026-11-03T10:00:00Z","expires_at":"2026-11-04T10:00:00Z","evaluation_mode":"manual_full_demo","demo_policy_id":"${"b".repeat(64)}"}"""
    private val accessToken = "vca_" + "x".repeat(43)
    private fun session(method: String) = """{"access_token":"$accessToken","expires_at":"2026-11-03T10:10:00Z","authentication_method":"$method","profile":$profile}"""

    @Test fun setupUsesSuccessfulSessionBearerAndExplicitProfilePolicy() = runTest {
        val server = MockWebServer().apply { start() }
        try {
            server.enqueue(MockResponse().setBody(profile))
            val result = SessionApi(server.url("/").toString()).setupAccountAccess("ses_synthetic", "private-session-token",
                AccountAccessSetupRequest("synthetic.user", "Synthetic passphrase", true, "account-profile-v1"))
            assertTrue(result is ApiResult.Ok<AccountProfile>)
            val request = requireNotNull(server.takeRequest(2, TimeUnit.SECONDS))
            assertEquals("POST", request.method)
            assertEquals("/v1/sessions/ses_synthetic/account-access/setup", request.path)
            assertEquals("Bearer private-session-token", request.getHeader("Authorization"))
            assertEquals("no-store", request.getHeader("Cache-Control"))
            val body = Json.parseToJsonElement(request.body.readUtf8()).jsonObject
            assertEquals(setOf("username", "password", "profile_consent", "policy_version"), body.keys)
            assertEquals("account-profile-v1", body.getValue("policy_version").jsonPrimitive.content)
            assertTrue(body.getValue("profile_consent").jsonPrimitive.boolean)
            assertEquals("Synthetic passphrase", body.getValue("password").jsonPrimitive.content)
            assertFalse(request.path.orEmpty().contains("passphrase"))
            assertFalse(request.path.orEmpty().contains("private-session-token"))
        } finally { server.shutdown() }
    }

    @Test fun passwordLoginSendsCredentialsOnlyInPostBodyAndParsesAccessSession() = runTest {
        val server = MockWebServer().apply { start() }
        try {
            server.enqueue(MockResponse().setBody(session("password")))
            val result = SessionApi(server.url("/").toString()).loginWithPassword("synthetic.user", "Synthetic passphrase")
            val value = (result as ApiResult.Ok<AccountAccessSession>).value
            assertEquals(accessToken, value.accessToken)
            assertEquals("password", value.authenticationMethod)
            assertEquals("********1234", value.profile.maskedIdNumber)
            val request = requireNotNull(server.takeRequest(2, TimeUnit.SECONDS))
            assertEquals("POST", request.method)
            assertEquals("/v1/account-access/password", request.path)
            assertNull(request.getHeader("Authorization"))
            assertEquals("no-store", request.getHeader("Cache-Control"))
            val body = Json.parseToJsonElement(request.body.readUtf8()).jsonObject
            assertEquals(setOf("username", "password"), body.keys)
            assertEquals("synthetic.user", body.getValue("username").jsonPrimitive.content)
            assertEquals("Synthetic passphrase", body.getValue("password").jsonPrimitive.content)
        } finally { server.shutdown() }
    }

    @Test fun faceExchangeAndProfileUseDifferentBearerScopes() = runTest {
        val server = MockWebServer().apply { start() }
        try {
            server.enqueue(MockResponse().setBody(session("face")))
            server.enqueue(MockResponse().setBody(profile))
            server.enqueue(MockResponse().setBody("""{"revoked":true}"""))
            val api = SessionApi(server.url("/").toString())
            assertTrue(api.loginAfterFace("ses_synthetic", "face-session-token") is ApiResult.Ok)
            assertTrue(api.accountProfile(accessToken) is ApiResult.Ok)
            assertTrue(api.logoutAccount(accessToken) is ApiResult.Ok)
            val face = requireNotNull(server.takeRequest(2, TimeUnit.SECONDS))
            val me = requireNotNull(server.takeRequest(2, TimeUnit.SECONDS))
            val logout = requireNotNull(server.takeRequest(2, TimeUnit.SECONDS))
            assertEquals("/v1/sessions/ses_synthetic/account-access/face", face.path)
            assertEquals("Bearer face-session-token", face.getHeader("Authorization"))
            assertEquals("{}", face.body.readUtf8())
            assertEquals("GET", me.method)
            assertEquals("/v1/account-access/me", me.path)
            assertEquals("Bearer $accessToken", me.getHeader("Authorization"))
            assertEquals("/v1/account-access/logout", logout.path)
            assertEquals("POST", logout.method)
            assertEquals("Bearer $accessToken", logout.getHeader("Authorization"))
            listOf(face, me, logout).forEach {
                assertEquals("no-store", it.getHeader("Cache-Control"))
                assertFalse(it.path.orEmpty().contains(accessToken))
            }
        } finally { server.shutdown() }
    }

    @Test fun redirectedPasswordRequestsAreNeverForwardedToAnotherServer() = runTest {
        val server = MockWebServer().apply { start() }
        val target = MockWebServer().apply { start() }
        try {
            server.enqueue(MockResponse().setResponseCode(307).setHeader("Location", target.url("/capture")))
            target.enqueue(MockResponse().setBody(session("password")))
            assertTrue(SessionApi(server.url("/").toString()).loginWithPassword("synthetic.user", "Synthetic passphrase") is ApiResult.Err)
            assertEquals(1, server.requestCount)
            assertEquals(0, target.requestCount)
        } finally { server.shutdown(); target.shutdown() }
    }

    @Test fun redirectedBearerRequestsAreNotFollowedEvenOnSameOrigin() = runTest {
        val server = MockWebServer().apply { start() }
        try {
            server.enqueue(MockResponse().setResponseCode(302).setHeader("Location", server.url("/unexpected")))
            server.enqueue(MockResponse().setBody(profile))
            assertTrue(SessionApi(server.url("/").toString()).accountProfile(accessToken) is ApiResult.Err)
            assertEquals(1, server.requestCount)
        } finally { server.shutdown() }
    }

    @Test fun malformedAndIncompleteSuccessBodiesAreErrors() = runTest {
        val server = MockWebServer().apply { start() }
        try {
            val api = SessionApi(server.url("/").toString())
            for (body in listOf("not-json", "{}", """{"access_token":"$accessToken"}""", "null")) {
                server.enqueue(MockResponse().setBody(body))
                val result = api.loginWithPassword("synthetic.user", "Synthetic passphrase")
                assertEquals(ApiError.BadResponse, (result as ApiResult.Err).error)
            }
        } finally { server.shutdown() }
    }

    @Test fun oversizedResponsesAreRejectedForContentLengthAndChunkedTransfer() = runTest {
        val server = MockWebServer().apply { start() }
        try {
            val body = session("password").dropLast(1) + ",\"ignored_padding\":\"" + "x".repeat(70_000) + "\"}"
            server.enqueue(MockResponse().setBody(body))
            server.enqueue(MockResponse().setChunkedBody(body, 4096))
            val api = SessionApi(server.url("/").toString())
            repeat(2) {
                assertEquals(ApiError.BadResponse, (api.loginWithPassword("synthetic.user", "Synthetic passphrase") as ApiResult.Err).error)
            }
        } finally { server.shutdown() }
    }

    @Test fun failedPasswordPostIsNotRetriedAutomatically() = runTest {
        val server = MockWebServer().apply { start() }
        try {
            server.enqueue(MockResponse().setSocketPolicy(SocketPolicy.DISCONNECT_AFTER_REQUEST))
            server.enqueue(MockResponse().setBody(session("password")))
            assertEquals(ApiError.Network, (SessionApi(server.url("/").toString()).loginWithPassword("synthetic.user", "Synthetic passphrase") as ApiResult.Err).error)
            assertEquals(1, server.requestCount)
        } finally { server.shutdown() }
    }

    @Test fun unauthorizedOrExpiredResponseNeverBecomesAnAccessSession() = runTest {
        val server = MockWebServer().apply { start() }
        try {
            val api = SessionApi(server.url("/").toString())
            for ((status, expected) in listOf(401 to ApiError.Unauthorized, 410 to ApiError.Expired)) {
                server.enqueue(MockResponse().setResponseCode(status).setBody("""{"error_code":"account_unavailable","message":"private detail is not displayed"}"""))
                val result = api.loginWithPassword("synthetic.user", "Synthetic passphrase")
                assertEquals(expected, (result as ApiResult.Err).error)
            }
        } finally { server.shutdown() }
    }
}
