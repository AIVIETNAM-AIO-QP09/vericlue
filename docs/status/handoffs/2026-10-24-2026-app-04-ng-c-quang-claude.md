# Bàn giao · APP-04 · Ngọc Quang+Claude · 2026-10-24 20:26

**Nhánh:** `feat/APP-04-short-onboarding`
**Trạng thái task sau phiên này:** doing (luồng gọn đã chạy hết trên máy ảo với API mock 25/10; chưa thử trên điện thoại thật)

## Đã xong
- **Bản vẽ:** Figma trang "Đề xuất · Luồng gọn" (`kKEiRjXMCNDPVeupHsUn1H`, page `2122:27`). Thêm 2 màn CCCD theo ý Quang: `2125:659` (vừa chụp, dừng 1 nhịp rồi sang mặt sau) và `2125:715` (xem lại 2 mặt trên 1 màn). Sửa chú thích và số màn ở hàng đề xuất.
- **App Android, luồng đăng ký gọn** (Quang duyệt 24/10):
  - Điều khoản và đồng ý từng mục gộp thành 1 màn (`TermsScreen`); nút cần đọc hết, tích điều khoản và tích mục bắt buộc (`Agreement.canContinueWith`). Không tích sẵn mục nào.
  - Bỏ màn Giới thiệu và Xin quyền. Danh sách chuẩn bị chuyển vào màn chào (`AuthScreen`). Camera xin lúc mở camera (CCCD hoặc căn mặt), micro xin ở bước đọc câu. Từ chối micro thì ra màn "Chưa cho micro".
  - CCCD tự chụp khi 2 khung liền nhau đủ nét, không lóa **và thấy chữ của thẻ** (`IdAutoCapture`, `CardText`: ML Kit đọc chữ ngầm khoảng 0,7 s một lần, trên bản chép thu nhỏ); lấy mẫu mỗi 0,5 s sau 1,5 s đầu; vẫn có nút chụp. Chụp xong, ảnh đứng yên 1,5 s kèm nút "Chụp lại mặt …", rồi tự sang mặt sau. Một màn xem lại cả 2 mặt (`IdReviewScreen`), chụp lại từng mặt thì quay về màn này.
  - Màn Kiểm tra thông tin dời ra sau phần khuôn mặt (`FlowRules.afterFace` / `afterConfirm` / `afterIdReview`). Video giữ trên máy; bấm "Thông tin đúng" xong mới sang màn "Đang gửi" (media → signals → `finalize`). Thử lại sau `retry` không hiện lại màn xác nhận. Đứng ở màn này mà bấm quay lại thì hỏi dừng, không quay lại camera.
  - **25/10, Quang chốt:** bỏ gửi video song song lúc người dùng đọc màn xác nhận (bản đầu có `LiveFlow.uploadFace`, đã gỡ). Lý do: server nhánh `feat/FLOW-05-identity-lab` mà team SW dùng để kiểm thử trả 409 `step_not_allowed` cho `id-card/confirm` và cho ảnh CCCD mới khi phiên đã nhận media.
  - OTP tự điền từ `simulated_sms` (bản demo) hoặc từ SMS thật qua SMS User Consent API (`ui/SmsConsent.kt`, thư viện `play-services-auth-api-phone` 18.1.0, không cần quyền SMS). Bàn phím vẫn gõ tay được.
- **25/10, sửa sau khi chạy máy ảo** (commit `6b7204c` và sau đó):
  - Nút chụp tay không ăn: vòng tự chụp ghi đè yêu cầu khung của nút. Nay hai bên dùng chung một khung (`CameraSession.captureId`).
  - Tự chụp bắt cả cảnh phòng khách không có thẻ. Nay cần thấy chữ của CCCD (`CardText`). Đọc chữ trên máy ảo mất 8–10 giây mỗi lần, nên chạy ngầm trên bản chép, không giữ khung camera.
  - Chụp tay ảnh mờ/lóa không còn báo "Ảnh rõ". Server trả `retry` vì không đọc được QR thì màn camera nói lý do.
  - Đứng ở màn xác nhận quá lâu làm thử thách hết hạn (`media` bị 409 `challenge_expired`, trước đây ra màn "Tạm thời chưa thể xác minh"). Nay ra màn "Lượt quay đã hết thời gian" (`Routes.FaceExpired`): giữ giấy tờ, chỉ làm lại phần mặt với thử thách mới, không hỏi lại màn xác nhận.
  - Bản debug có nút "Dùng mã QR mẫu (debug)" ở màn xem lại (dữ liệu giả như `IdCardTest`), vì camera máy ảo không đọc được QR. Bản release không có.
- **Gộp `main` sau PR #65 (FLOW-05)** (commit `11c4068`): giữ luồng gọn và luật FLOW-05 (không dùng dữ liệu mẫu khi thiếu trường, cho sửa số CCCD, `validIdentityValues`, thiếu ảnh/thông tin thì quay về chụp thẻ). Lỗi 422 `identity_incomplete` khi xác nhận giờ quay về màn sửa kèm lý do (`FlowRules.confirmErrorText`), thay vì màn lỗi chung. 503 `identity_unavailable` vẫn ra màn "Dịch vụ không đáp ứng".
- `apps/android/docs/can-chot.md` thêm nhóm H (câu 27–30). `apps/android/README.md` và `apps/ios/docs/plan-ios.md` ghi luồng mới.

## Đang dở
- Chưa thử trên điện thoại thật; chưa chạy với runtime identity lab thật (`IDENTITY_LAB_URL`, cần file `best.pt` trên Drive, Quang chưa đồng ý tải).
- **Tự chụp chưa kiểm được trên máy ảo:** cảnh ảo không có thẻ nên chỉ kiểm được là nó *không* chụp nhầm. Từ khóa trong `CardText` và ngưỡng `MIN_SHARPNESS`/`MAX_GLARE` phải chỉnh trên thẻ thật.

## Bước tiếp theo
1. Push 3 commit mới lên PR #69 (chưa push, chờ Quang bảo) và xem CI.
2. Trên điện thoại thật: chỉnh `MIN_SHARPNESS`/`MAX_GLARE` cho tự chụp, kiểm **mã QR nằm ở mặt nào** của CCCD gắn chip (thẻ thật có QR ở mặt trước; app đang nhắc "đọc QR" ở mặt sau, nhưng chuỗi QR quét được ở mặt nào cũng được giữ và gửi).
3. Chờ trưởng nhóm trả lời can-chot câu 27–29 rồi mới bỏ số điện thoại/OTP, gộp màn "Chuẩn bị", hay đổi luật đọc câu.

## Quyết định, lưu ý, bẫy
- **Thứ tự bắt buộc:** `id-card/confirm` → media → signals → `finalize`. Trên `main`, `finalize` có thể mở ca duyệt và đóng phiên (xác nhận sau đó bị `session_closed`, ca mất ghi chú "sửa khác QR"). Trên nhánh FLOW-05, xác nhận hoặc gửi lại ảnh CCCD sau media đều bị 409; `_identity_gate` cũng cần `id_confirmed` trước `finalize` mới cho đạt.
- **Hết hạn:** thử thách màu sống 120 giây (`challenge_ttl_seconds`), tính từ lúc lấy ở màn căn mặt; trên máy ảo phần mặt mất khoảng 29 giây. Quá hạn thì app cho làm lại phần mặt (xem trên); chỉ áp dụng khi server **chưa** nhận media.
- **Chạy máy ảo:** mở máy ảo với `-camera-back virtualscene` (camera sau có hình), API mock theo README (Windows: `DATABASE_URL=sqlite:///D:/vericlue/tmp/dev.db`, không dùng `$PWD` của Git Bash). Máy ảo hay treo khi build Gradle cùng lúc; treo thì tắt `qemu-system-x86_64` rồi mở lại.
- Không đổi hợp đồng, server, ADR. Bỏ số điện thoại/OTP, gộp màn "Chuẩn bị", đọc câu chỉ khi cần: **chưa làm**, chờ duyệt (can-chot H).
- `apps/ios/docs/plan-ios.md` ghi "Khôi phục: bỏ bước CCCD", nhưng app Android (`FlowRules.afterOtp`) vẫn cho luồng khôi phục chụp CCCD. Phiên này không sửa chỗ lệch đó.

## Câu hỏi cho nhóm
- can-chot.md câu 27 (bỏ số điện thoại/OTP khi ngân hàng đã xác minh số), 28 (gộp màn "Chuẩn bị quay mặt"), 29 (đọc câu chỉ khi server yêu cầu: hiện ngược #49 và ADR-0016), 30 (báo cho FLOW-03: thứ tự confirm trước finalize).

## Test đã chạy
```
cd apps/android && ./gradlew --no-daemon testDebugUnitTest assembleDebug
BUILD SUCCESSFUL — 77 test, 0 lỗi (Windows 11, JDK 17, 25/10, sau khi gộp main #65); test mới:
  FlowRulesTest (afterFace/afterConfirm/afterIdReview, OtpRules.codeIn, Agreement.canContinueWith, confirmErrorText),
  IdCardTest (autoCaptureNeedsTwoGoodFramesInARow, cardWordsAreFoundWithOrWithoutDiacritics),
  LiveFlowRetryTest.expiredChallengeBeforeAnyUploadRedoesOnlyTheFacePart, IdentityCorrectionTest (từ FLOW-05)
./gradlew recordPaparazziDebug --tests '*ScreensSnapshotTest*'  → đã xem 02_terms, 14_id_front_captured, 15_id_review, 16_confirm_after_face
```

Máy ảo Pixel x86_64, API mock của `main` sau #65 (`USE_MOCK_MODELS=true`, không bật `IDENTITY_LAB_URL`), 25/10. Chụp CCCD bằng tay, QR mẫu bằng nút debug, mặt bằng "Chụp ngay (debug)":

| Kịch bản | Kết quả | Thứ tự gọi API (log server) |
|---|---|---|
| `genuine` | Đọc câu → thành công → "Mở tài khoản thành công" | otp → otp/verify → id-card → challenge → **id-card/confirm → media → signals → finalize** → voice |
| `low_quality` | Chụp lại 2 lần (lần sau không hiện lại màn xác nhận) → hết lượt → "Hồ sơ đang được xác minh thêm" | … confirm → media → signals → finalize → challenge → media → signals → finalize → challenge → … |
| `voice_clone` | Đọc câu → "Hồ sơ đang được xác minh thêm" | như `genuine` |
| `genuine`, chờ 110 s ở màn xác nhận | "Lượt quay đã hết thời gian" → làm lại phần mặt → đọc câu → thành công | … confirm → media **409** → challenge → media → signals → finalize → voice |

Cũng thấy đúng: điều khoản phải kéo hết và tích mục bắt buộc mới bật nút; OTP tự điền từ SMS mô phỏng; hộp xin quyền camera hiện lúc mở camera CCCD, micro lúc đọc câu; màn xem lại viền cam khi ảnh lóa; không tự chụp nhầm cảnh không có thẻ sau khi thêm `CardText`.
