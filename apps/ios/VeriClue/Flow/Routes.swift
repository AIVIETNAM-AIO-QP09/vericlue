import Foundation

enum Route: String, CaseIterable, Hashable, Identifiable {
    case bankStart = "bank_start"
    case bankOpened = "bank_opened"
    case gallery
    case splash
    case auth
    case terms
    case consent
    case intro
    case permission
    case phone
    case otp
    case otpError = "otp_error"
    case idFront = "id_front"
    case idFrontGlare = "id_front_glare"
    case idFrontReview = "id_front_review"
    case idBack = "id_back"
    case idBackReview = "id_back_review"
    case confirm
    case editInfo = "edit_info"
    case faceReady = "face_ready"
    case framing
    case holdStill = "hold_still"
    case turnHead = "turn_head"
    case voice
    case voiceAgain = "voice_again"
    case uploading
    case uploadFailed = "upload_failed"
    case checking
    case slow
    case success
    case review
    case retryQuality = "retry_quality"
    case retryChallenge = "retry_challenge"
    case errorCamera = "error_camera"
    case errorMic = "error_mic"
    case errorNetwork = "error_network"
    case errorSession = "error_session"
    case errorService = "error_service"
    case errorDevice = "error_device"
    case interrupted
    case noVoice = "no_voice"
    case exitConfirm = "exit_confirm"
    case stopped
    case flashSkipped = "flash_skipped"
    case deny
    case recoveryRequired = "recovery_required"

    var id: String { rawValue }
}
