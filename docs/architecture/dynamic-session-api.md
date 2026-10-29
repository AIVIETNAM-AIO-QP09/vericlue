# API luồng xác minh và gói thử thách — FLOW-01 / LIVE-01

## Trạng thái

Backend đã có gói thử thách, ràng buộc mã lượt, luật quyết định theo `purpose` và
kiểm thử xuyên suốt bằng mock. **Luồng có `purpose` hiện chỉ chạy khi
`USE_MOCK_MODELS=true`**. Real/mixed trả `503 flow_unavailable`, kể cả với phiên
mock đã lưu trước khi chuyển cấu hình. Không có cờ để bỏ qua chốt này.

Đây chưa phải luồng đăng ký tài khoản hoàn chỉnh. OTP mô phỏng, QR/OCR và so
CCCD–selfie bằng LVFace-B đã có đường opt-in; xem
[`identity-integration.md`](../runbooks/identity-integration.md). Chọn/kiểm ảnh chính
diện từ video, nối đo ánh mắt/quay đầu, chiều sâu, liên tục cùng một người, mẫu đăng
ký, khóa thiết bị và chữ ký media vẫn còn ở FLOW-03…05, LIVE-02/03, SEC-02.
`reference_image_id` là điểm nối; chưa có resolver
ảnh và chưa được dùng để kết luận đúng người. Không nhận đường dẫn/URL từ client.

Luồng MVP hiện tại không gửi body vẫn hoạt động như trước. Chỉ file type API
được sinh lại trong `apps/web`; không sửa giao diện, camera, nội dung hay tương tác.

## Tạo phiên

```http
POST /v1/sessions
Content-Type: application/json
X-Mock-Scenario: genuine

{"purpose":"onboarding","nonce":"integration_nonce_12345678"}
```

- `purpose`: `onboarding`, `reauth`, `recovery`.
- `nonce`: 16–128 ký tự trong `A-Z a-z 0-9 _ -`, do bên tích hợp cấp để đối chiếu.
  Đây không phải bằng chứng thiết bị hay cơ chế chống phát lại media. Cùng nonce
  vẫn tạo các phiên/gói mới, không phải khóa idempotency.
- `reference_image_id` tùy chọn: `ref_…`, mã ảnh do server quản lý trong tương lai.
- Body lạ hoặc có `device_verified` bị từ chối 422. Client không thể tự xác nhận
  khóa thiết bị, điểm mô hình hay danh tính đã được kiểm tra.
- Phản hồi thêm `purpose`, `nonce`. `challenge.dynamic` chỉ xuất hiện với
  `onboarding` và `recovery`.

Với `reauth`, client chỉ thu hình thụ động, **không phát màu/đường chấm/quay đầu**.
`challenge` vẫn giữ vỏ màu của MVP để tương thích kiểu dữ liệu, nhưng không phải
lệnh trình diễn ở luồng này; dùng `purpose` để chọn cách thu hình. Khóa thiết bị
chưa được kiểm thì kết quả là `recovery_required`.

Nguồn hợp đồng: `packages/contracts/schemas/session.schema.json`, OpenAPI và
type sinh trong `apps/web/src/lib/api/schema.d.ts`. Đây là thay đổi `[contract]`
đã được giao cùng FLOW-01/LIVE-01. Client cũ không gửi body không gặp các trạng thái mới.

## Lịch thu hình

Mọi `at_ms` tính từ **đầu bản ghi phần khuôn mặt**, không phải đồng hồ server.
Client bắt đầu ghi sau khi đã căn khung; dùng đồng hồ đơn điệu để chạy lịch.

| Phần | Lệnh server cấp |
|---|---|
| Nền xám | Chụp chính diện tại `frontal_capture_at_ms`, trước khi đổi màu |
| Ánh sáng | `baseline_ms`, `color_sequence`, `capture_at_ms` của challenge |
| Ánh mắt | 8 `gaze_points` chuẩn hóa theo kích thước vùng hiển thị; nội suy tuyến tính giữa các điểm, tổng 7 giây |
| Quay đầu | `head_start_at_ms`, `head_duration_ms=6000`, trái/phải ngẫu nhiên rồi về giữa |
| Đọc câu | `voice_start_at_ms`, `voice_prompt`, `voice_challenge_id` đã có ngay từ lúc tạo phiên |

Chuỗi màu giữ nguyên 8 bước và cấu hình an toàn dùng chung. Tổng thời gian là tổng
thời lượng thực trong gói, không ép thành con số ước lượng 18 giây trong ADR.
Tọa độ mắt dùng hệ quy chiếu màn hình, **không tự đảo theo ảnh camera gương**.
Server tương lai phải chuẩn hóa tọa độ mắt đo được sang cùng hệ trước khi so.

Câu đọc mới ghép 4 từ tiếng Việt và 6 chữ số viết thành tiếng bằng CSPRNG, thay vì
chỉ chọn giữa 5 câu ghi âm cố định của MVP. Độ dài/độ dễ đọc và độ chính xác ASR
còn phải đo trên người thật; chưa cam kết thời gian đọc hay khả năng chống giọng AI.

Gói thử thách dùng `SystemRandom`/`secrets`. Có mã phiên, nonce bên tích hợp,
challenge ID 128 bit và mã lần đọc riêng. Gói chỉ mô tả việc phải làm, không chứng
minh người dùng đã làm đúng.

## Gửi dữ liệu và nhận kết quả

Mọi bước gửi `Authorization: Bearer <token>`:

1. `POST /v1/sessions/{id}/media`: multipart `image`, `video` tùy chọn,
   **`challenge_id`** của lượt hiện tại. Thiếu/sai ID bị chặn trước khi lưu file.
2. `POST …/signals`: JSON có `color_events`, `frame_times`, **`challenge_id`**.
   Tín hiệu client chỉ để tham khảo; không được biến thành bằng chứng người thật.
3. `POST …/finalize`: JSON **`{"challenge_id":"ch_…"}`**. Phải nhận đủ media
   và signals. Trong khi request này chấm mặt, client đã có thể bắt đầu **thu âm**
   theo lịch. Không cần chờ phản hồi mới biết câu đọc.
4. Nếu trả `voice_challenge`, đối chiếu prompt/ID server trả rồi gửi `POST …/voice`:
   multipart `audio`, `video` tùy chọn, **`voice_challenge_id`**.
   Không gửi voice trước khi finalize cho phép. Đây là ghi âm song song ở client;
   backend hiện chưa nhận/lưu voice đồng thời với inference mặt, chưa có job nền.
5. Kết quả cuối: pass hoặc review với đăng ký/khôi phục. UI chỉ hiển thị thông
   báo phù hợp, không điểm số hay nguyên nhân an ninh.

Ảnh ba góc, video chia đoạn, chữ ký và các số đo mới chưa thêm ở lô này. Không coi
upload `image` đơn lẻ là đủ để chấm toàn bộ Dynamic Liveness ở chế độ thật.

## Luật và làm lại

| Luồng | Luật |
|---|---|
| Không có body | Giữ nguyên MVP: mặt đạt có thể pass; vùng giữa mới đọc câu |
| `onboarding` | Mặt rõ đạt → pass (ghi danh tại `finalize`, biên nhận qua `GET .../account`); vùng giữa → đọc câu; lỗi bắt buộc/nghi rõ → review. Cập nhật 26/10, ADR-0016 |
| `recovery` | Mặt đạt vẫn phải đọc câu; lỗi bắt buộc/nghi rõ chuyển review; giọng không thể xóa quyết định review của mặt |
| `reauth` | Khóa chưa được server xác minh → `recovery_required`; khi có xác minh thật, mặt rõ đạt → pass, vùng giữa → đọc câu, nghi/lỗi → deny; không mở ca nhân viên |

Hiện SEC-02 chưa có, nên reauth qua HTTP luôn `recovery_required`, **không giả vờ
thiết bị đã được xác minh**. Các nhánh có thiết bị hợp lệ được kiểm bằng unit test
của chính sách; chưa tuyên bố đã xác thực khóa thiết bị đầu–cuối.

- Chất lượng chưa đạt: tối đa 2 lần chụp lại theo cấu hình hiện có. Mỗi lần trả
  `retry` cấp cả gói mới; xóa tham chiếu media, signals, kết quả của lượt cũ.
- Đọc sai câu: được đọc lại 1 lần; prompt và mã lần đọc đều thay. Bản ghi của câu
  trước không được gửi lại bằng mã cũ.
- Hết hạn, sai phiên/lượt, thiếu mã, gửi trùng hoặc phiên đã đóng: 409. Token sai/hết hạn: 401.
- Mã lượt được kiểm với snapshot dưới khóa hàng PostgreSQL. SQLite test không
  thay thế bảo đảm khóa đồng thời của PostgreSQL.
- Media của ca `deny`/`recovery_required` không vào bàn duyệt được dọn theo
  `MEDIA_TTL_INCOMPLETE_HOURS` (mặc định 24 giờ); không để trạng thái mới thoát TTL.
- **Mã lượt không phải chữ ký media.** Ai có token vẫn có thể gắn mã mới vào media
  cũ; LIVE-03/SEC-02 và các detector phải kiểm việc đó. Không tuyên bố đã chống
  phát lại video chỉ bằng so mã.

## Trước khi bật thật

Nối từng detector thật với mock cùng giao diện `ModuleResult`, kiểm ảnh tham chiếu,
ánh mắt, quay đầu, liên tục danh tính, chữ ký và nonce thiết bị. Router phải bắt
buộc các mô-đun tương ứng. Chỉ bỏ chốt 503 sau khi có kiểm thử thiếu/lỗi từng lớp
và đã kiểm trên đầu vào thật. Không bỏ chốt chỉ vì trọng số đã tải xong.
