# Thuật ngữ

| Thuật ngữ | Nghĩa |
|---|---|
| **eKYC** | Định danh khách hàng điện tử — xác minh danh tính từ xa qua điện thoại |
| **PAD** (Presentation Attack Detection) | Phát hiện tấn công trình diện: ảnh in, màn hình phát lại, mặt nạ đặt trước camera |
| **Deepfake** | Khuôn mặt hoặc giọng nói tạo hay chỉnh sửa bằng AI |
| **Face-swap thời gian thực** | Ghép mặt người khác lên mặt kẻ gian ngay trong lúc quay (Deep-Live-Cam) |
| **Chèn luồng / camera ảo** (injection) | Thay hình từ camera thật bằng video có sẵn (OBS, tiện ích trình duyệt, hook Android) |
| **ChromaPulse** | Thành phần của VeriClue: màn hình nháy chuỗi màu, đo da mặt có phản chiếu đúng màu và đúng lúc |
| **CamProbe** | Thành phần của VeriClue: kiểm tra camera có bị phần mềm thay thế hoặc can thiệp |
| **TrustRouter** | Bộ ra quyết định: cho qua / chụp lại / đọc câu / chuyển nhân viên |
| **VoiceGate** | Bước đọc câu tiếng Việt ngẫu nhiên để kiểm tra giọng và môi |
| **Bộ não** | Tập hợp các bộ phát hiện dùng chung cho hai chế độ |
| **ModuleResult** | Định dạng kết quả chuẩn mà mọi bộ phát hiện trả về |
| **Mock** | Mô-đun giả lập, trả kết quả đúng định dạng để phát triển song song |
| **APCER** | Tỷ lệ tấn công bị nhận nhầm là thật (tỷ lệ "lọt"), tính theo từng loại tấn công |
| **BPCER** | Tỷ lệ người thật bị nhận nhầm là tấn công (tỷ lệ "chặn oan") |
| **EER** | Điểm mà hai loại lỗi bằng nhau; càng thấp càng tốt |
| **AUC** | Diện tích dưới đường ROC; càng gần 1 càng tốt |
| **Hiệu chỉnh** (calibration) | Biến điểm thô của mô hình thành xác suất đáng tin |
| **Learn-then-Test (LTT)** | Phương pháp chọn ngưỡng có **bảo đảm thống kê**: tỷ lệ lọt ≤ α với xác suất ≥ 1−δ |
| **α, δ** | α: mức lọt tối đa cho phép (ví dụ 5%); δ: xác suất bảo đảm bị sai (ví dụ 5%) |
| **OOD** (ngoài phạm vi) | Mẫu khác xa dữ liệu đã kiểm thử → không tự quyết, chuyển nhân viên |
| **Tỷ số khả năng** (likelihood ratio) | Bằng chứng ủng hộ giả thuyết này hơn giả thuyết kia bao nhiêu lần — dùng trong báo cáo giám định |
| **ENFSI** | Mạng lưới các viện khoa học hình sự châu Âu; có thang lời chuẩn cho mức độ bằng chứng |
| **Thủy vân AI** (watermark) | "Dấu ẩn" mà công cụ AI gắn vào file nó tạo ra (AudioSeal, Perth) |
| **C2PA** | Chuẩn chứng nhận nguồn gốc nội dung số |
| **Red-team** | Tự đóng vai kẻ tấn công để thử hệ thống của chính mình |
| **R1–R6** | Sáu nhóm kết quả sẽ trình bày (proposal §2.9) |
| **M0–M3** | Các mốc tiến độ (docs/plan/roadmap.md) |
| **M1–M5** | Năm vai trò trong đội (docs/context/team.md) |
| **ADR** | Architecture Decision Record — ghi lại một quyết định thiết kế và lý do |
| **Task card** | Mô tả đầy đủ một việc: mục tiêu, bước, tiêu chí xong (docs/plan/epics/) |
| **calib_fit / calib_ltt** | Hai nửa của tập hiệu chỉnh, chia theo người. `calib_fit`: hiệu chỉnh, hợp nhất, chọn mô hình. `calib_ltt`: **chỉ** để chọn ngưỡng có bảo đảm (ADR-0010) |
| **Handoff** | Ghi chú bàn giao cuối mỗi phiên làm việc — mỗi lần một file trong docs/status/handoffs/ |
