# Bàn giao · APP-01 · Ngoc-Quang+Codex · 2026-10-30 21:31

**Nhánh:** codex/APP-01-demo-integration
**Trạng thái task sau phiên này:** doing

## Đã xong
- Tiếp tục ba file Android đang có thay đổi hướng dẫn/hold/audio từ phiên trước, không ghi đè bỏ phần đó.
- FaceSignal nhận pitch/roll từ ML Kit; hướng dẫn cảnh báo khi nghiêng/cúi quá 12° hoặc góc không hữu hạn trước khi báo xanh. Đây chỉ là biên nhắc nhở local, không đổi ngưỡng server.
- Oval riêng bước quay đầu rộng tối đa 78%/280dp, vẫn giới hạn theo chiều cao; các bước khác giữ hình học cũ. Không crop/zoom/rebind hoặc sửa video.
- Âm báo ngắn 65/90ms, mức 35/100 thay 85; bỏ ACK/NACK/BEEP2. Mỗi trạng thái chỉ rung một lần mỗi đoạn để tránh dao động góc làm lặp cảnh báo.
- Giữ đủ 850ms chỉ tính chuỗi kết quả liên tục: nhịp đo cách trên 300ms hoặc thời gian không tăng sẽ bắt đầu lại. Review độc lập đã phát hiện và xác nhận sửa điểm này.
- README, task card, dòng backlog được cập nhật; APP-01 tiếp tục doing vì chưa nghiệm thu đầy đủ.

## Đang dở
- Người dùng cần thử bản mới trên Samsung; không hứa khắc phục hết sai khác ML Kit và MediaPipe.
- Dữ liệu/artifact hiệu chỉnh đúng protocol và quyền lưu mẫu SEC-09 chưa hoàn tất; không suy hướng dẫn xanh là server xác minh đạt.

## Bước tiếp theo
1. Bắt đầu phiên mới, quay nhẹ theo mũi tên, dừng khi báo giữ; khi báo giữ đủ thì về nhìn thẳng.
2. Kiểm kết quả server của phiên đó, phân biệt lỗi tư thế với các bước AI phía sau. Không nới ngưỡng để ép pass.

## Quyết định, lưu ý, bẫy
- Chỉ sửa Android, không đổi flow, data/api, contracts, backend hoặc thresholds.yaml. Chỉ thêm số đo tư thế local tại analyzer capture.
- Video chẩn đoán đã dùng lease tạm và giải phóng, không xuất/commit dữ liệu sinh trắc.
- Bản ghi hướng dẫn giữ đủ là tín hiệu local, không phải quyết định server. Không sửa lịch 4 giây/hướng, OTP demo hoặc các chốt tài khoản.
- Không push hoặc mở PR theo yêu cầu người dùng.

## Câu hỏi cho nhóm
- Không có câu hỏi mới; các hạn chế hiệu chỉnh và SEC-09 vẫn còn.

## Test đã chạy
- TDD: invalidAngleNeverShowsGreenOrCompletesHold đỏ trước sửa; analyzerGapsOrReversedTimeCannotCompleteAHold đỏ trước sửa review (12 test, 1 fail), sau đó sửa và chạy lại toàn suite.
- testDebugUnitTest assembleDebug: BUILD SUCCESSFUL, 171 test, 0 fail/error/skip; gồm CitizenCopyTest, ThemeAccessibilityTest. Có cảnh báo LocalLifecycleOwner deprecated cũ.
- SDK apksigner: signer SHA256 822e5e44be42ce365f186a6c73af5bf36eb262c3cc65011b4269363adc695c75 khớp bản debug trước.
- plan_check.py: 0 lỗi, 10 cảnh báo tải công việc/đường găng hiện có.
- Ảnh và kết quả JUnit lưu local ở D:/vericlue/tmp/full-demo-setup/head-assist-comfort; snapshot/cài đặt sẽ ghi xác nhận bên dưới sau khi thực hiện.

- recordPaparazziDebug --tests '*FaceChallengeSnapshotTest*': BUILD SUCCESSFUL; 45 ảnh trước/54 ảnh sau, 16 ảnh khác đều ở bước quay đầu, không có màn khác đổi. Đã xem trực quan màn thường và chữ 200%, không thấy chồng/cắt chữ.
- Review độc lập sau sửa gap: không còn phát hiện cần sửa. git diff --check sạch.
- adb install -r trên Samsung SM_A526B: Success, không gỡ app/xóa dữ liệu. APK giao tại D:/vericlue/tmp/full-demo-setup/apk/VeriClue-demo-debug.apk, SHA256 8809e1d6022ba14f1379cfb17d4c7a0673afe46e5db296bf590585705073db44.
- Lệnh ghép kiểm hash APK từ điện thoại/mở app/reverse/health bị auto-review chặn (blocked by policy, không có lý do cụ thể hơn), chưa xác nhận các thao tác trong lệnh đó. Không thử đường vòng; người dùng mở app thủ công. Trước cài server health ok và ADB reverse còn hoạt động.
