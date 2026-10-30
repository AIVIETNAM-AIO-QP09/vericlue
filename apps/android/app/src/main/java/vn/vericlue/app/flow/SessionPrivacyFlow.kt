package vn.vericlue.app.flow

import vn.vericlue.app.data.api.*
import kotlinx.coroutines.sync.Mutex
import kotlinx.coroutines.sync.withLock

/** Version of the notice actually bundled with TermsScreen, never copied from the server. */
object PrivacyNotice {
    const val VERSION = "demo-v1"
    fun categories(purpose: Purpose): List<String> = when (purpose) {
        Purpose.Onboarding -> listOf("contact", "id_document", "face_biometrics", "voice_biometrics")
        Purpose.Recovery -> listOf("contact", "face_biometrics", "voice_biometrics")
        Purpose.Reauth -> listOf("face_biometrics", "voice_biometrics")
    }
}

/** Only an explicit user action calls grant. The session supplier always provides the latest bearer. */
class SessionPrivacyFlow(private val api: SessionApi, private val mutation: Mutex = Mutex(), private val session: () -> CreateSessionResponse?) {
    var receipt: SessionPrivacyState? = null
        private set
    var stopping = false
        private set

    fun reset() { receipt = null; stopping = false }

    fun permits(category: String): Boolean = !stopping && receipt?.let {
        it.sessionId == session()?.sessionId && it.status == "granted" && category in it.categories
    } == true

    suspend fun grant(purpose: Purpose, displayedVersion: String): ApiError? {
        return mutation.withLock { grantLocked(purpose, displayedVersion) }
    }

    private suspend fun grantLocked(purpose: Purpose, displayedVersion: String): ApiError? {
        if (stopping) return ApiError.Expired
        val current = session() ?: return ApiError.Expired
        receipt = null
        val state = when (val result = api.sessionPrivacy(current.sessionId, current.token)) {
            is ApiResult.Err -> return result.error
            is ApiResult.Ok -> result.value
        }
        if (!state.validFor(current.sessionId) || displayedVersion != PrivacyNotice.VERSION ||
            state.policyVersion != displayedVersion) return ApiError.BadResponse
        if (state.status == "withdrawn") { stopping = true; return ApiError.Expired }
        if (stopping || session() != current) return ApiError.Expired
        return when (val result = api.grantSessionConsent(current.sessionId, current.token,
            PrivacyConsentRequest(displayedVersion, PrivacyNotice.categories(purpose), true))) {
            is ApiResult.Err -> result.error
            is ApiResult.Ok -> {
                val granted = result.value
                if (stopping || session() != current) return ApiError.Expired
                if (!granted.validFor(current.sessionId) || granted.policyVersion != displayedVersion ||
                    granted.status != "granted" || !granted.categories.containsAll(PrivacyNotice.categories(purpose)) ||
                    !validReceipt(granted.consentReceiptId) || granted.consentedAt == null) ApiError.BadResponse
                else { receipt = granted; null }
            }
        }
    }

    suspend fun withdraw(): ApiError? {
        stopping = true // Block new capture/upload even if the request fails; retain bearer for retry.
        return mutation.withLock { withdrawLocked() }
    }

    private suspend fun withdrawLocked(): ApiError? {
        val current = session() ?: return ApiError.Expired
        return when (val result = api.withdrawSessionConsent(current.sessionId, current.token)) {
            is ApiResult.Err -> result.error
            is ApiResult.Ok -> {
                val withdrawn = result.value
                if (session() != current) return ApiError.Expired
                if (!withdrawn.validFor(current.sessionId) || withdrawn.status != "withdrawn" ||
                    !validReceipt(withdrawn.withdrawalReceiptId) || withdrawn.withdrawnAt == null ||
                    withdrawn.storageErasure == "not_requested") ApiError.BadResponse
                else { receipt = withdrawn; null }
            }
        }
    }

    private fun validReceipt(id: String?) = id?.matches(Regex("prv_[0-9a-f]{32}")) == true
}
