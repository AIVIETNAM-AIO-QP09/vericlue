# Bàn giao nối quyền riêng tư vào app — FLOW-06

Nguồn đối chiếu: main `54acaad` sau PR #105, ngày 28/10/2026.
Tài liệu dành cho người nối logic Android/iOS; **chưa có thay đổi app trong PR
này**. Luồng người dùng và các quyết định ở [workflow](project-workflow.md).
Hợp đồng hiện có: [privacy.schema.json](../../packages/contracts/schemas/privacy.schema.json).

## 1. Ranh giới phải giữ

- App có thể tạo metadata phiên/khóa theo luồng, nhưng chỉ gửi dữ liệu thuộc
  nhóm được người dùng chủ động đồng ý và server đã ghi nhận. Không tự gọi
  `grant` chỉ vì đang chạy ở protected hoặc đã bấm một nút “tiếp tục” khác.
- Giữ chính xác `session_id`, bearer mới nhất, version và tập nhóm được đồng ý.
  Refresh challenge thay bearer; mọi lời gọi privacy sau đó dùng token mới.
- Không suy diễn `face_biometrics` thành đồng ý lưu mẫu cho tài khoản. Theo D1,
  đăng ký cần quyền lưu mẫu, nhưng contract hiện tại chỉ ghi nhóm xử lý theo
  phiên; phải bổ sung hợp đồng/kiểm tra ghi danh trước khi hứa đã thực thi D1.
- Không ánh xạ checkbox lưu ảnh CCCD dài hạn sang `id_document`: nhóm này cho
  xử lý CCCD trong phiên, không tự đặt thời hạn/tùy chọn lưu dữ liệu tài khoản.
- Nội dung/quyền được hiển thị trước thu dữ liệu, không tick sẵn; không biến
  phiên bản mã `demo-v1` thành một thông báo đầy đủ. Backend chưa cấp nội dung
  chính sách hoặc tự xác định pháp nhân/kênh hỗ trợ.

## 2. Model và điểm gọi API hiện có

| Method client cần có | API / body | Dùng khi nào |
|---|---|---|
| Đọc trạng thái | `GET /v1/sessions/{id}/privacy` | Lấy version/trạng thái/biên nhận sau khi có bearer; không trả dữ liệu sinh trắc |
| Ghi đồng ý | `POST .../privacy/consent` với `policy_version`, `categories`, `consent:true` | Sau lựa chọn chủ động, trước lần thu/gửi dữ liệu cần nhóm tương ứng |
| Rút lại | `POST .../privacy/withdraw` với `confirm:true` | Khi người dùng yêu cầu dừng xử lý/xóa kho phiên; có thể gọi lại cùng bearer còn hạn |

Nhóm hiện có: `contact`, `id_document`, `face_biometrics`, `voice_biometrics`.
Model response phải giữ đầy đủ `scope`, trạng thái, version/nhóm, receipt/time,
`storage_erasure`, `processing_cleanup`, `account_data_erased`,
`credential_revocation`. Không rút gọn response thành `deleted=true`.
Unknown enum/response sai hợp đồng thành lỗi rõ ràng, không chuyển thành pass.

Android `SessionApi`/`LiveFlow` hiện chưa có ba method này. SDK web đã có
`sessionPrivacy`, `grantSessionConsent`, `withdrawSessionConsent` để tham khảo
body/type, không phải để gọi thay hoặc sao chép UI web vào mobile.

## 3. Thứ tự tích hợp đăng ký

1. Màn thông báo trả về **lựa chọn cụ thể** và version đã hiển thị. Giữ trong
   bộ nhớ của luồng; callback hiện chỉ điều hướng nên cần thêm dữ liệu đầu ra.
2. Tạo phiên đúng purpose/khóa như hiện có. Có thể thực hiện cùng thao tác
   “tiếp tục” hoặc trước lần gửi dữ liệu đầu tiên; không cần màn tạo phiên riêng.
3. Đọc trạng thái privacy/version; chỉ ghi các lựa chọn khớp version thực sự đã
   xem. Nếu version khác, hiển thị nội dung mới và chờ lựa chọn, không tự đổi mã
   version rồi gửi lại `consent:true`.
4. Có receipt `contact` mới gửi số/OTP; có `id_document` mới nhận/gửi CCCD; có
   `face_biometrics` mới thu/gửi lượt mặt cần xử lý. Có thể ghi nhiều nhóm trong
   một request nếu người dùng đã đồng ý rõ từng mục trên cùng màn.
5. Ghi lựa chọn lưu mẫu theo D1 bằng hợp đồng tương ứng **sau khi hợp đồng đó
   được bổ sung**. Không gửi field/category tự đặt: API hiện chặn thuộc tính lạ.
6. Khi server trả `voice_challenge`, chỉ xin micro/thu âm sau lựa chọn giọng phù
   hợp. Nếu chưa đồng ý giọng, giải thích ngay trong bước đọc câu, ghi bổ sung
   `voice_biometrics` rồi mới thu. Không lặng lẽ dùng consent chung để bật micro.
7. Chỉ báo tạo tài khoản thành công khi có receipt thật và binding/alias lưu
   bền. Không lấy verdict mock, ACK khóa L0 hoặc cấu hình enrollment làm receipt.

Đăng nhập/khôi phục cũng cần lựa chọn phù hợp cho phiên hiện tại; không tự dùng
checkbox của lần đăng ký cho mọi phiên sau. Dữ liệu được dùng lại phải có nhóm
hiện hành: ví dụ mẫu/giọng/CCCD cũ tùy đường xử lý. Việc tự động hóa dựa trên
consent còn hiệu lực ngoài một phiên chưa nằm trong hợp đồng này.

## 4. Rút lại và rời luồng

| Trạng thái client | Hành động | Điều được nói với người dùng |
|---|---|---|
| Yêu cầu rút lại | Dừng camera/micro, không tạo upload mới; hủy task client phù hợp và giữ ngữ cảnh phiên để gọi API | Đang gửi yêu cầu; không khẳng định server đã dừng chỉ vì task HTTP bị hủy |
| Đang chờ / lỗi mạng / `503 storage_busy` | Giữ trạng thái chưa xác nhận; cho retry khi bearer còn hạn; không tự chạy lại xác minh | Chưa xác nhận được yêu cầu; không hiện “đã xóa” |
| Receipt `withdrawn`, `key_destroyed` | Dừng hẳn luồng; chỉ đọc/retry receipt hoặc bắt đầu phiên mới do lựa chọn rõ ràng | Server đã nhận rút lại và hủy khóa kho phiên; file có thể chờ dọn |
| Receipt `files_deleted` | Dọn dữ liệu local của luồng; kết thúc | File nguồn của phiên đã được dọn; plaintext đang xử lý vẫn `not_verified` |
| Bearer sai/cũ/hết hạn | Không thử token khác đoán từ account_id; hướng dẫn bắt đầu lại/hỗ trợ theo thiết kế | Không thể xác nhận xóa sớm qua token này; không hứa đã xóa mọi kho |

`leave()` hiện chỉ reset local. Cần phân biệt “thoát tạm/gián đoạn” với lựa chọn
“rút lại xử lý phiên”. Nếu sản phẩm muốn mọi lần xác nhận thoát đều rút lại thì
phải ghi rõ trên hành động đó và nối API, không coi reset như thao tác server.

Hủy request không bảo đảm server rollback. Không reset mất bearer trước khi
nhận receipt nếu còn cần retry. Bearer chỉ giữ trong ngữ cảnh được bảo vệ của
luồng, không log/URL/clipboard. Nếu muốn retry qua restart app phải thiết kế lưu
bí mật an toàn có hạn; chưa có hàng đợi bền như vậy trong thay đổi này.

Rút phiên không xóa mẫu tài khoản, bản sao lưu hoặc thu hồi ngay BBS đã cấp.
Không tự xóa alias tài khoản đã ghi danh chỉ vì rời một phiên đăng nhập; việc
đổi/xóa khóa theo protocol tài khoản riêng.

## 5. Lỗi, làm lại và đồng bộ trạng thái

| Phản hồi | Cách xử lý dự kiến |
|---|---|
| `409 privacy_consent_required` | Dừng thu/gửi nhóm liên quan, đọc trạng thái và xin lựa chọn còn thiếu; không tự đồng ý |
| `409 privacy_policy_changed` | Xem thông báo đúng version rồi ghi lựa chọn mới. Phiên đã đóng không nhận grant mới: cần đường bắt đầu phiên mới rõ ràng |
| `410 session_withdrawn` | Kết thúc, không retry media/voice hoặc tự cấp session để tiếp tục cùng dữ liệu |
| `410 data_expired`, `401`, `session_too_long` | Kết thúc phiên không còn dùng được; không hứa đã xóa backup/tài khoản. Không đổi nonce để gửi lại video cũ |
| `409 step_already_received` sau mất response | Trạng thái commit chưa chắc client biết. Không tự đánh dấu ACK chỉ từ mã lỗi; API chưa có endpoint đồng bộ tổng quát mọi step. Thiết kế phục hồi phải được kiểm riêng |
| `retry` kèm challenge | Cập nhật gói hiện hành, bỏ dữ liệu/kết quả lượt cũ, giữ phần OTP/CCCD còn hợp lệ; không làm lại toàn bộ đăng ký nếu server cho làm lại phần mặt |
| `review` trong mode eKYC | Kết thúc chưa thể xác minh; không dẫn sang lời hứa chờ nhân viên |
| `503 flow_unavailable` / `otp_unavailable` | Hiện chưa sẵn sàng; không fallback mock/legacy hoặc bỏ guard để đi tiếp |

Giao diện không có score, nguyên nhân an ninh hoặc chữ quy kết người dùng.
Không đổi nhãn `review` trong hợp đồng API chỉ để sửa chữ hiển thị.

## 6. Checklist nghiệm thu trước khi bật trên app

Đây là **các ca cần chạy**, không phải kết quả đã thử điện thoại.

| Nhóm | Ca bắt buộc |
|---|---|
| Lựa chọn | Không tick sẵn; từ chối lưu mẫu dừng tạo tài khoản; chưa có receipt không gửi dữ liệu; thay version không tự grant |
| Phạm vi | Đồng ý mặt không kích hoạt micro; prompt cấp trước chưa phải lệnh thu; server yêu cầu giọng mới đi đúng nhánh |
| Phiên | Hai luồng/tài khoản không dùng lẫn lựa chọn/token; refresh dùng token mới; phiên đã rút không tự sống lại |
| Rút lại | Thành công, mất mạng, chờ khóa DB, lỗi xóa file, receipt không đầy đủ; không báo xóa tài khoản/backup/BBS |
| Retry | Ngắt mạng trước/sau ACK, timeout mất response commit, quay lại từ background, hết hạn khi xác nhận CCCD; không replay byte cũ dưới challenge mới |
| Danh tính | CCCD chính diện, mẫu tài khoản ở reauth/recovery; mất alias hướng dẫn khôi phục; receipt thiếu/lưu lỗi không hứa đăng nhập lại được |
| Thiết bị | Xin camera/micro đúng lúc, release HTTPS/ký media, Keystore/alias, dọn tệp local; test Android/iOS trên máy thật |

Backend đã có test consent, withdrawal đồng thời, quota, retention và PostgreSQL
lock budget ở PR #105; chúng không thay checklist app ở trên. Không mở guard
ghi danh/sinh trắc thật hoặc bổ sung fake-pass để hoàn thành ca thử.
