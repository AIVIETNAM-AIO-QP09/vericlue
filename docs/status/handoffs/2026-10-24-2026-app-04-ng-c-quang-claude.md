# Bàn giao · APP-04 · Ngọc Quang+Claude · 2026-10-24 20:26

**Nhánh:** `feat/APP-04-short-onboarding`
**Trạng thái task sau phiên này:** doing (luồng gọn đã code, chưa thử trên điện thoại thật)

## Đã xong
- **Bản vẽ:** Figma trang "Đề xuất · Luồng gọn" (`kKEiRjXMCNDPVeupHsUn1H`, page `2122:27`). Thêm 2 màn CCCD theo ý Quang: `2125:659` (vừa chụp, dừng 1 nhịp rồi sang mặt sau) và `2125:715` (xem lại 2 mặt trên 1 màn). Sửa chú thích và số màn ở hàng đề xuất.
- **App Android, luồng đăng ký gọn** (Quang duyệt 24/10):
  - Điều khoản và đồng ý từng mục gộp thành 1 màn (`TermsScreen`); nút cần đọc hết, tích điều khoản và tích mục bắt buộc (`Agreement.canContinueWith`). Không tích sẵn mục nào.
  - Bỏ màn Giới thiệu và Xin quyền. Danh sách chuẩn bị chuyển vào màn chào (`AuthScreen`). Camera xin lúc mở camera (CCCD hoặc căn mặt), micro xin ở bước đọc câu. Từ chối micro thì ra màn "Chưa cho micro".
  - CCCD tự chụp khi 2 khung liền nhau đủ nét và không lóa (`IdAutoCapture`, lấy mẫu mỗi 0,5 s sau 1,5 s đầu); vẫn có nút chụp. Chụp xong, ảnh đứng yên 1,5 s kèm nút "Chụp lại mặt …", rồi tự sang mặt sau. Một màn xem lại cả 2 mặt (`IdReviewScreen`), chụp lại từng mặt thì quay về màn này.
  - Màn Kiểm tra thông tin dời ra sau phần khuôn mặt (`FlowRules.afterFace` / `afterConfirm` / `afterIdReview`). Video giữ trên máy; bấm "Thông tin đúng" xong mới sang màn "Đang gửi" (media → signals → `finalize`). Thử lại sau `retry` không hiện lại màn xác nhận. Đứng ở màn này mà bấm quay lại thì hỏi dừng, không quay lại camera.
  - **25/10, Quang chốt:** bỏ gửi video song song lúc người dùng đọc màn xác nhận (bản đầu có `LiveFlow.uploadFace`, đã gỡ). Lý do: server nhánh `feat/FLOW-05-identity-lab` mà team SW dùng để kiểm thử trả 409 `step_not_allowed` cho `id-card/confirm` và cho ảnh CCCD mới khi phiên đã nhận media.
  - OTP tự điền từ `simulated_sms` (bản demo) hoặc từ SMS thật qua SMS User Consent API (`ui/SmsConsent.kt`, thư viện `play-services-auth-api-phone` 18.1.0, không cần quyền SMS). Bàn phím vẫn gõ tay được.
- `apps/android/docs/can-chot.md` thêm nhóm H (câu 27–30). `apps/android/README.md` và `apps/ios/docs/plan-ios.md` ghi luồng mới.

## Đang dở
- Chưa thử trên máy ảo với API mock và chưa thử trên điện thoại thật. Cần đi lại luồng `genuine`, `low_quality` (retry không hiện lại màn xác nhận) và `voice_clone`.
- Ngưỡng tự chụp (`IdQuality.MIN_SHARPNESS`, `MAX_GLARE`) vẫn là số khởi đầu. Trên bàn trống không có thẻ, ảnh vẫn có thể đủ nét và bị tự chụp; khi đó người dùng thấy ngay ở bước dừng 1 nhịp và ở màn xem lại.

## Bước tiếp theo
1. Chạy API mock theo README, cài APK debug lên máy ảo (`D:\tools\chay-vericlue.cmd`), đi hết luồng đăng ký với `genuine`, `low_quality`, `voice_clone`. Kiểm log server: `id-card/confirm` phải đến trước `finalize`.
2. Trên điện thoại thật: chỉnh `MIN_SHARPNESS`/`MAX_GLARE` cho tự chụp, kiểm **mã QR nằm ở mặt nào** của CCCD gắn chip (thẻ thật có QR ở mặt trước; app đang nhắc "đọc QR" ở mặt sau, nhưng chuỗi QR quét được ở mặt nào cũng được giữ và gửi).
3. Chờ trưởng nhóm trả lời can-chot câu 27–29 rồi mới bỏ số điện thoại/OTP, gộp màn "Chuẩn bị", hay đổi luật đọc câu.

## Quyết định, lưu ý, bẫy
- **Thứ tự bắt buộc:** `id-card/confirm` → media → signals → `finalize`. Trên `main`, `finalize` có thể mở ca duyệt và đóng phiên (xác nhận sau đó bị `session_closed`, ca mất ghi chú "sửa khác QR"). Trên nhánh FLOW-05, xác nhận hoặc gửi lại ảnh CCCD sau media đều bị 409; `_identity_gate` cũng cần `id_confirmed` trước `finalize` mới cho đạt.
- **Rủi ro hết hạn:** thử thách màu sống 120 giây (`challenge_ttl_seconds`), tính từ lúc lấy thử thách ở màn căn mặt. Phần mặt cũng nằm trong 120 giây đó; người dùng sửa thông tin quá lâu thì gửi media bị `challenge_expired` và ra màn lỗi. Chưa xử lý; nếu gặp khi thử thì gọi `POST .../challenge` lấy thử thách mới rồi quay lại phần mặt.
- **Gộp với nhánh FLOW-05:** nhánh đó cũng sửa `App.kt`, `IdentityScreens.kt` (cho sửa số CCCD, `validIdentityValues`, không dùng dữ liệu mẫu khi thiếu trường). Nhánh nào vào `main` sau phải gộp tay và giữ phần kiểm trường của họ.
- Không đổi hợp đồng, server, ADR. Bỏ số điện thoại/OTP, gộp màn "Chuẩn bị", đọc câu chỉ khi cần: **chưa làm**, chờ duyệt (can-chot H).
- `apps/ios/docs/plan-ios.md` ghi "Khôi phục: bỏ bước CCCD", nhưng app Android (`FlowRules.afterOtp`) vẫn cho luồng khôi phục chụp CCCD. Phiên này không sửa chỗ lệch đó.

## Câu hỏi cho nhóm
- can-chot.md câu 27 (bỏ số điện thoại/OTP khi ngân hàng đã xác minh số), 28 (gộp màn "Chuẩn bị quay mặt"), 29 (đọc câu chỉ khi server yêu cầu: hiện ngược #49 và ADR-0016), 30 (báo cho FLOW-03: thứ tự confirm trước finalize).

## Test đã chạy
```
cd apps/android && ./gradlew --no-daemon testDebugUnitTest assembleDebug
BUILD SUCCESSFUL — 71 test, 0 lỗi (Windows 11, JDK 17, chạy lại 25/10 sau khi bỏ gửi song song); có test mới:
  FlowRulesTest (afterFace/afterConfirm/afterIdReview, OtpRules.codeIn, Agreement.canContinueWith),
  IdCardTest.autoCaptureNeedsTwoGoodFramesInARow,
./gradlew recordPaparazziDebug --tests '*ScreensSnapshotTest*'  → đã xem ảnh 02_terms, 14_id_front_captured, 15_id_review, 16_confirm_after_face
Chưa chạy trên máy ảo/điện thoại.
```
