package vn.vericlue.app.data.api

import kotlinx.serialization.SerialName
import kotlinx.serialization.Serializable

/** packages/contracts/schemas/account_access.schema.json. Never persisted as a login session. */
@Serializable
data class AccountProfile(
    @SerialName("account_id") val accountId: String,
    val username: String,
    @SerialName("full_name") val fullName: String?,
    @SerialName("masked_id_number") val maskedIdNumber: String?,
    @SerialName("created_at") val createdAt: String,
    @SerialName("expires_at") val expiresAt: String,
    @SerialName("evaluation_mode") val evaluationMode: String,
    @SerialName("demo_policy_id") val demoPolicyId: String?,
)

@Serializable
data class AccountAccessSession(
    @SerialName("access_token") val accessToken: String,
    @SerialName("expires_at") val expiresAt: String,
    @SerialName("authentication_method") val authenticationMethod: String,
    val profile: AccountProfile,
)

@Serializable
data class AccountAccessSetupRequest(
    val username: String,
    val password: String,
    @SerialName("profile_consent") val profileConsent: Boolean,
    @SerialName("policy_version") val policyVersion: String,
)

@Serializable
data class AccountPasswordRequest(val username: String, val password: String)

@Serializable
data class AccountLogoutResponse(val revoked: Boolean)
