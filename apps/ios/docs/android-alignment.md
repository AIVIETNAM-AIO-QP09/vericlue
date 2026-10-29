# Đồng bộ iOS với Android — baseline và phạm vi

## Nền đối chiếu hiện hành — cập nhật 28/10/2026

Đã fetch `upstream/main`, khóa nguồn đánh giá tại
`24895c31e07f3d8f7351d828b2e6c7fc51ba664f` (merge PR #103,
28/10/2026 09:52:52 +0700). Bản đọc riêng ở
`/Users/mac/Desktop/project/vericlue-upstream-main`, detached HEAD cùng commit,
worktree sạch khi kiểm tra. Đây là nền **tham chiếu** mới, không phải đã merge
vào nhánh iOS. Các mục ghi f034fa9 dưới đây là lịch sử đối chiếu trước đó.

Đánh giá tĩnh có giới hạn: Android flow/UI/theme/API, phần backend/contract liên
quan và đối chiếu iOS đang sửa. Chưa chạy build/test hay nghiệm thu thiết bị trong
lượt đánh giá này; không kết luận toàn bộ upstream ổn định chỉ từ việc đã merge.
Graph chưa có index, dùng đọc source và git diff thay thế.

### Kết quả ảnh hưởng tới iOS

- Luồng gọn, auto-capture, review hai mặt, confirm sau quay mặt và theme ấm vẫn
  là hướng tham chiếu. Delta Android từ f034fa9 không thay những phần này.
- Android đã bỏ `data/AccountStore.kt`, `boundAccount`, tự lấy/lưu receipt trên
  màn success. Model/API receipt và `fetchAccountReceipt()` vẫn còn. Không xóa
  Keychain iOS chỉ để giống Android: đây là phần độc lập sếp đã yêu cầu, không
  dùng để xác thực hoặc thay device proof. Không còn mô tả Android hiện hành
  là đã tự lưu receipt.
- `Flow.kt.afterOtp` Android vẫn cho recovery qua CCCD, trái mục 1 plan-ios.
  Giữ quyết định iOS recovery bỏ CCCD; không tự đổi theo source mâu thuẫn.
- Backend upstream `IdentitySteps.send_otp` vẫn reset attempts mỗi lần resend.
  Giữ chính sách sếp chốt tổng 5 lần sai trong phiên ở bản sửa local; khi tích
  hợp backend mới phải port/review riêng thay đổi này, không chỉ giữ số UI.
- Android có nhánh ký media/device proof nhưng không đủ căn cứ coi đăng nhập
  lại qua UI đã hoàn chỉnh: Auth không truyền receipt, trong khi ensureSession
  yêu cầu account và signer cho reauth. Không sao chép nhánh này như luồng đã
  nghiệm thu hoặc mở rộng scope iOS sang ký thiết bị ngầm.
- Consent vẫn ghi nội dung mẫu/chờ nhóm và pháp chế; mục lưu CCCD là tùy chọn.
  Giữ nhãn demo và phân loại đã chốt, không tuyên bố nội dung đã được duyệt.
- Contract `session.schema.json` và `signals.schema.json` không đổi giữa
  f034fa9 và mốc mới. OpenAPI có phần credential/BBS mới; đây không phải receipt
  tài khoản hay điều kiện phải thêm vào UI iOS. Không tự port holder/BBS.
- Backend vẫn nêu luồng purpose thật/mixed bị chặn và account enrollment opt-in;
  upstream mới không tự giải quyết bằng chứng GET account 200 còn thiếu.

### Thứ tự tiếp tục

1. Nghiệm thu lại camera sau/QR/Home của chặng 3 trên bản iPhone mới nhất.
2. Chặng 4: tách đóng file khỏi upload; chủ sở hữu payload/deadline/challenge
   rõ ràng; confirm trước media/signals/finalize; giữ retry/ack/cleanup IOS-06.
3. Chặng 5: port semantic token/component/màn từ Theme.kt hiện hành, không đổi
   lịch màu, clock, tọa độ hoặc thuật toán thu.
4. Build từng chặng; viết test nhưng chỉ chạy khi sếp yêu cầu. Sau đó nghiệm thu
   lại luồng bị ảnh hưởng, review và chia PR. Chưa chuyển sang cổng 8.

Không merge/reset/stash nhánh hiện tại, không đổi project.pbxproj hoặc IP/API
Debug của sếp để thực hiện việc đối chiếu này.

## 0. Chặng chuẩn bị — hoàn tất ngày 28/10/2026

- Nhánh làm việc: `feat/IOS-02-android-alignment`, tạo từ IOS-06
  `6aef3acadb3fca994c046b0ee079d02162958520`.
- Android tham chiếu: `feat/APP-01-account-flow`, khóa tại
  `f034fa9406ea9aef1ee86365ce82142de517d553`. Đọc bằng `git show`/`git grep`,
  không checkout hoặc merge nhánh Android vào iOS.
- Worktree sạch trước khi tạo nhánh; không có chỉnh sửa người dùng bị giấu/stash.
- Ngoại lệ Info.plist đã khôi phục. Blob của project ở baseline và trên đĩa:
  `3757f703fa286597f132a254105c3ace82decb68`.
- Chặng 0 chỉ tạo nhánh, kiểm nguồn và tài liệu. Chưa triển khai chức năng,
  build/test, commit/push hoặc tạo PR. Các chặng dưới là mục tiêu, không phải
  mô tả chức năng đã hoàn tất.

## 1. Quyết định phạm vi đã được sếp chốt

1. Recovery **bỏ CCCD theo tài liệu**. Android tại bản tham chiếu vẫn chỉ cho
   reauth bỏ CCCD (`Flow.kt:afterOtp`); không sao chép phần mâu thuẫn này.
2. Làm receipt riêng trước; không thêm ký media, khóa thiết bị hoặc device proof.
3. Không dùng receipt như thông tin xác thực. Không tuyên bố đăng nhập lại thật
   đã hoàn tất khi chưa có khóa/ký và backend hỗ trợ.
4. Giữ lại camera/timeline/giọng và các luật retry/ack của IOS-06.
5. Không sửa backend, contracts, thresholds, ADR hoặc STATUS. Không merge nguyên
   main chỉ để lấy API mới. Nếu cần tích hợp nguồn contract/backend mới, phải
   tách bước phối hợp và kiểm lại diff/test liên quan.
6. Viết/cập nhật test khi triển khai; build sau từng chặng. Chỉ chạy test khi sếp
   yêu cầu. Không dùng kết quả IOS-06 cũ để tuyên bố code đồng bộ mới đã xanh.
7. PR mô tả trong chat theo yêu cầu sếp, không tạo file nháp PR Markdown.

## 2. Bảng đối chiếu màn và route

| Phần | iOS baseline | Android tham chiếu | Mục tiêu iOS |
|---|---|---|---|
| Điều khoản/đồng ý | terms → consent, một số ô chọn sẵn | một TermsScreen, không chọn sẵn | một màn, chọn từng mục, điều kiện bắt buộc theo bản nhóm duyệt |
| Giới thiệu/quyền | intro → permission riêng | không nằm trong luồng chính | bỏ hai màn khỏi luồng chính; xin quyền lúc cần |
| OTP | SMS mô phỏng, gõ tay, deadline resend | thêm điền autoCode | tự điền hợp lệ, vẫn sửa tay; không tự verify |
| Chụp CCCD | nút chụp và review từng mặt | auto + nút tay, dừng một nhịp | auto kiểm chất lượng/nội dung thẻ, không chụp trùng; giữ nút tay |
| Review | id_front_review/id_back_review | id_review hai mặt | một màn hai ảnh, retake từng mặt giữ mặt còn lại |
| Sau /id-card | confirm | face_ready | lưu fields/draft, tới chuẩn bị mặt, chưa confirm |
| Sau quay mặt | finishAndSubmit gửi ngay | giữ video, tới confirm nếu cần | hoàn tất file/evidence; chờ confirm ở onboarding |
| Sau confirm | face_ready | uploading | upload payload cùng lượt nếu còn hợp lệ |
| Kết quả | pass → success; voice_challenge → voice | cùng quy tắc | giữ nguyên quyết định từ server, không suy diễn điểm/nghi ngờ ở client |
| Receipt | chưa có model/API/storage | receiptAfterPass + AccountStore | chặng riêng, không tự xác thực tài khoản |
| Theme | trắng/xanh cũ | trắng ngà/navy/cam, VC, pill | đồng bộ token, component và màn; không thay lịch capture |

Các route `consent`, `intro`, `permission` và review cũ chỉ xóa sau khi kiểm hết
caller/Gallery/test. Không để demo và live đi hai sơ đồ mâu thuẫn.

## 3. Luồng đích theo purpose

### Onboarding

Ngân hàng → chào/auth → điều khoản và đồng ý → điện thoại → OTP → CCCD trước
→ CCCD sau → review hai mặt → chuẩn bị/căn mặt → quay xong, đóng file
→ kiểm tra/sửa thông tin → POST id-card/confirm → media → signals → finalize.

- pass: thành công, không đọc câu; lấy receipt theo khả năng server.
- voice_challenge: đọc đúng prompt/ID từ server, gửi voice, theo status.
- retry/review/deny/lỗi: giữ điều hướng an toàn như IOS-06.

### Recovery — quyết định khác code Android

Auth → điện thoại → OTP → chuẩn bị/căn mặt → quay → media → signals → finalize
→ giọng theo response server → kết quả. Không gọi /id-card hoặc /id-card/confirm,
không đòi fields giả. Server phải thực thi quy tắc recovery cần giọng; client
không tự tạo prompt/ID hoặc tự bỏ qua bước. Nếu có mâu thuẫn response/contract,
ghi câu hỏi, không ép thành công.

### Reauth

Giữ thu thụ động và điều hướng theo server, không có CCCD. Chưa nối receipt để
bỏ qua device proof. Account-bound reauth/recovery thực tế vẫn bị backend bản
tham chiếu chặn bước sinh trắc bằng 503; không tuyên bố luồng thật hoạt động.

## 4. Hợp đồng receipt đã đối chiếu (chỉ đọc)

Nguồn khóa tại `f034fa9`:

- `packages/contracts/schemas/session.schema.json`, `$defs.AccountReceipt`.
- `packages/contracts/openapi.json`, GET `/v1/sessions/{session_id}/account`.
- `apps/android/app/src/main/java/vn/vericlue/app/data/api/Api.kt`.
- `apps/android/app/src/main/java/vn/vericlue/app/flow/LiveFlow.kt`.

| Field | Schema nguồn | Hướng port |
|---|---|---|
| account_id | string bắt buộc, `^acct_[0-9a-f]{32}$` | accountId; không dùng giá trị mẫu như tài khoản thật |
| device_id | string bắt buộc, `^dev_[0-9a-f]{32}$` | deviceId; không coi nó thay cho bằng chứng khóa |
| expires_at | string bắt buộc, date-time | expiresAt, kiểm hết hạn khi load |
| account trong VoiceResponse | tùy chọn, tham chiếu AccountReceipt | không làm response giọng cũ decode thất bại khi vắng field |

GET account gửi Bearer token và Cache-Control no-store; 200 trả receipt.
OpenAPI nguồn khai báo 401/409/422/503: xử lý lỗi, không tạo receipt giả.
Sau pass: dùng account response nếu có, nếu chưa có thì GET account. Lỗi lấy
receipt không đổi kết quả sinh trắc đã pass và không tự chạy lại sinh trắc.
Chỉ lưu receipt, không lưu session token/media; quyết định kho lưu iOS ở
chặng 1: Keychain riêng, không đưa khóa ký thiết bị vào scope.

**Lệch phiên bản hiện hữu:** contract và API backend trên nhánh IOS-06 baseline
chưa có AccountReceipt/GET account (đã tìm trong contracts và API source).
Chưa copy/schema-update bất kỳ file nào. Chặng 1 phải nêu rõ nguồn contract và
phụ thuộc backend tương thích; MockURLProtocol test không chứng minh server
local đã có endpoint. Không thể nghiệm thu receipt thật chỉ bằng API mock cũ.

## 5. Thứ tự triển khai và checkpoint

| Chặng | Công việc | Điểm đạt |
|---|---|---|
| 0 | baseline, nhánh, bảng đối chiếu, khóa scope/contract | hoàn tất trong tài liệu này; không đổi chức năng |
| 1 | model/API/storage receipt và test riêng | receipt thiếu/hỏng/hết hạn an toàn; không ký thiết bị, không tài khoản giả |
| 2 | Terms gộp, route, quyền tại chỗ, OTP | ba purpose đúng sơ đồ; recovery không CCCD; build |
| 3 | CCCD auto + review chung | auto/manual không đua, background hủy tác vụ, giữ mặt khi retake; build + thử iPhone |
| 4 | payload chờ confirm, upload tách khỏi thu | đúng confirm → media → signals → finalize; hết hạn không tái dùng video cũ; build |
| 5 | theme và màn | light/dark/font lớn/Reduce Motion; không ảnh hưởng clock/màu/chấm; build |
| Cuối | test khi sếp yêu cầu, nghiệm thu phần thay đổi, review, bàn giao/PR | không dùng mốc xanh cũ làm bằng chứng cho code mới |

Tham chiếu auto-capture Android: CardText kiểm chữ thẻ, IdAutoCapture cần hai mẫu
liên tiếp tốt; delay đầu 1.500ms, lấy mẫu cách 500ms, giữ ảnh 1.500ms. Đây là
tham số nguồn, không phải số đo iPhone; không thay ngưỡng chất lượng để dễ qua.

Phần payload cần chủ sở hữu rõ, file đã đóng và JPEG/signals/challenge ID của
cùng lượt. onDisappear chuyển sang confirm không được xóa nhầm. Phải phân biệt
challenge hết hạn và session hết hạn; không gửi video cũ với challenge mới.
Back/Home/mất mạng/late reply và callback dọn file đều phải giữ invariant IOS-06.

## 6. File dự kiến bị ảnh hưởng

- Receipt: `Data/Models.swift`, `Data/SessionApi.swift`, `Flow/LiveFlow.swift`,
  lớp lưu receipt mới và test (chưa tạo trong chặng 0).
- Luồng: `Flow/Routes.swift`, `Flow/FlowRules.swift`, `Flow/DemoFlow.swift`,
  `Flow/IdentityFlow.swift`, `UI/AppNavigation.swift`, `UI/Screens/RouteScreen.swift`.
- CCCD: `Capture/CameraSession.swift`, `Capture/IdCard.swift`,
  `UI/Screens/LiveIdentityScreens.swift` và các màn demo tương ứng.
- Payload chờ: `Flow/FaceCaptureFlow.swift`, màn face/confirm/edit và expiry policy.
- Giao diện: `UI/Theme.swift`, `UI/Components/Components.swift`, StartScreens,
  IdentityScreens, VoiceResultScreens; thêm asset VC theo hệ thống vector hiện có.
- Test: route/consent/OTP, auto-capture, hai mặt/retake, thứ tự request,
  confirm lỗi mạng, expiry, retry/ack, receipt và UI Gallery/Back/vùng bấm.

Tất cả đường dẫn trên tính từ `apps/ios/VeriClue/`, trừ test ở `apps/ios/VeriClueTests/`
và `apps/ios/VeriClueUITests/`. Không sửa project.pbxproj nếu không cần thiết.

## 7. Phân PR, bằng chứng và giới hạn

1. Receipt riêng (IOS-02, nhánh hiện tại).
2. Luồng gọn/CCCD (IOS-01/03), nhánh riêng khi triển khai.
3. Confirm sau mặt và hồi quy IOS-06, nhánh riêng khi triển khai.
4. Theme (IOS-01), nhánh riêng khi triển khai.

Không tạo mã task mới, không đánh dấu task cũ done chỉ vì chặng 0 hoàn tất.
Các PR cũ giữ độc lập. Không tự merge/rebase/force-push hoặc tích hợp main.
IOS-06 từng đạt 105/105 ở baseline; chặng 0 không chạy test nên không phát sinh
bằng chứng test mới. Cổng 8 chỉ làm sau khi luồng/UI mục tiêu ổn định.

## 8. Tiến độ chặng 1 — 28/10/2026

Đã nối receipt độc lập: model, GET Bearer/no-store, optional account trong voice,
thu thập sau pass và kho Keychain qua actor riêng. Có 19 hàm test mới dùng mock,
đã chạy xanh cả hai suite receipt cùng unit bundle. Một lượt toàn bộ test đạt
123/124; sau đó kiểm lại riêng UI `testDebugGalleryOpens` đạt 1/1, không sửa assertion.
Không coi đây là một lượt mới toàn bộ 124 bài xanh; GET 200 receipt thật vẫn chờ
môi trường ghi danh hợp lệ, mock không có account đủ điều kiện.
Build Simulator và Release iPhone không ký thành công. Không đổi camera, thứ tự CCCD, theme,
device proof hoặc project.pbxproj. Không tuyên bố đăng nhập lại thật đã xong.

Xem [thiết kế và giới hạn receipt](account-receipt.md),
[bàn giao chặng 1](../../../docs/status/handoffs/2026-10-28-0413-ios-02-l-anh-qu-n-codex.md).

## 9. Checkpoint chặng 2–3 — 28/10/2026

Đã nối màn Terms/consent chung không chọn sẵn, loại route consent/intro/permission,
OTP tự điền hợp lệ nhưng chỉ verify khi bấm; giữ luật resend/attempts/chống trùng.
Recovery bỏ CCCD theo quyết định sếp, khác Android ref. Nội dung consent vẫn demo;
sếp chấp nhận phân loại Android, không tuyên bố nhóm/pháp chế đã duyệt.

CCCD có sample output riêng trên session camera sau, Vision đọc chữ/QR và quality,
auto-gate unit-test được, nút tay cùng chốt claim, pause và hủy theo lifecycle.
Một route id_review, retake giữ mặt còn lại và thay capture ID để không tái dùng
ảnh đang giữ của màn cũ. `/id-card` giữ fields/draft, chưa gọi confirm.

**Dừng đúng checkpoint:** onboarding face_ready hiển thị màn dừng sau nhận CCCD,
không đi vào pipeline upload cũ trước confirm. Chưa làm chặng 4/5; demo vẫn dùng
confirm cũ trước mặt tới khi chặng 4 được triển khai. Chưa nghiệm thu end-to-end
luồng đích, chưa chạy test mới. Xem [checklist](compact-flow-device-checklist.md).
Receipt/chặng 2–3 còn chung dirty worktree; chưa commit/stash/tách PR tự động.

**Sửa QR sau đối chiếu Android:** QR lấy từ cả hai ảnh, ưu tiên back hợp định dạng
rồi front hợp định dạng. Bỏ QR riêng khỏi gate auto/quality mỗi mặt. Local không
đọc được hoặc server QR_INVALID: giữ review và hai ảnh, cho chọn retake mặt chứa
QR; không ép chụp lại mặt sau như bản iOS trước. Test đã cập nhật, chưa chạy;
checkpoint iPhone chưa được coi là đạt.

## 10. Cấu trúc iOS đối chiếu Android

Rà và refactor theo upstream/main `24895c3` ngày 28/10/2026. Thay đổi tổ chức,
không thay luồng nghiệp vụ hoặc thuật toán thu; không merge upstream vào nhánh.

| Android nguồn | iOS hiện hành | Trách nhiệm |
|---|---|---|
| `MainActivity.kt` | `VeriClueApp.swift`, `ContentView.swift` | entry point của nền tảng |
| `data/api/Api.kt` | `Data/API/Models.swift`, `SessionApi.swift`, `MultipartBody.swift` | DTO/codec, HTTP và multipart |
| API không kiêm kho lưu | `Data/AccountStore.swift` | receipt Keychain riêng, không xác thực |
| `flow/Flow.kt` | `Flow/FlowTypes.swift`, `Routes.swift`, `FlowRules.swift`, `ConsentPolicy.swift` | domain types, route, policy thuần |
| `flow/LiveFlow.kt` | `Flow/LiveFlow.swift` | phiên/token, challenge, API orchestration, ack/retry |
| trạng thái trong `ui/App.kt` | `Flow/DemoFlow.swift`, `IdentityFlow.swift` | demo và draft/OTP/CCCD |
| điều phối thu trong `ui/App.kt` | `Flow/CaptureFlows.swift`, `FaceCaptureFlow.swift`, `VoiceCaptureFlow.swift` | lifecycle, quyền, expiry, file/recorder ownership |
| NavHost trong `ui/App.kt` | `UI/App.swift`, `AppRoutes.swift`, `AppNavigation.swift` | composition root, nối route với màn, navigation path |
| Gallery trong `ui/App.kt` | `UI/Debug/GalleryScreen.swift` | công cụ demo/checkpoint, chỉ Debug |
| `ui/theme/Theme.kt` | `UI/Theme/Theme.swift` | token/font/theme (giá trị theme ấm chưa port) |
| `ui/components`, `ui/screens` | `UI/Components`, `UI/Screens` | thành phần dùng lại và màn hình |
| `capture/*` | `Capture/*` | camera/Vision/writer/audio/clock/signals native |

Các đường dẫn iOS trong bảng tính từ `apps/ios/VeriClue`; các file cùng nhóm
ngắn gọn sau dấu phẩy nằm trong thư mục của file đầu. Swift cùng app module,
không cần thêm import giữa các nhóm. Xcode dùng filesystem-synchronized group,
không sửa project.pbxproj hoặc ngoại lệ Info.plist khi chuyển file.

Không gom toàn bộ flow vào App.swift chỉ để giống một file Compose: camera,
async finish, cancellation và cleanup của iOS vẫn có lớp sở hữu riêng.
Không chuyển API call vào screen; screen gọi flow, flow gọi SessionApi.
Các tên public/internal type và entry point AppNavigationView giữ nguyên để
không đổi caller/test trong lượt refactor này.

### Kiểm chứng refactor

- Đối chiếu text sau khi ghép lại các phần tách (bỏ import): AppNavigation +
  CaptureFlows + App, AppRoutes + Gallery, FlowTypes + DemoFlow giống trước tách.
- Các file API/theme chuyển nguyên nội dung; không thay JSON, endpoint, token,
  timeout, màu, timeline, state machine hoặc ngưỡng.
- Build Simulator/test bundle và Release iPhone không ký: kết quả ghi trong
  bàn giao cấu trúc. Build-for-testing không thực thi test.
- Không có logic mới cần mở rộng assertion trong lượt này; giữ bộ test đang có
  và compile qua build-for-testing. Chưa có bằng chứng runtime mới.

Phần bảng/file ở các mục trước có đường dẫn cũ là lịch sử kế hoạch. Dùng bảng
mục này và cây thư mục mục 6 plan-ios.md cho source hiện hành. Confirm sau mặt,
theme ấm và nghiệm thu camera vẫn đang dở, không được đánh dấu xong vì đổi cấu trúc.

## 11. Chặng 4 — confirm sau quay mặt (đã chốt xanh)

**Kết luận mới nhất sau sửa:** chốt chặng 4 xanh: 148/148 bài, 0 lỗi/0 bỏ qua
(174/174 lần thực thi tính tham số), Simulator iPhone 17 Pro iOS 26.3.1.
Result `/tmp/vericlue-ios-stage4-final-tests.GT5ZbJ/FullRun.xcresult`.
Sếp đã báo A/B/C/D đạt, DB confirm đã đối chiếu. IOS-03 chuyển review, không done
hoặc đã merge. Lịch sử 145/148 và 147/148 bên dưới/bàn giao không bị viết lại.

**Kết quả cập nhật:** đã chạy đúng một lượt test theo yêu cầu mới: 145/148 đạt,
3 lỗi (guard file mất trước confirm, assertion OTP policy cũ, UI consent).
Chưa sửa/chạy lại/chốt xanh. Sếp xác nhận A/B/C/D và dữ liệu DB confirm đã kiểm;
chi tiết trong bàn giao chặng 4. Các dòng “chưa thực thi” dưới đây là mốc trước đó.

Nguồn đối chiếu main mới nhất đã fetch `a54d093` (PR #104). Delta so với 24895c3
chủ yếu runtime BBS, không đổi Android/luồng confirm. Không merge nguồn này.

- Sếp đã xác nhận 4 ca camera sau của chặng 3 đạt. Đây là điều kiện bắt đầu,
  không phải nghiệm thu code chặng 4 hoặc toàn bộ test mới.
- FaceCaptureFlow tách finishCapture và submit; sau đóng/inspect writer giữ URL
  cùng JPEG/signals/probe/events, không nạp toàn bộ MP4 trong lúc chờ chỉnh sửa.
- FaceAttemptBinding giữ đúng phiên/token/challenge/deadline tại prepare, kiểm
  trước confirm và submit. Đổi binding/hết challenge → face_expired; hết session
  → error_session. File thiếu/rỗng cũng không được confirm/upload như bản thu tốt.
- Onboarding chưa confirm → confirm/edit, API confirm ack rồi mới media/signals/
  finalize. Recovery/reauth không đòi fields. idCardConfirmed tồn tại qua retry
  mặt, không bắt confirm lại nếu thẻ chưa thay đổi; reset ở phiên/thẻ mới.
- Home ở confirm/edit giữ bản thu đã đóng đến deadline, không tự gửi; Back ở
  confirm hỏi dừng, Back ở edit chỉ về confirm. Retake CCCD từ edit bỏ evidence
  mặt cũ. Chuyển mặt → confirm không gọi cleanup nhầm.
- Media ack dọn MP4; network retry còn signals/finalize không đòi file đã xóa,
  không gửi lại media. Không tạo cơ chế suy pass khi mất finalize response.
- Demo cũng review → face → confirm; Gallery vẫn chỉ Debug. Chưa đổi theme.
- Test PendingFaceCaptureTests dùng dữ liệu tổng hợp/MockURLProtocol, cùng các
  test cũ được compile; chưa thực thi. Bằng chứng build và giới hạn trong
  [bàn giao chặng 4](../../../docs/status/handoffs/2026-10-28-1106-ios-03-l-anh-qu-n-codex.md).

Nghiệm thu tiếp theo: [checklist chặng 4](post-face-confirm-device-checklist.md).
Các đoạn “chưa nối chặng 4” ở mục lịch sử trên mô tả mốc cũ, không phải trạng thái
source hiện tại. Không thay bằng chứng runtime/test bằng build thành công.

## 12. Chặng 5 — theme ấm, Simulator và nghiệm thu iPhone

Đã port palette Android trong `UI/Theme/Theme.swift`, primary pill 56 pt,
Be Vietnam Pro, logo VC native Path, welcome/success và nhãn tài khoản mẫu.
Screen dùng ScrollView để hỗ trợ chữ lớn; banner/list giảm viền. Token dark
riêng và màu onPrimary tránh chữ trắng trên nút sáng. Reduce Motion chỉ tắt
animation trang trí, camera không nhận press/progress animation mới.

Nguồn vừa fetch: upstream/main `caf4469`. Theme Android không đổi so với
`a54d093`; phần account/device proof mới không được gộp vào chặng theme.
Không merge upstream hoặc thay cấu hình Xcode/API của sếp.

**Kết luận source cuối 28/10 17:23:** toàn bộ **159/159 bài, 186/186 lần thực thi
tính tham số**, 0 lỗi/0 bỏ qua, iPhone 17 Pro Simulator iOS 26.3.1. Bundle
`/tmp/vericlue-ios-theme-final-20261028.xcresult`. Release không ký exit 0.
Demo/Gallery dùng projected Binding trực tiếp, API thật giữ adapter Back chốt
capture. UI test qua 12 vòng native Back Terms → Gallery, OTP nhập sai/đúng và
cuộn đủ trường confirm ở AX3. Confirm demo dùng cùng component màn thật;
keypad AX giữ số lớn và bỏ ABC phụ, không giảm cỡ chữ để ép vừa màn.
28 ảnh cuối export, đã xem các ảnh trọng tâm OTP/confirm AX3 và VC dark; lịch
sử 24 ảnh đầu, 0/1 và 156/159 được giữ trong bàn giao, không xóa lỗi từng gặp.

Capture/Flow/Data khớp SHA256 trước theme. Không sửa màu flash, timeline,
tọa độ, contract hoặc timeout. Kết quả cũ 148/148 chỉ là lịch sử chặng 4.

Ngày 28/10/2026, **sếp xác nhận iPhone A–D trên bản mới nhất đều đạt**: theme/
Back/chữ lớn; CCCD auto/manual/retake/Home; quay → sửa/confirm/offline/retry/
thứ tự API; Home/Back/Dừng/file tạm 0. Đây là báo cáo nghiệm thu thủ công của
sếp, không phải agent tự chạy trên iPhone. Không thêm số đo/log hoặc model/iOS
chưa xác nhận lại. Chặng 5 chuyển review, còn commit/push/PR review/merge,
không coi receipt thật/device proof đã xong. Xem
[checklist theme](warm-theme-device-checklist.md); chi tiết kết quả/giới hạn ở
[bàn giao](../../../docs/status/handoffs/2026-10-28-1608-ios-01-l-anh-qu-n-codex.md).
