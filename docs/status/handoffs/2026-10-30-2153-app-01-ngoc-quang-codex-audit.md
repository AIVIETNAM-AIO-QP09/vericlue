# Bàn giao · APP-01 / LIVE-02 · Ngoc-Quang+Codex-Audit · 2026-10-30 21:53

**Nhánh:** codex/APP-01-demo-integration
**Trạng thái task sau phiên này:** doing

## Đã xong
- Theo yêu cầu người dùng: kiểm lỗi và viết kế hoạch giao Gemini làm trực tiếp để tiết kiệm; không triển khai thêm thuật toán trong lượt này.
- Đọc kết quả bốn lượt gần nhất, tách lỗi mắt ngang khỏi mất bám mặt ở head. Hai lượt mới nhất đều đủ gần 99% mẫu mắt nhưng trục ngang kém, không được quy hết cho thao tác người dùng.
- Dùng CalibrationStore trong runtime thật kiểm full version PAD/GenD session-video-v2: đều unavailable; kiểm cấu hình danh tính/consistency chưa có artifact, account_enrollment=false. Đây là chốt toàn luồng độc lập.
- Viết spec chẩn đoán, kế hoạch 5 task và prompt Gemini; đã tự rà thứ tự, tiêu chí nghiệm thu, negative controls, giữ dữ liệu riêng tư và ràng buộc không ép pass.

## Đang dở
- Chưa có trace ML Kit đồng bộ với MediaPipe/video để chứng minh chênh lệch góc. Chưa xác định nguyên nhân mắt ngang bằng oracle độc lập. Không gọi đây là lỗi hình học đã được chứng minh.
- Chưa sửa code hoặc chạy nghiệm thu mới sau dab9f6f. Chưa có công cụ gọi Gemini trực tiếp trong phiên này; prompt dành cho người dùng gửi sang Gemini.

## Bước tiếp theo
1. Đọc docs/superpowers/specs/2026-10-30-presence-demo-stabilization-design.md.
2. Gemini thực hiện docs/superpowers/plans/2026-10-30-presence-demo-stabilization-gemini.md khi người dùng gửi yêu cầu thực hiện.
3. Prompt local: tmp/design/codex-prompt-gemini-presence-fix.md (ignored, không có trong commit). Người dùng chỉ cần yêu cầu Gemini đọc file đó.
4. Kết luận prefix mắt+đầu riêng với toàn eKYC/ghi danh. Không hứa fix tuyệt đối hoặc full pass khi thiếu artifact.

## Quyết định, lưu ý, bẫy
- Không đổi threshold/schema/ADR/STATUS/guard hay OTP demo. Không dùng test/clip chẩn đoán để chọn ngưỡng.
- Dữ liệu runtime chỉ tổng hợp whitelist tại D:/vericlue/tmp/full-demo-setup/head-assist-comfort/handoff-audit.json và handoff-artifact-audit.json. Không xuất media, CCCD, khóa hoặc token.
- Không chạy thêm agent Codex hoặc gửi dữ liệu sang bên ngoài; không push/PR.

## Câu hỏi cho nhóm
- Cần dữ liệu và artifact đúng protocol nếu mục tiêu là full eKYC thật; chưa có bằng chứng chúng có sẵn để hoàn tất trong một phiên chỉ bằng sửa code.

## Test đã chạy
- Không đổi product code, không chạy lại Android/ML suite cho lượt chỉ viết tài liệu này. 171 test xanh là bằng chứng của commit dab9f6f, không phải kết quả mới của kế hoạch.
- Đã thực hiện truy vấn chẩn đoán qua SessionPrivacy và kiểm loader/config runtime, không đoán từ tên file.
- plan_check.py: 0 lỗi, 10 cảnh báo cũ; git diff --cached --check sạch trước commit tài liệu.
