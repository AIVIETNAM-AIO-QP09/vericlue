# Contracts — hợp đồng giữa các phần

Đây là **nguồn sự thật** cho dữ liệu đi qua lại giữa web, API và bộ não AI. Nhờ có hợp đồng cố định, 5 người (và nhiều AI) làm song song mà không lệch nhau.

| File | Dùng cho |
|---|---|
| `schemas/module_result.schema.json` | Kết quả của MỌI bộ phát hiện |
| `schemas/detector_input.schema.json` | Đầu vào nội bộ API → ML; đường dẫn do server kiểm soát, không phải body HTTP |
| `schemas/face_template.schema.json` | Artifact ML → API nội bộ: vector chỉ lưu mã hóa, không nhận/trả qua HTTP |
| `schemas/session.schema.json` | API phiên eKYC: tạo phiên, tín hiệu, kết quả (API v1, chốt ở PLAT-04) |
| `schemas/review.schema.json` | Bàn duyệt. **Draft v1**: chỉ thêm trường tùy chọn. `ReviewCase` không có điểm AI; `ReviewAiOpinion` tách riêng |
| `schemas/forensic.schema.json` | Cổng giám định. **Draft v1**: chỉ thêm trường tùy chọn |
| `chromapulse.json` | **File cấu hình** (không phải JSON Schema): bảng màu, nhịp và giới hạn an toàn của ChromaPulse. Nguồn duy nhất cho API (`challenge.py`) và web (trang lab, CAP-04); test ở cả hai phía kiểm điều đó và kiểm các giới hạn ADR-0011 |
| `examples/` | Ví dụ JSON hợp lệ, tên `<schema>.<Def>[.<biến thể>].json` (`Def` là khóa trong `$defs`); test: `services/api/tests/test_contract_examples.py` |

## Quy tắc

SEC-02 thêm tùy chọn `CreateSessionRequest.device_public_key_spki`,
`Challenge.media_nonce` và multipart `media_signature` ở mặt/giọng. Phiên đã
ràng buộc public key bắt buộc ký cả hai bước. Định dạng ký và mẫu đối chiếu
Python/Kotlin: [`media-proof.md`](../../docs/architecture/media-proof.md),
`test-vectors/media-proof-v1.json`. Không cấp `device_verified` từ public key tự gửi.

SEC-01 thêm `ReviewIdentity` và hai endpoint review xem che/mở đầy đủ. Khi bật
`SESSION_PRIVACY`, dùng `StaffBearer` độc lập với token người dân; chỉ xem đầy đủ
qua thao tác reveal có nhật ký. Không thêm PII/điểm vào `ReviewCase` hay phản hồi
người dân. Chi tiết: [`session-privacy.md`](../../docs/architecture/session-privacy.md).

LIVE-02 thêm tên module `gaze_tracking` vào ModuleResult để diagnostic và mock
cùng trả đúng hợp đồng. Đây không phải thay đổi trạng thái cho người dân, không
tự bật mô-đun trong full/MVP hoặc bỏ chốt chế độ thật của luồng mới.

FLOW-04/FLOW-05 thêm `head_turn`, `face_match` theo cùng cách diagnostic.
`DetectorInput.image_roles` gán front/left/right cho từng ảnh, `reference_image`
là chân dung tham chiếu đã cắt do server quản lý. Các đường dẫn và nhãn góc này
không được lấy trực tiếp từ JSON/signals của client. Chưa có endpoint nhận
đường dẫn; chưa tự bật quyết định API hay thêm điểm số cho người dân.

1. **Đổi schema trước, code sau**, cả hai phía trong **cùng một PR**. Tiêu đề PR có `[contract]`.
2. Chỉ **thêm** trường tùy chọn thì không phá tương thích. **Đổi tên / xóa / đổi kiểu** thì phải tăng phiên bản API (`/v2`) hoặc báo cả nhóm.
3. Phía Python sinh model Pydantic từ schema; phía TypeScript sinh type từ OpenAPI của FastAPI (task PLAT-04).
4. Không ai tự thêm trường "tạm" ngoài schema.

## Token, lượt và thử thách (ADR-0011)

**FLOW-01/LIVE-01 (24/10):** Tạo phiên có body `CreateSessionRequest` là opt-in
cho `purpose`/`nonce`; chưa gửi body vẫn giữ MVP. Gói `challenge.dynamic` chứa
lịch ánh mắt, quay đầu và câu đọc từ trước. Luồng mới cần mã lượt ở media,
signals, finalize và mã lần đọc ở voice; chỉ hỗ trợ mock hiện tại. Trạng thái
`deny`/`recovery_required` dành cho bên tích hợp dùng reauth; không hiển thị lý
do an ninh cho người dân. Xem
[`dynamic-session-api.md`](../../docs/architecture/dynamic-session-api.md).

- Token **theo phiên**, gửi `Authorization: Bearer` ở mọi lần gọi của phiên. Sai/hết hạn → 401.
- **Lượt = một challenge.** Mỗi bước (media, signals, finalize, voice) chỉ nhận một lần trong một lượt, gọi lại → 409. `finalize` trả `retry` hoặc `voice_challenge` thì mở lượt mới; đọc lại câu tối đa 1 lần.
- Challenge sống 120 giây (`challenge.expires_at`), tách khỏi hạn của token (`expires_at` ở gốc phản hồi). Khi `finalize` trả `retry`, phản hồi kèm `challenge` mới.
- **409** có hai nghĩa: (a) bước đã nhận trong lượt này (chống phát lại, **PLAT-06** cài); (b) sai thứ tự luồng, đã cài ở PLAT-04: `voice_not_requested` (gọi `/voice` khi `finalize` chưa trả `voice_challenge`) và `session_closed` (phiên đã vào bàn duyệt, không nhận thêm `finalize`/`voice`).
- PLAT-04 khai báo hợp đồng và kiểm thứ tự luồng; PLAT-06 cài HMAC, TTL, 429 và máy trạng thái "mỗi bước một lần mỗi lượt".
