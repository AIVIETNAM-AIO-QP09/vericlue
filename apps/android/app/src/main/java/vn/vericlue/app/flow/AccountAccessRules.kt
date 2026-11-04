package vn.vericlue.app.flow

import java.time.Instant
import java.time.OffsetDateTime
import java.time.format.DateTimeFormatter
import java.time.ZoneId
import java.util.Locale
import java.text.Normalizer
import vn.vericlue.app.data.StoredAccount
import vn.vericlue.app.data.api.AccountAccessSession
import vn.vericlue.app.data.api.AccountProfile
import vn.vericlue.app.data.api.ApiError
import vn.vericlue.app.data.api.ApiResult

/** Access to a profile is separate from enrollment or issuing an eKYC result. */
object AccountAccessRules {
    fun username(value: String) = value.trim().lowercase(Locale.ROOT)
    fun validUsername(value: String) = Regex("[a-z0-9][a-z0-9._-]{2,31}").matches(value)
    fun validPassword(value: String) = value.codePointCount(0, value.length) in 12..128

    /** Presentation only: keep the original verified name in the API profile. */
    fun displayName(value: String?): String? = value?.trim()?.takeIf { it.isNotEmpty() }?.let {
        Normalizer.normalize(it, Normalizer.Form.NFD).replace(Regex("\\p{M}+"), "")
            .replace('đ', 'd').replace('Đ', 'D').replace(Regex("\\s+"), " ").uppercase(Locale.ROOT)
    }

    fun profileValid(profile: AccountProfile, now: Instant = Instant.now()): Boolean {
        val created = instant(profile.createdAt) ?: return false
        val expires = instant(profile.expiresAt) ?: return false
        return Regex("acct_[0-9a-f]{32}").matches(profile.accountId) && validUsername(profile.username) &&
            expires.isAfter(now) && expires.isAfter(created) && !created.isAfter(now.plusSeconds(300)) &&
            (profile.fullName == null || profile.fullName.length <= 200) &&
            (profile.maskedIdNumber == null || Regex("\\*{8}[0-9]{4}").matches(profile.maskedIdNumber)) &&
            when (profile.evaluationMode) {
                "standard" -> profile.demoPolicyId == null
                "manual_full_demo" -> profile.demoPolicyId?.matches(Regex("[0-9a-f]{64}")) == true
                else -> false
            }
    }

    fun sessionValid(value: AccountAccessSession, method: String, expectedUsername: String? = null,
                     binding: StoredAccount? = null, now: Instant = Instant.now()): Boolean {
        val expires = instant(value.expiresAt) ?: return false
        val accountExpires = instant(value.profile.expiresAt) ?: return false
        if (!Regex("vca_[A-Za-z0-9_-]{43}").matches(value.accessToken) ||
            value.authenticationMethod != method || method !in setOf("face", "password") ||
            !expires.isAfter(now) || expires.isAfter(accountExpires) ||
            !profileValid(value.profile, now) ||
            (expectedUsername != null && value.profile.username != username(expectedUsername))) return false
        return method != "face" || binding != null && binding.hasKnownEvaluationBinding &&
            instant(binding.receipt.expiresAt)?.isAfter(now) == true &&
            value.profile.accountId == binding.receipt.accountId &&
            value.profile.evaluationMode == binding.evaluationMode &&
            value.profile.demoPolicyId == binding.demoPolicyId
    }

    fun sameProfile(a: AccountProfile, b: AccountProfile) = a.accountId == b.accountId &&
        a.username == b.username && a.evaluationMode == b.evaluationMode && a.demoPolicyId == b.demoPolicyId

    fun instant(value: String): Instant? = runCatching { OffsetDateTime.parse(value).toInstant() }.getOrNull()
    fun displayDate(value: String): String = instant(value)?.let {
        DateTimeFormatter.ofPattern("HH:mm · dd/MM/yyyy", Locale.forLanguageTag("vi-VN"))
            .withZone(ZoneId.systemDefault()).format(it)
    } ?: "Chưa có thông tin"

    fun error(result: ApiResult.Err): String = when (result.code) {
        "account_setup_required" -> "Tài khoản chưa có thông tin đăng nhập. Hãy đăng nhập bằng khuôn mặt để thiết lập."
        "username_unavailable" -> "Số điện thoại này chưa thể dùng để đăng ký. Vui lòng đăng nhập hoặc khôi phục tài khoản."
        "account_phone_mismatch" -> "Số điện thoại chưa khớp với tài khoản đã xác minh. Vui lòng kiểm tra lại."
        "account_access_locked", "account_login_limited", "rate_limited" -> "Bạn đã thử nhiều lần. Vui lòng chờ rồi đăng nhập lại."
        else -> when (result.error) {
            ApiError.Network -> "Chưa thể kết nối. Kiểm tra mạng rồi thử lại."
            ApiError.Unauthorized -> "Thông tin đăng nhập chưa đúng hoặc phiên đã hết hạn."
            ApiError.Expired -> "Tài khoản hoặc phiên đăng nhập đã hết hạn. Vui lòng bắt đầu lại."
            ApiError.Busy, ApiError.Server -> "Dịch vụ đang bận. Vui lòng thử lại sau."
            else -> "Chưa thể hoàn tất yêu cầu. Vui lòng kiểm tra và thử lại."
        }
    }
}
