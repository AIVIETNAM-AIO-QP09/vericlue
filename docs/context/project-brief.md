# VeriClue — Tóm tắt dự án (1 trang)

> Đọc file này trước tiên nếu bạn mới vào dự án. Chi tiết đầy đủ: `docs/proposal/proposal.md`.

## Bài toán

Từ 2024, Việt Nam bắt buộc xác thực khuôn mặt khi giao dịch ngân hàng trực tuyến. Tội phạm chuyển sang **dùng AI làm giả khuôn mặt và giọng nói**, và **thay luồng camera bằng video có sẵn**. Các vụ án tiêu biểu: Thái Bình (2025), hai vụ Thanh Hóa (2025–2026, hơn 2.000 tài khoản). Đề bài **BTL86-16** (Bộ Tư lệnh 86) nhận định công cụ hiện có "chủ yếu tối ưu cho dữ liệu nước ngoài".

## Giải pháp

**1 bộ não phát hiện giả mạo** được kiểm tra trên dữ liệu Việt Nam, dùng chung cho **2 chế độ**:

| Thành phần | Làm gì |
|---|---|
| **Bộ não** | Phát hiện ảnh in, màn hình, mặt ghép AI (GenD, SBI), giọng giả tiếng Việt (AntiDeepfake), môi không khớp tiếng (SyncNet) |
| **Chế độ 1 — eKYC tức thời** | Web trên điện thoại:<br>• **ChromaPulse**: màn hình nháy màu, đo da mặt phản chiếu và độ trễ;<br>• **CamProbe**: phát hiện camera ảo;<br>• **TrustRouter**: ra quyết định với ngưỡng có bảo đảm thống kê (Learn-then-Test);<br>• kết quả: *cho qua / chụp lại / đọc câu tiếng Việt / chuyển nhân viên* |
| **Chế độ 2 — Giám định** | Điều tra viên tải video lên → phân tích từng đoạn → quét thủy vân AI → báo cáo theo chuẩn ENFSI, có chữ ký số |

## Phạm vi bản thi

- **Có:**
  - web demo chạy trên điện thoại thật;
  - bàn duyệt cho nhân viên;
  - cổng giám định;
  - báo cáo kết quả R1–R6 trên dữ liệu công khai.
- **Không:**
  - app native;
  - đọc chip CCCD;
  - đối chiếu cơ sở dữ liệu dân cư;
  - thu dữ liệu sinh trắc của người ngoài;
  - Ring Radar (phát hiện đường dây) — để sau.

## Mốc thời gian

| Mốc | Ngày | Kết quả |
|---|---|---|
| M0 | 17/10 | Khung dự án chạy được đầu–cuối với mô-đun giả lập; chốt kết quả thử ChromaPulse |
| M1 | 25/10 | eKYC phần hình ảnh chạy với mô hình thật |
| M2 | 01/11 | Giọng nói + giám định + ngưỡng có bảo đảm |
| M3 | 04/11 | Đóng băng tính năng; đủ kết quả đánh giá; video demo |
| **Nộp** | **05/11** (hạn chót trước 06/11) | Gói nộp hoàn chỉnh |

## Quyết định quan trọng đã chốt

Xem `docs/adr/`:
- chỉ dùng dữ liệu công khai;
- web chứ không làm app;
- dùng mô hình có sẵn và chỉ tinh chỉnh;
- GenD + SBI cho khuôn mặt;
- AntiDeepfake cho giọng nói;
- Learn-then-Test qua thư viện MAPIE;
- ChromaPulse đo độ trễ tuyệt đối;
- hạ tầng tối giản.

## Đội

5 thành viên, chia theo vai trò M1–M5: xem `docs/context/team.md`.
