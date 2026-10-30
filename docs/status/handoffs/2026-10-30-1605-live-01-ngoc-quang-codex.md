# Bàn giao · LIVE-01 · Ngoc Quang+Codex · 2026-10-30 16:05

**Nhánh:** codex/APP-01-demo-integration
**Trạng thái task sau phiên này:** doing

## Đã xong
- Theo lựa chọn của người dùng: dynamic v2 quay đầu 12000 ms, mỗi hướng 4000 ms; vẫn nhận v1/6000 cho lượt cũ. Kiểm cặp version/duration và tổng lịch <=30000 ms, voice offset đúng.
- Contract/schema/Pydantic/OpenAPI/examples và type web đồng bộ; bộ sinh phát v2, không đổi màu/nhịp nháy hoặc ngưỡng xác minh.
- ML chọn calibrator theo request/protocol, cache cả trường hợp thiếu theo version; không sửa self.version chung khi request v1/v2 xen kẽ. Collector không gộp protocol. VideoFaceMatch nhiều góc v2 có version riêng, không dùng ngưỡng v1 cho v2.
- Android có đếm ngược và hướng tiếp theo theo mốc server, giữ video liên tục, không thêm delay/TTS/bước tập. Bố cục đo chiều cao và oval giới hạn theo vùng trống chỉ tại màn quay đầu để chữ lớn không chồng lấn; camera capture không thay đổi.
- 45 ảnh trước/sau tại tmp/head-turn-4s/{before,after}; đã xem chữ lớn 200%, compact và các trạng thái trái/giữa. Không commit ảnh vào repo.

## Đang dở
- Chưa có artifact hiệu chỉnh thật đúng protocol v2, chưa nghiệm thu đạt toàn luồng và chưa hoàn thiện SEC-09. Lỗi/degraded vẫn không được đạt; guard ghi danh mock/mixed giữ nguyên.
- iOS hiện kiểm version 1 nên chưa dùng với lịch mới; không sửa iOS trong đợt này.
- Chưa có lượt thử người dùng sau bản 4 giây/hướng; không tuyên bố đã nghiệm thu chuyển động hoặc đạt xác minh.

## Bước tiếp theo
1. Sau cập nhật, tạo phiên mới để nhận v2; phiên v1 cũ vẫn 2 giây/hướng.
2. Giữ điện thoại cố định; đến mỗi hướng quay đầu chậm theo mũi tên và giữ đến hướng dẫn kế tiếp, cuối cùng nhìn thẳng. Chỉ theo chấm bằng mắt trong phần trước đó.
3. Nếu vẫn review, đọc chẩn đoán theo module trước sửa; không mặc định do người dùng và không hạ ngưỡng để ép đạt. Chưa dùng video thử để fit.

## Quyết định, lưu ý, bẫy
- Các regression v2 gom tại ml/tests/test_head_protocol_v2.py và tái dùng fixture tổng hợp; rủi ro coupling fixture được bù bằng chạy suite cũ và mới.
- Unit adapter trước đây mock session_views và bỏ metadata; nay fixture cấp metadata v1 rõ ràng để kiểm chọn protocol trước decode. API test dùng gói v2 đầy đủ do generator phát.
- Paparazzi phát hiện chữ lớn bị chồng; sửa theo layout đo kích thước, mặc định oval các màn khác giữ nguyên. Cần thử thật để đánh giá hướng dẫn, không suy từ ảnh snapshot rằng xác minh sẽ đạt.
- OTP demo, guard, giới hạn video/decoder và các ngưỡng chuyển động không đổi. Không push/PR; không sửa STATUS, ADR hoặc thresholds.yaml.
- Review độc lập phát hiện race trong collector: lịch có thể bị thay sau preflight nhưng trước đo, trộn protocol dù row lỗi. Đã có 4 test đỏ cho thay khi nạp model/đo mẫu trước, cả mẫu thành công/lỗi; sửa bind hash lịch từ preflight, kiểm lại trước/sau từng lượt và trước ghi report. Các test xanh, toàn suite 775/775.

### Các mục review để lại cho phạm vi khác

- Chốt API/template/continuity vẫn từ chối version nhiều góc mới khi chưa đủ bằng chứng: giữ theo thiết kế, chi phí là chưa ghi danh/đăng nhập thật toàn luồng.
- Độ chính xác chuyển động, hướng ảnh gương và UX máy thật: cần người dùng thử bản mới; chi phí là vẫn có thể phải sửa sau lượt thực tế.
- Kiểm tư thế riêng từng đoạn và xác minh chiều sâu: luật cũ được giữ; chi phí là chưa được coi đã chống tấn công chiều sâu.
- Cài APK/restart/handoff: đã kiểm vận hành bên dưới, còn người dùng nghiệm thu; Wi-Fi/cổng reverse có thể cần nối lại khi đổi mạng.
- iOS v2: ngoài phạm vi theo yêu cầu; chi phí là chưa demo iOS bằng server lịch mới.

## Câu hỏi cho nhóm
- Cần bộ dữ liệu đúng protocol và hiệu chỉnh/đánh giá độc lập; kéo dài thời gian không tự giải quyết độ chính xác hoặc bằng chứng chiều sâu.

## Test đã chạy
- Suite Python ML/API/router/contract sau sửa review: 775 test, 0 lỗi/thất bại/bỏ qua (final.xml trong evidence local); có cảnh báo dependency/fixture cũ.
- Android testDebugUnitTest + assembleDebug: 162 test, 0 lỗi/thất bại/bỏ qua; JUnit đã giữ riêng. CitizenCopyTest và ThemeAccessibilityTest nằm trong suite.
- recordPaparazziDebug --tests '*FaceChallengeSnapshotTest*': qua, 45 ảnh before/after; view kiểm đại diện chữ 200%/compact.
- Ruff phần Python thay đổi: sạch; OpenAPI --check khớp; web npm run typecheck qua.
- plan_check.py: 0 lỗi, 10 cảnh báo tải công việc/đường găng hiện có; git diff --check qua.
- SDK apksigner xác nhận APK arm64 debug có v2 signature, signer SHA256 822e5e44be42ce365f186a6c73af5bf36eb262c3cc65011b4269363adc695c75 khớp bản đang cài.

## Bàn giao vận hành đã kiểm

- APK tại D:/vericlue/tmp/full-demo-setup/apk/VeriClue-demo-debug.apk; mã Android 1c4f69ac54e468d0be1340a52e3843b47e89b70c.
- SHA256 a8a44630cd5002e63bda4907821cb24eab1d87af3b0e62c0fa485e36f3d74648. Đã install -r Success trên Samsung SM_A526B qua ADB Wi-Fi; hash base.apk trên máy khớp chính xác. Không gỡ app hoặc xóa Keystore. APK/metadata cũ lưu tại apk/archive-94be648.
- Launcher hiện có đã stop/start server, giữ DB/.env/khóa. Health ok, failed_modules rỗng, mock_models true đúng do OTP demo.
- Smoke HTTP bằng metadata/khóa công khai tổng hợp: nhận version=2, head_duration_ms=12000, mỗi đoạn 4000; voice offset đúng, tổng trong giới hạn 30000; rút phiên synthetic sau thử. Không thu hoặc xuất media người thật.
- ADB reverse tcp:8421 đã nối lại, app đã mở. Bằng chứng local tại D:/vericlue/tmp/full-demo-setup/head-turn-4s/delivery-smoke.json. Người dùng tự bắt đầu lượt mới để nghiệm thu.
