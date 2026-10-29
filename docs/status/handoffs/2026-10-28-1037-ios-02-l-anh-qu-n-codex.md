# Bàn giao · IOS-02 · Lý Anh Quân+Codex · 2026-10-28 10:37

**Nhánh:** `feat/IOS-02-android-alignment`, HEAD `6aef3ac`; thay đổi chưa commit.
**Trạng thái task sau phiên này:** doing

## Đã xong

- Rà cấu trúc iOS đang sửa với Android upstream/main `24895c31e07f3d8f7351d828b2e6c7fc51ba664f`.
- Chuyển nguyên nội dung model/client/multipart sang `Data/API`, theme sang `UI/Theme`.
- Tách composition root sang `UI/App.swift`, route composition sang `UI/AppRoutes.swift`,
  Gallery chỉ Debug sang `UI/Debug/GalleryScreen.swift`.
- `UI/AppNavigation.swift` chỉ quản path; lifecycle/expiry/quyền/cleanup chung sang
  `Flow/CaptureFlows.swift`; Purpose/DemoOutcome sang `Flow/FlowTypes.swift`.
- So lại text ghép các phần tách, bỏ import: không đổi thân implementation của
  navigation/capture coordinator/app, routes/gallery hoặc types/demo.
- Cập nhật plan-ios, api-client, android-alignment, task card và dòng IOS-02 backlog.

## Đang dở

- Không có logic mới trong lượt refactor; không tuyên bố đã giống toàn bộ hành vi Android.
- Checkpoint iPhone chặng 3 (camera sau/QR/Home) vẫn chưa nghiệm thu lại sau sửa.
- Chặng 4 confirm sau mặt và chặng 5 theme ấm chưa làm. Onboarding live vẫn dừng
  tại IdentityCardCheckpointScreen theo chính sách bản trung gian, demo vẫn confirm trước mặt.
- GET 200 receipt thật còn thiếu bằng chứng; refactor không giải quyết enrollment.
- Test code hiện hành chưa chạy sau thay đổi chặng 2–3/refactor.

## Bước tiếp theo

1. Thử camera sau trên iPhone trước khi đổi pipeline mặt.
2. Chặng 4: đóng writer, giữ payload cùng challenge/deadline, confirm thành công
   rồi mới media/signals/finalize; bảo toàn token rotation, ack, retry và cleanup.
3. Chặng 5: theme/token/component theo Android; không đổi clock/màu/chấm timeline.
4. Chỉ chạy test khi sếp yêu cầu; review diff và chia PR sau nghiệm thu liên quan.

## Quyết định, lưu ý, bẫy

- Không gom các flow native vào một App.swift lớn như Compose App.kt; giữ chủ sở
  hữu recorder/cancellation riêng. Tương đồng trách nhiệm, không sao chép cơ học.
- Giữ recovery bỏ CCCD, QR cả hai mặt, tổng 5 lần OTP sai/phiên, receipt Keychain
  độc lập; không thêm media/device proof hoặc holder/BBS theo upstream ngầm.
- Không sửa backend trong lượt này. Bản OTP backend local đã sửa từ lượt trước,
  không phải có sẵn trong upstream/main; cần phối hợp khi tích hợp backend mới.
- Không sửa project.pbxproj (blob vẫn `3757f703fa286597f132a254105c3ace82decb68`),
  Debug API vẫn `192.168.1.12:8001`. Không merge/stash/commit/push.
- Git chưa stage nên chuyển file hiện có dạng deleted + untracked. Phải stage cả
  đường dẫn cũ lẫn mới khi chuẩn bị commit; không chỉ stage file deleted.
- Tất cả chỉnh sửa trước lượt này được giữ. Các đường dẫn source cũ trong bàn
  giao lịch sử không bị viết lại; bảng hiện hành nằm ở android-alignment mục 10.

## Câu hỏi cho nhóm

- Không có quyết định phạm vi mới cần để hoàn thành refactor. Các mâu thuẫn
  Android/tài liệu và giới hạn account đã ghi trong android-alignment, vẫn còn.

## Kiểm chứng đã chạy

Không thực thi test, theo yêu cầu sếp. Chỉ build và kiểm tra tài liệu/diff:

```bash
xcodebuild -quiet -project apps/ios/VeriClue.xcodeproj -scheme VeriClue \
  -destination 'generic/platform=iOS Simulator' \
  -derivedDataPath /tmp/vericlue-ios-structure-alignment build-for-testing
xcodebuild -quiet -project apps/ios/VeriClue.xcodeproj -scheme VeriClue \
  -configuration Release -destination 'generic/platform=iOS' \
  -derivedDataPath /tmp/vericlue-ios-structure-alignment-release CODE_SIGNING_ALLOWED=NO build
.venv/bin/python scripts/plan_check.py
git diff --check
```

- Hai build exit 0, không có output lỗi/cảnh báo ở lượt build ngoài sandbox.
- Lượt build sandbox ban đầu exit 65 vì không truy cập được CoreSimulator/asset
  runtime; build lại ngoài sandbox thành công, không sửa code để vượt lỗi này.
- `uv run` bị sandbox chặn cache lock; chạy cùng script bằng Python của .venv:
  exit 0, 0 lỗi/10 cảnh báo tải công việc và chuỗi găng.
- Diff whitespace sạch. Build-for-testing chỉ compile test bundle, không chứng
  minh test pass hoặc lifecycle camera đã nghiệm thu lại.
