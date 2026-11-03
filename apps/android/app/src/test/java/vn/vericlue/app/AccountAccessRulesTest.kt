package vn.vericlue.app

import java.time.Instant
import org.junit.Assert.*
import org.junit.Test
import vn.vericlue.app.data.StoredAccount
import vn.vericlue.app.data.api.AccountAccessSession
import vn.vericlue.app.data.api.AccountProfile
import vn.vericlue.app.data.api.AccountReceipt
import vn.vericlue.app.data.api.ApiError
import vn.vericlue.app.data.api.ApiResult
import vn.vericlue.app.flow.AccountAccessRules as Rules

class AccountAccessRulesTest {
    @Test fun nameFormattingDoesNotChangeTheVerifiedOriginal() {
        val original = "  Nguyễn   Thị Đặng  "
        assertEquals("NGUYEN THI DANG", Rules.displayName(original))
        assertEquals("NGUYEN THI DANG", Rules.displayName("Nguyễn Thị Đặng"))
        assertNull(Rules.displayName(null))
        assertNull(Rules.displayName("  "))
        assertEquals("  Nguyễn   Thị Đặng  ", original)
    }
    private val now = Instant.parse("2026-11-03T10:00:00Z")
    private val policy = "b".repeat(64)
    private val profile = AccountProfile("acct_" + "a".repeat(32), "synthetic.user", "Synthetic User", "********1234",
        "2026-11-03T09:00:00Z", "2026-11-04T09:00:00Z", "manual_full_demo", policy)
    private val session = AccountAccessSession("vca_" + "x".repeat(43), "2026-11-03T10:10:00Z", "password", profile)
    private val binding = StoredAccount(AccountReceipt(profile.accountId, "dev_synthetic", profile.expiresAt),
        "vericlue.media.synthetic", "manual_full_demo", policy)

    @Test fun acceptedSessionRequiresTheRequestedUsernameAndMethod() {
        assertTrue(Rules.sessionValid(session, "password", " Synthetic.User ", now = now))
        assertFalse(Rules.sessionValid(session, "password", "different.user", now = now))
        assertFalse(Rules.sessionValid(session, "face", binding = binding, now = now))
        assertFalse(Rules.sessionValid(session.copy(authenticationMethod = "unknown"), "unknown", now = now))
    }

    @Test fun tokenAndAccountExpiryAreEnforcedAtTheExactBoundary() {
        assertFalse(Rules.sessionValid(session.copy(expiresAt = now.toString()), "password", now = now))
        assertFalse(Rules.sessionValid(session.copy(expiresAt = "not-a-date"), "password", now = now))
        assertFalse(Rules.sessionValid(session.copy(expiresAt = "2026-11-05T10:00:00Z"), "password", now = now))
        assertFalse(Rules.profileValid(profile.copy(expiresAt = now.toString()), now))
        assertFalse(Rules.profileValid(profile.copy(createdAt = "2026-11-03T11:00:00Z"), now))
        assertFalse(Rules.profileValid(profile.copy(createdAt = profile.expiresAt), now))
    }

    @Test fun malformedTokenOrUnmaskedIdentityIsRejected() {
        for (token in listOf("", "token", "vca_" + "x".repeat(42), "vca_" + "x".repeat(44), "vca_" + "/".repeat(43))) {
            assertFalse(Rules.sessionValid(session.copy(accessToken = token), "password", now = now))
        }
        assertFalse(Rules.profileValid(profile.copy(accountId = "account_1"), now))
        assertFalse(Rules.profileValid(profile.copy(maskedIdNumber = "001099001234"), now))
        assertFalse(Rules.profileValid(profile.copy(fullName = "x".repeat(201)), now))
        assertTrue(Rules.profileValid(profile.copy(fullName = null, maskedIdNumber = null), now))
    }

    @Test fun faceRequiresMatchingStoredAccountAndExactEvaluationBinding() {
        val face = session.copy(authenticationMethod = "face")
        assertTrue(Rules.sessionValid(face, "face", binding = binding, now = now))
        assertFalse(Rules.sessionValid(face, "face", now = now))
        assertFalse(Rules.sessionValid(face, "face", binding = binding.copy(receipt = binding.receipt.copy(accountId = "acct_" + "c".repeat(32))), now = now))
        assertFalse(Rules.sessionValid(face, "face", binding = binding.copy(demoPolicyId = "c".repeat(64)), now = now))
        assertFalse(Rules.sessionValid(face, "face", binding = binding.copy(evaluationMode = "standard", demoPolicyId = null), now = now))
        assertFalse(Rules.sessionValid(face, "face", binding = binding.copy(evaluationMode = null, demoPolicyId = null), now = now))
    }

    @Test fun faceBindingCannotExpireWhileTheScanWasInProgress() {
        val face = session.copy(authenticationMethod = "face")
        assertFalse(Rules.sessionValid(face, "face", binding = binding.copy(receipt = binding.receipt.copy(expiresAt = now.toString())), now = now))
        assertFalse(Rules.sessionValid(face, "face", binding = binding.copy(receipt = binding.receipt.copy(expiresAt = "not-a-date")), now = now))
    }

    @Test fun modesCannotPretendToBeCalibratedOrDropTheirPolicy() {
        assertFalse(Rules.profileValid(profile.copy(evaluationMode = "standard"), now))
        assertTrue(Rules.profileValid(profile.copy(evaluationMode = "standard", demoPolicyId = null), now))
        assertFalse(Rules.profileValid(profile.copy(demoPolicyId = null), now))
        assertFalse(Rules.profileValid(profile.copy(demoPolicyId = "invalid"), now))
        assertFalse(Rules.profileValid(profile.copy(evaluationMode = "mock"), now))
    }

    @Test fun refreshCannotReplaceAccountUsernameOrPolicySilently() {
        assertTrue(Rules.sameProfile(profile, profile.copy(fullName = "Corrected Display Name")))
        assertFalse(Rules.sameProfile(profile, profile.copy(accountId = "acct_" + "c".repeat(32))))
        assertFalse(Rules.sameProfile(profile, profile.copy(username = "different.user")))
        assertFalse(Rules.sameProfile(profile, profile.copy(demoPolicyId = "c".repeat(64))))
        assertFalse(Rules.sameProfile(profile, profile.copy(evaluationMode = "standard", demoPolicyId = null)))
    }

    @Test fun usernameValidationAndUnicodePasswordLengthFollowContract() {
        assertEquals("synthetic.user", Rules.username(" Synthetic.User "))
        for (valid in listOf("abc", "a.b_c-d", "a".repeat(32))) assertTrue(Rules.validUsername(valid))
        for (invalid in listOf("ab", "AUser", "_user", "a user", "tên.user", "a".repeat(33))) assertFalse(Rules.validUsername(invalid))
        assertFalse(Rules.validPassword("x".repeat(11)))
        assertTrue(Rules.validPassword("x".repeat(12)))
        assertTrue(Rules.validPassword("x".repeat(128)))
        assertFalse(Rules.validPassword("x".repeat(129)))
        // JSON Schema counts Unicode code points, not UTF-16 storage units.
        assertFalse(Rules.validPassword("\uD83D\uDD11".repeat(6)))
        assertTrue(Rules.validPassword("\uD83D\uDD11".repeat(12)))
    }

    @Test fun errorsNeverExposeUnknownBackendDetailOrCredentials() {
        val message = Rules.error(ApiResult.Err(ApiError.Server, "private_token_or_password"))
        assertFalse(message.contains("private_token_or_password"))
        assertTrue(Rules.error(ApiResult.Err(ApiError.BadResponse, "account_setup_required")).contains("khuôn mặt"))
        assertTrue(Rules.error(ApiResult.Err(ApiError.BadResponse, "account_access_locked")).contains("chờ"))
    }
}
