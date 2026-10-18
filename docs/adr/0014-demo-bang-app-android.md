# ADR-0014: Bản demo cho người dân là app Android (thay ADR-0003 cho luồng người dân)

- **Trạng thái:** đã chấp nhận (18/10). Cách làm app ở mục 2 vẫn **đang chờ chốt**.
- **Ngày:** 2026-10-18
- **Người quyết định:** Trưởng nhóm (người dùng)

## Bối cảnh
ADR-0003 chọn chạy trên **web ở điện thoại**. Trưởng nhóm quyết định bản demo nộp cuộc thi là **app Android** và sản phẩm sau này cũng là app Android. iOS không làm. Không đọc chip CCCD.

## Quyết định
1. **Luồng người dân** (đăng ký, đăng nhập lại, khôi phục; ADR-0013) chạy trên **app Android**, yêu cầu Android 10 trở lên.
   - **Bàn duyệt** và **giám định** vẫn là web trên máy tính.
   - Web `/verify` được giữ làm bản dự phòng và để phát triển nhanh.
2. **Cách làm app — chưa chốt:**
   - **(a) Bọc web hiện có bằng Capacitor** (MIT). Dùng lại gần như toàn bộ code thu nhận (camera, video, WAV, ChromaPulse, CamProbe). Phần native thêm bằng plugin (Keystore, Play Integrity). Ước tính 1–2 ngày.
   - **(b) Kotlin native**, học cấu trúc từ `AIVIETNAM-AIO-QP09/eKYC-system` (CameraX, ML Kit, Keystore). Phải viết lại phần thu nhận, nên lâu hơn. Chỉ chọn nếu nhóm SW có người làm được Kotlin.
3. **Mô hình quyết định luôn chạy ở server** (ADR-0013 nguyên tắc 7). Trên máy chỉ chạy MediaPipe, OpenCV và thư viện đọc QR để hướng dẫn người dùng. Vì vậy chọn mô hình không phụ thuộc phần cứng điện thoại.
4. **Kết nối từ app tới server demo** phải là **HTTPS**, vì Android chỉ cho bật camera và micro trong ngữ cảnh an toàn. Cần thiết lập HTTPS cho máy demo ngay từ đầu.

## Phương án đã cân nhắc
- **Giữ web (ADR-0003):** khách quét QR là thử được ngay. Nhưng không có Keystore, chứng thực thiết bị hay đọc OTP tự động.
- **Làm cả Android và iOS:** không đủ thời gian và nhân lực.

## Hệ quả
- **Proposal** cần sửa các chỗ nói "web trên điện thoại" và "quét QR thử ngay". Theo AGENTS §6 luật 7, việc này cần task riêng; giao cho DEMO-03 hoặc một task proposal.
- **CamProbe:** phần bắt can thiệp vào JavaScript chỉ có ý nghĩa trên web hoặc WebView. App native cần thêm kiểm tra root/hook và chứng thực thiết bị.
- **Thêm task APP-01** (epic E9).
