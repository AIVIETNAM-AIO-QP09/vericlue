# Red-team — tự thử tấn công hệ thống của nhóm

> Hoàn thiện ở task REDT-01. **Đọc kỹ quy tắc trước khi làm.**

## Quy tắc bắt buộc

1. **Chỉ tấn công hệ thống VeriClue của nhóm.** Không thử vào ngân hàng, ví điện tử hay bất kỳ hệ thống thật nào.
2. **Chỉ dùng mặt và giọng của thành viên nhóm** (đã đồng ý), hoặc người nổi tiếng trong bộ dữ liệu công khai chỉ để tạo dữ liệu kiểm thử. Không dùng mặt người ngoài trong demo trực tiếp.
3. Công cụ tấn công **chỉ cài trên máy red-team**, không đưa vào repo (Deep-Live-Cam là AGPL).
4. Dữ liệu tạo ra chỉ dùng nội bộ, xóa sau dự án, không đăng lên mạng.

## Công cụ

| Công cụ | Dùng cho kịch bản | Ghi chú |
|---|---|---|
| OBS Studio + Virtual Camera | T3: camera ảo phát video | |
| Tiện ích Chrome giả camera (ví dụ `camera-intercept-extension`) | T3: thay hàm camera trên trang | Cài thủ công ở chế độ developer |
| Deep-Live-Cam, FaceFusion | T5, T6: ghép mặt thời gian thực | Thử cả có và không bật hòa trộn Poisson |
| VieNeu-TTS | Clone giọng tiếng Việt | Chạy trên CPU |
| Chatterbox | Giọng giả **có thủy vân** PerTh | Cho kịch bản demo số 7 |
| Wav2Lip | Lồng tiếng khớp môi | |
| Ảnh in A4, máy tính bảng | T1, T2 | |

## Kịch bản (khớp proposal §1.4 và §2.4)

| # | Kịch bản | Cách làm | Kết quả mong đợi |
|---|---|---|---|
| 1 | Người thật | Thành viên tự xác minh | Cho qua |
| 2 | Người thật, phòng tối | Tắt đèn | Chụp lại |
| 3 | Ảnh in / phát lại | Giơ ảnh hoặc máy tính bảng trước camera | Chuyển nhân viên |
| 4 | Camera ảo | OBS phát video quay sẵn; hoặc tiện ích giả camera | Chuyển nhân viên – ưu tiên cao |
| 5 | Ghép mặt thời gian thực + giọng clone | Deep-Live-Cam → OBS; VieNeu-TTS | Chuyển nhân viên – ưu tiên cao |
| 6 | Giám định video giả đã nén | Video từ DATA-04, nén CRF 40 | Báo cáo chỉ ra đoạn nghi giả |
| 7 | Giám định giọng có thủy vân | File từ Chatterbox | "Phát hiện thủy vân AI" |

Ghi lại tham số đã dùng cho từng lần chạy (công cụ, phiên bản, cấu hình) vào bảng cuối file này.

## Nhật ký chạy

| Ngày | Kịch bản | Công cụ / phiên bản / tham số | Kết quả hệ thống | Người |
|---|---|---|---|---|
