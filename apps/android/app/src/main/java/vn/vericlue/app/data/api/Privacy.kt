package vn.vericlue.app.data.api

import kotlinx.serialization.SerialName
import kotlinx.serialization.Serializable

/** Existing privacy.schema.json: session processing does not grant account-template storage. */
@Serializable
data class PrivacyConsentRequest(
    @SerialName("policy_version") val policyVersion: String,
    val categories: List<String>,
    val consent: Boolean,
)

@Serializable
data class PrivacyWithdrawalRequest(val confirm: Boolean)

@Serializable
data class SessionPrivacyState(
    @SerialName("session_id") val sessionId: String,
    val scope: String,
    @SerialName("policy_version") val policyVersion: String,
    val status: String,
    val categories: List<String>,
    @SerialName("consent_receipt_id") val consentReceiptId: String? = null,
    @SerialName("consented_at") val consentedAt: String? = null,
    @SerialName("withdrawal_receipt_id") val withdrawalReceiptId: String? = null,
    @SerialName("withdrawn_at") val withdrawnAt: String? = null,
    @SerialName("storage_erasure") val storageErasure: String,
    @SerialName("processing_cleanup") val processingCleanup: String,
    @SerialName("account_data_erased") val accountDataErased: Boolean,
    @SerialName("credential_revocation") val credentialRevocation: String,
) {
    fun validFor(sessionId: String): Boolean = this.sessionId == sessionId && scope == "session" &&
        policyVersion.matches(Regex("[A-Za-z0-9._-]{1,64}")) &&
        status in setOf("not_granted", "granted", "withdrawn") &&
        categories.distinct().size == categories.size && categories.all { it in CATEGORIES } &&
        storageErasure in setOf("not_requested", "key_destroyed", "files_deleted") &&
        processingCleanup in setOf("not_applicable", "not_verified") &&
        !accountDataErased && credentialRevocation == "not_performed"

    companion object {
        val CATEGORIES = setOf("contact", "id_document", "face_biometrics", "voice_biometrics")
    }
}

@Serializable
data class AccountTemplateConsentRequest(
    @SerialName("policy_version") val policyVersion: String,
    val purpose: String,
    val consent: Boolean,
)

@Serializable
data class AccountTemplatePrivacyState(
    @SerialName("session_id") val sessionId: String,
    val scope: String,
    val purpose: String,
    @SerialName("policy_version") val policyVersion: String,
    @SerialName("retention_seconds") val retentionSeconds: Int,
    val status: String,
    @SerialName("consent_receipt_id") val consentReceiptId: String? = null,
    @SerialName("consented_at") val consentedAt: String? = null,
) {
    fun validFor(sessionId: String): Boolean = this.sessionId == sessionId &&
        scope == "account_template" &&
        purpose == "account_template" &&
        policyVersion.matches(Regex("[A-Za-z0-9._-]{1,64}")) &&
        retentionSeconds == 86400 &&
        status in setOf("not_granted", "granted", "withdrawn")
}
