# Bàn giao · IOS-02 · Lý Anh Quân+Codex · 2026-10-28 04:13

**Nhánh:** `feat/IOS-02-android-alignment`
**Trạng thái task sau phiên này:** doing

## Đã xong
- Đã nối receipt độc lập theo contract tại Android ref `f034fa9406ea9aef1ee86365ce82142de517d553`: account_id, device_id, expires_at; kiểm định dạng/ngày và hạn sử dụng.
- GET account có Bearer hiện tại/no-store; voice pass nhận optional account; receipt hỏng không làm mất pass, dùng GET để lấy lại. Lỗi metadata tách khỏi xác minh; retry không gửi lại sinh trắc.
- AccountStore actor dùng Keychain item riêng WhenUnlockedThisDeviceOnly, không đồng bộ iCloud; load/save/clear, xóa corruption/expiry nhưng không xóa vì Keychain bị khóa. Không lưu token/media, không log receipt/token.
- Collector do LiveFlow sở hữu, không phụ thuộc tuổi thọ màn Success; reset hủy request/loại response trễ. Chỉ pass onboarding/recovery; demo/review/reauth không lưu receipt.
- Thêm 19 hàm test với MockURLProtocol/kho RAM: codec, GET, HTTP/network, retry/lỗi storage, voice optional, token rotation và hủy/response trễ. Hai suite receipt đã chạy xanh trong lượt toàn bộ test bên dưới.
- Cập nhật tài liệu API/receipt/kế hoạch/task/backlog. Không sửa camera, navigation, theme, backend/contracts hay project.pbxproj. Số tài khoản mẫu vẫn ghi “Dữ liệu mẫu”.

## Đang dở
- Đã chạy một lượt toàn bộ test theo yêu cầu tiếp theo của sếp: unit bundle xanh, UI có một lỗi timeout tổng hợp thao tác. Probe Keychain trên iPhone đã được sếp xác nhận đạt (bổ sung bên dưới); chưa kiểm chứng GET 200 receipt thật.
- Backend/contracts local tại nền IOS-06 chưa có endpoint/schema receipt. Mock test không chứng minh API local đã hỗ trợ; 404 không được thay bằng receipt giả.
- Không có UI thử lại/xóa receipt mới; API metadata/storage đã tách để tích hợp chặng sau. Chưa nối device proof, không tuyên bố đăng nhập lại thật đã xong.

## Bước tiếp theo
1. Điều tra UI test `testDebugGalleryOpens`: lỗi tổng hợp event bị timeout; chưa đủ căn cứ kết luận là bug app hay môi trường. Không tự chạy thêm lượt.
2. Dùng backend tương thích ref trên để kiểm pass → nhận/lưu receipt; GET lỗi vẫn giữ pass, retry chỉ metadata; thử load/clear/hết hạn trên iPhone. Không ghi receipt/token thật vào log/bàn giao.
3. Review diff, rồi sếp tự commit/push. Luồng gọn/CCCD/theme và device proof không thuộc chặng này.

## Quyết định, lưu ý, bẫy
- Nền iOS HEAD `6aef3acadb3fca994c046b0ee079d02162958520`; thay đổi chặng 0 vẫn trong worktree. Chưa commit/push.
- Reset xóa receipt trong RAM và hủy collector; không xóa receipt hợp lệ đã lưu. Dùng `try await AccountStore.shared.clear()` khi cần xóa item. Không dùng receipt để bỏ qua chứng minh thiết bị.
- Tolerant decode chỉ áp dụng account ancillary của voice; status/core vẫn strict. Unknown receipt fields không được lưu lại; kho chỉ encode ba trường DTO.

## Câu hỏi cho nhóm
- Cần backend tương thích account flow để nghiệm thu receipt tích hợp; không tự merge main hoặc sửa contract/backend trong chặng này.
- Đã đọc điều kiện cấp account ở backend tham chiếu: từ chối mock/mixed, còn cần
  gates/calibration/danh tính/mã hóa/khóa thiết bị. Chạy đúng backend chưa đủ để
  cấp receipt thật. Cần nhóm cung cấp môi trường/phiên đủ điều kiện, không bypass.

## Bổ sung chuẩn bị nghiệm thu iPhone

- Đã dựng worktree detached `f034fa9` tại `tmp/receipt-backend` (ignored), venv riêng,
  SQLite `tmp/receipt-check.db` và media riêng trong worktree. Không đổi DB/backend
  cổng 8000. Script local `tmp/run-receipt-backend.sh` chạy cổng 8001 mock; không cấp
  receipt mẫu. Quota 50/giờ cho kiểm local, không là cấu hình production.
- Smoke HTTP thực tế: health 200; OpenAPI có GET account/AccountReceipt/voice.account;
  tạo phiên tổng hợp có nonce 200; GET thiếu Bearer 401; GET phiên chưa pass 409
  enrollment_not_available. Lần đầu smoke thiếu nonce nhận 422, đã sửa request
  kiểm tra cho đúng contract (không sửa server). Không log token hoặc receipt.
- Thêm probe DEBUG trên Gallery, dùng AccountStore + Keychain service riêng;
  ghi/đọc qua đóng mở app/xóa/corruption/expiry theo mốc giờ. Không thay kho live.
  Chỉ nút đọc kho live có thể dọn item hết hạn/hỏng theo semantics load hiện hữu.
- Build test bundle Simulator và Release iPhone không ký sau khi thêm probe: exit 0.
  Không chạy lại test: kết quả 123/124 bên dưới thuộc bản trước khi bổ sung probe.
  Sau đó sếp xác nhận probe trên iPhone đạt; chưa nhận GET 200 receipt thật.
- Chi tiết: [checklist iPhone](../../../apps/ios/docs/receipt-device-checklist.md).

### Xác nhận nghiệm thu bổ sung — 28/10/2026

Sếp xác nhận cả hai nhóm đạt: (1) probe Keychain ghi → đóng/mở → đọc, xóa và
hỏng/hết hạn; (2) app hiện thành công, sau GET account 409 không quay lại thu mặt/
giọng. Bằng chứng log phiên `ses_5b4ab2550e286be1`: media/signals/finalize 200,
GET account 409; status pass/giữ màn thành công do sếp xác nhận, không suy từ HTTP
200. Agent không trực tiếp quan sát UI. Chưa ghi nhận lại iOS/build cài trên máy
cho lượt này. Không đánh dấu GET 200 receipt thật hoặc đăng nhập lại thật đã xong.

Kiểm tra thêm theo yêu cầu sếp: backend cổng 8001 trả health mock_models=true;
SELECT chỉ đọc đếm accounts=0, sessions pass=1. GET receipt đòi account đã được
ghi danh, trong khi service từ chối mock/mixed. Không thể chạy ca 200 thật bằng
môi trường hiện tại, cần nhóm cung cấp phiên/môi trường ghi danh thật. Không sửa
server/DB hay tạo receipt mẫu; giữ cấu hình Debug cổng 8001 sếp đã đổi.

### Kiểm lại UI theo yêu cầu sếp — 28/10/2026

Chạy đúng một lượt `testDebugGalleryOpens` trên code mới nhất: **1/1 Passed,
0 failed, 0 skipped**, xcodebuild exit 0. Không sửa code/test/assertion. Result
bundle xác nhận iPhone 17 Pro Simulator iOS 26.3.1. Lỗi timeout cũ không tái hiện
trong lượt này; chưa kết luận nguyên nhân timeout và không tuyên bố một lượt mới
toàn bộ 124 test xanh. Kết quả toàn bộ trước đó 123/124 vẫn được giữ lịch sử.

```bash
xcodebuild -quiet -project apps/ios/VeriClue.xcodeproj -scheme VeriClue \
  -destination 'platform=iOS Simulator,id=184BFA1A-7DB0-4CE7-A9BB-1DA25FB36F80' \
  -derivedDataPath /tmp/vericlue-ios-receipt \
  -resultBundlePath /tmp/vericlue-ios-receipt-gallery-recheck-20261028.xcresult \
  -parallel-testing-enabled NO \
  -only-testing:VeriClueUITests/VeriClueUITests/testDebugGalleryOpens test
```

GET 200 receipt thật vẫn chưa kiểm chứng, vì không có account đủ điều kiện trong
môi trường mock. Đã hết lỗi ở lượt UI kiểm lại, không dùng điều đó để đóng phụ
thuộc ghi danh thật hoặc tự thêm device proof vào phạm vi chặng 1.

### Kiểm tra tiếp mức sẵn sàng ghi danh thật — 28/10/2026

Chỉ đọc, không đổi cờ/mô hình/DB hoặc chạy lại test. Graph không có index, đã đọc
nguồn trực tiếp. Trong môi trường backend riêng: torch/onnxruntime/cv2 không có;
Settings không cấu hình identity lab, face/consistency/voice calibration hoặc
session master key; các opt-in face checks/models, voice models, video identity,
consistency, voice continuity và enrollment đều tắt. Không in giá trị bí mật.
DB đếm accounts=0, media_proof_uses=0, device_proof_uses=0.

`AccountStore._validate_biometrics` còn bắt buộc real mode, gates hợp lệ, public
key P-256 và `require_consumed(..., required=True)` cho media của các pha cần
thiết. iOS `CreateSessionRequest` hiện chỉ có purpose/nonce/referenceImageId,
chưa gửi device_public_key_spki. Đây là phần ký media/khóa thiết bị đã tách khỏi
chặng 1; không tự triển khai trong yêu cầu kiểm chứng này. Device proof L0 cho
đăng nhập lại là bước khác, không đồng nhất với chữ ký media khi ghi danh.

Kết luận: không phải lỗi GET đơn lẻ; môi trường và client hiện chưa có đủ điều
kiện sinh account thật. Cần nhóm backend chuẩn bị pipeline thật/phiên đủ điều
kiện và thống nhất phạm vi tích hợp khóa thiết bị/ký media cho iOS. Không tải mô
hình, tự chọn calibration, seed account hoặc hạ chốt để tạo HTTP 200.

## Test đã chạy
Đã build/check và chạy **một lượt toàn bộ test** theo yêu cầu tiếp theo của sếp.
Chưa đạt tiêu chí toàn bộ test xanh: 123/124 test đạt theo summary xcresulttool;
unit bundle và hai suite receipt Passed. Bài UI `testDebugGalleryOpens()` Failed:
`Failed to synthesize event: Timed out while synthesizing event.` Không sửa code,
không nới assertion và không tự chạy lại sau lỗi này. Chưa đủ dữ kiện quy nguyên
nhân cho app hay Simulator.

Thiết bị báo cáo trong result bundle: iPhone 17 Pro Simulator, iOS 26.3.1,
build 23D8133. Summary đếm 124 test (123 pass/1 fail); số lượt có cả tham số là
147 (146 pass/1 fail), không trộn hai cách đếm.

```
xcodebuild -quiet -project apps/ios/VeriClue.xcodeproj -scheme VeriClue \
  -destination 'generic/platform=iOS Simulator' \
  -derivedDataPath /tmp/vericlue-ios-receipt build-for-testing
# exit 0; app + toàn bộ test bundle compile, không thực thi test.

xcodebuild -quiet -project apps/ios/VeriClue.xcodeproj -scheme VeriClue \
  -configuration Release -destination 'generic/platform=iOS' \
  -derivedDataPath /tmp/vericlue-ios-receipt-release CODE_SIGNING_ALLOWED=NO build
# exit 0; không ký/cài trên iPhone, không thay thế nghiệm thu thiết bị.

uv run python scripts/plan_check.py
# exit 0; 0 lỗi, 10 cảnh báo tải công việc/đường găng.

xcodebuild -quiet -project apps/ios/VeriClue.xcodeproj -scheme VeriClue \
  -destination 'platform=iOS Simulator,id=184BFA1A-7DB0-4CE7-A9BB-1DA25FB36F80' \
  -derivedDataPath /tmp/vericlue-ios-receipt \
  -resultBundlePath /tmp/vericlue-ios-receipt-tests-20261028-0421.xcresult \
  -parallel-testing-enabled NO test
# exit 65; 123/124 test pass, một UI timeout. Unit + receipt suite Passed.
```

Hook pre-commit trên đúng 15 file thay đổi: exit 0 (whitespace/EOF/conflict/large
files/private key và hook áp dụng đều qua). Không có SwiftLint trong bộ hook này.
`git diff --check` sạch. Không có diff trong `packages/contracts/`, `services/api/`
hay `apps/ios/VeriClue.xcodeproj/project.pbxproj`. Chỉ thêm source/test/tài liệu,
không thêm receipt/token thật, ảnh, audio/video hoặc DB. Chưa stage file.
