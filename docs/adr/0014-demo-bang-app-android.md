# ADR-0014: Bản demo cho người dân là app Android (thay ADR-0003 cho luồng người dân)

- **Trạng thái:** đã chấp nhận (18/10). Cách làm app ở mục 2 đã chốt: **app Kotlin native**.
- **Ngày:** 2026-10-18
- **Người quyết định:** Trưởng nhóm (người dùng)

## Bối cảnh
ADR-0003 chọn chạy trên **web ở điện thoại**. Trưởng nhóm quyết định bản demo nộp cuộc thi là **app Android** và sản phẩm sau này cũng là app Android. iOS không làm. Không đọc chip CCCD.

## Quyết định
1. **Luồng người dân** (đăng ký, đăng nhập lại, khôi phục; ADR-0013) chạy trên **app Android**, yêu cầu Android 10 trở lên.
   - **Bàn duyệt** và **giám định** vẫn là web trên máy tính.
   - Web `/verify` được giữ làm bản dự phòng và để phát triển nhanh.
2. **Cách làm app: viết app Kotlin native** (trưởng nhóm quyết 18/10).
   - Stack: Jetpack Compose, CameraX, ML Kit hoặc MediaPipe để hướng dẫn người dùng, Android Keystore. API client sinh từ `openapi.json`.
   - **Dùng lại code từ `AIVIETNAM-AIO-QP09/eKYC-system` (MIT):** khung app, CameraX, quay video, dò mặt kèm góc quay đầu, Keystore.
     - Phải giữ dòng giấy phép và ghi vào `third_party/README.md` (AGENTS §6 luật 6).
     - **Không** dùng lại phần app tự quyết `approval` và các mô hình trên máy của repo đó (`face_recognition_s.onnx` chưa rõ giấy phép).
   - Tách thành APP-01 đến APP-04.
   - Web `/verify` giữ làm **bản dự phòng** khi demo.
   - Đã cân nhắc bọc web bằng Capacitor: nhanh hơn (1–2 ngày) nhưng không chọn.
3. **Mô hình quyết định luôn chạy ở server** (ADR-0013 nguyên tắc 7). Trên máy chỉ chạy MediaPipe, OpenCV và thư viện đọc QR để hướng dẫn người dùng. Vì vậy chọn mô hình không phụ thuộc phần cứng điện thoại.
4. **Kết nối từ app tới server demo dùng HTTPS**, vì hai lý do:
   - từ Android 9, app mặc định chặn HTTP không mã hóa;
   - dữ liệu sinh trắc phải được mã hóa trên đường truyền.

   Sau này thêm certificate pinning (B9). Cần thiết lập HTTPS cho máy demo ngay từ đầu (APP-01).

## Phương án đã cân nhắc
- **Giữ web (ADR-0003):** khách quét QR là thử được ngay. Nhưng không có Keystore, chứng thực thiết bị hay đọc OTP tự động.
- **Làm cả Android và iOS:** không đủ thời gian và nhân lực.

## Hệ quả
- **Proposal** cần sửa các chỗ nói "web trên điện thoại" và "quét QR thử ngay". Theo AGENTS §6 luật 7, việc này cần task riêng; giao cho DEMO-03 hoặc một task proposal.
- **CamProbe:** phần bắt can thiệp vào JavaScript chỉ có ý nghĩa trên web hoặc WebView. App native cần thêm kiểm tra root/hook và chứng thực thiết bị.
- **Thêm task APP-01 đến APP-04** (epic E9). Phần server của các luồng nằm ở FLOW-01 đến FLOW-05.

## Cập nhật 21/10 — phạm vi và cách làm (trưởng nhóm chốt)
1. **Phạm vi bản nộp:** chỉ làm **đăng ký** (`onboarding`) và **đăng nhập lại** (`reauth`). Luồng **khôi phục** (`recovery`) chỉ mô tả trong báo cáo, làm thêm nếu còn thời gian. Lý do: còn 16 ngày, cả 3 luồng cần khoảng 13,5 ngày công.
2. **Làm theo lát cắt dọc:** trước tiên app phải đi hết một luồng trên điện thoại thật bằng API MVP đang có (tạo phiên → ảnh/video mặt → tín hiệu → chốt → đọc câu → kết quả). Sau đó mới thêm OTP, CCCD, quay đầu, so mặt.
3. **Phiên AI Claude viết app** ở worktree riêng; phiên Codex duyệt chéo. Trưởng nhóm build và cài thử trên điện thoại Android 10+ của nhóm.
4. **HTTPS bằng đường hầm Cloudflare** (`cloudflared`) trỏ vào API trên máy demo:
   - có chứng chỉ thật, điện thoại dùng 4G hay Wi-Fi nào cũng vào được, không phải cài chứng chỉ tự ký;
   - **đánh đổi:** dữ liệu sinh trắc đi qua hạ tầng Cloudflare (vẫn mã hóa trên đường truyền, TLS kết thúc tại Cloudflare). Chấp nhận cho bản demo; ghi là giới hạn trong báo cáo, sản phẩm thật dùng HTTPS trực tiếp + certificate pinning (B9);
   - địa chỉ đường hầm đặt bằng cấu hình build (không cứng trong code), không commit token Cloudflare.
