# Contracts — hợp đồng giữa các phần

LIVE-05 thêm `private_credential.schema.json` cho trao đổi giữa ba vai trò trong
lab BBS/SD-JWT độc lập, không thêm endpoint công dân. Assurance/header bắt buộc
synthetic-demo; offer không có holder secret. Producer/consumer Node cùng kiểm
schema trước crypto. Vector public BBS không chứa khóa bí mật; xem
[`services/credentials`](../../services/credentials/README.md).

FOR-04 thêm `PdfReportManifest` trong forensic.schema.json và endpoint ZIP
`/v1/forensic/jobs/{id}/report-bundle`. Artifact có PDF, JSON chuẩn hóa và chữ ký
tách rời; schema định nghĩa snapshot job, key ID, hash PDF và giới hạn bắt buộc.
Producer và CLI dùng cùng model/kiểm contract. Xem
[`forensic-pdf-bundle.md`](../../docs/architecture/forensic-pdf-bundle.md).

PLAT-06 ký HTML giám định: `/v1/forensic/signing-key` dùng lại `SigningKey`,
verify giữ shape body và giới hạn chữ ký 160 ký tự. MOCK không được verify là
chữ ký thật; header mới chỉ thuật toán/fingerprint. Xem
[`forensic-report-signing.md`](../../docs/architecture/forensic-report-signing.md).

PLAT-06 đánh dấu `StaffBearer` cho mọi operation review/forensic trong OpenAPI,
kèm lỗi 401/503. Yêu cầu bearer độc lập với cờ riêng tư và mock; token phiên
không thay credential nhân viên. Không đổi body schema. Chi tiết:
[`services/api/README.md`](../../services/api/README.md#truy-cập-nhân-viên-plat-06).

PLAT-06/FLOW-01 thêm `result.schema.json`: envelope Ed25519/claims và khóa công
khai cho bên tích hợp. Dùng bearer của phiên để đọc kết quả đã commit, không
nhận payload client để ký. Xem
[`signed-session-results.md`](../../docs/architecture/signed-session-results.md).

FLOW-05/SEC-02 bổ sung account_id/device_id cho tạo phiên, device_challenge,
device-proof và receipt theo bearer phiên. VoiceResponse có account sau hoàn
tất ghi danh/khôi phục; không trả template hoặc public key. ACK L0 chỉ xác nhận
khóa, không phải verdict sinh trắc. Chi tiết:
[`account-authentication.md`](../../docs/architecture/account-authentication.md).

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

FLOW-05 thêm module `face_continuity` và `DetectorInput.reference_video` nội bộ:
so khung chính diện đã duyệt với ba mẫu video đọc câu, kết quả/ngưỡng riêng với
`face_match`. Không nhận đường dẫn hay kết quả tham chiếu từ HTTP; response người
dân không đổi. Xem [`face-voice-continuity.md`](../../docs/architecture/face-voice-continuity.md).

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

FOR-04 thêm `review_case_id` tùy chọn trong multipart tạo job; `review_audit`
tùy chọn trong ForensicJob (và JSON đã ký) gồm case/session/role/hash nguồn và
count/ID/hash cuối nhật ký. Job độc lập không có mốc. Source hash phải khớp
file_sha256, server kiểm lại khi chuẩn hóa ký/xác minh. Thêm request/response
`ReviewAuditVerify*` cho `/v1/forensic/review-audit/verify`: chỉ scope JSON có chữ
ký và nhật ký, không xác minh byte PDF. Kiểm PDF đầy đủ vẫn dùng verifier gói.
Xem [thiết kế](../../docs/architecture/forensic-review-audit.md).

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
