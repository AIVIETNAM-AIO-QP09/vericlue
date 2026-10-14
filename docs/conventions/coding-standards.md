# Chuẩn viết code

## Chung

- **Tên** biến, hàm, file bằng tiếng Anh. Chữ hiển thị cho người dùng bằng tiếng Việt.
- **Ưu tiên đơn giản, đọc được.** Đây là bản demo trong 3 tuần: không trừu tượng hóa sớm, không tối ưu sớm.
- **Không có "số ma thuật":** ngưỡng và tham số để trong `ml/configs/*.yaml` hoặc hằng số có tên.
- **Ghi log** bằng logger (không dùng `print` trong code sản phẩm). Không log ảnh, video, hay dữ liệu cá nhân.
- **Lỗi:** bắt đúng loại lỗi, trả `error_code` theo hợp đồng. Không nuốt lỗi im lặng.

## Python (`services/api`, `ml`)

| Mục | Quy ước |
|---|---|
| Phiên bản | 3.12, quản lý bằng `uv` |
| Định dạng + lint | `ruff format`, `ruff check` (độ dài dòng 100) |
| Kiểu | Type hints cho mọi hàm công khai; dùng `pydantic` cho dữ liệu vào/ra |
| Test | `pytest`; file `tests/test_<module>.py`; test dùng mô-đun mock, không cần GPU |
| Cấu trúc gói | Layout `src/` |
| Import | Tuyệt đối (`from vericlue_ml.face.gend import ...`) |
| Docstring | Ngắn: làm gì, đầu vào, đầu ra, nguồn tham khảo (repo hoặc paper) |
| Mô hình | Nạp một lần (singleton hoặc lifespan của FastAPI), không nạp lại mỗi request |
| Thiết bị | Đọc `DEVICE` từ cấu hình; mọi mô hình phải chạy được trên CPU (chậm cũng được) |

## TypeScript (`apps/web`)

| Mục | Quy ước |
|---|---|
| Ngôn ngữ | TypeScript `strict` |
| Định dạng + lint | Prettier + ESLint (cấu hình của Next.js) |
| Component | Function component, nhỏ; logic tách vào hook hoặc `lib/` |
| Gọi API | Chỉ qua `src/lib/api/`, type sinh từ OpenAPI |
| Trạng thái luồng xác minh | Máy trạng thái rõ ràng (xstate hoặc reducer), không dùng cờ boolean rải rác |
| Test | Vitest cho logic (`lib/capture/*`); Playwright cho luồng chính nếu kịp |
| Thời gian | Đo thời gian bằng `performance.now()`, không dùng `Date.now()` cho phép đo trễ |

## Kiểm thử tối thiểu

- **Mỗi bộ phát hiện:** 1 test chạy mock, 1 test kiểm tra đầu ra khớp `ModuleResult`.
- **TrustRouter:** test cho từng nhánh quyết định (pass / retry / voice_challenge / review), và test "lỗi thì không bao giờ pass".
- **API:** test các endpoint chính bằng `TestClient` với mock.
- **ChromaPulse:** test với chuỗi tín hiệu tổng hợp (đồng bộ / trễ / không phản chiếu) để biết trước kết quả đúng.
