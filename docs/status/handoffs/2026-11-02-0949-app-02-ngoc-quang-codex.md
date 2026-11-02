# Bàn giao · APP-02 / APP-04 · Ngoc Quang+Codex · 2026-11-02 09:49

**Nhánh:** `codex/APP-02-s24fe-capture-guidance`, base `5544038` (Draft PR128).
**Trạng thái:** doing; chưa nghiệm thu ba luồng AI thật trên máy.

## Đã xong
- Theo dõi lượt S24 FE sau bản API6f3171e: CCCD và gaze qua, head_turn báo wrong_order. Replay read-only cho thấy thứ tự chuyển động thực tế đúng, nhưng hướng đầu vượt50độ ở một số đoạn và không có run300ms liên tục trong vùng nhận; các model cần ba tư thế trả degraded. Không nới ngưỡng hoặc đổi kết quả cũ.
- Rà GitHub: PR115 (f158cd0, merge7fc2ce9),114,112 đã có trong APK7904d70. Không có bản sửa QR mới chưa cài. PR115 đã ghi nhận decoded=true/qrRead=false trên máy cũ; chưa đủ căn cứ gọi đây là lỗi riêng S24.
- Sửa HeadCuePolicy để không liên tục ngắt/phát lại lời nhắc khi góc dao động ngắn. Cảnh báo vẫn ngắt lời nhắc giữ sai ngay; cảnh báo đang phát không tự bị ngắt bởi recovery ngắn. Hướng dẫn quay lại cần ổn định300ms và cách lần đọc trước1s. Câu ngắn “Quay chậm…” / “Dừng xoay, giữ yên”. Giữ lịch12s, rate1f, expiry2s và ngưỡng.
- Sửa lời nhắc CCCD sau20s tự chụp dừng: yêu cầu bấm nút thủ công, giữ lý do ảnh lỗi, không tiếp tục nói đang tự chụp. Không đổi guard/timer/ROI/parser.
- Log debug QR thêm formatValid,rotation,cropRect; chỉ cờ kỹ thuật, không nội dung QR/CCCD. Chưa kết luận format hay ROI là nguyên nhân từ log cũ.
- Hai sub-agent rà độc lập; root bắt thêm lỗi cảnh báo tự ngắt khi recovery chập chờn, đã có RED rồi sửa và GREEN.

## Kiểm tra
- QR regression RED2ca timeout, RED1ca che lý do ảnh lỗi; head RED6ca và RED1ca warning tự ngắt. GREEN focused15/15.
- Android testDebugUnitTest:231tests,0failures,0errors,0skipped.
- lintDebug/assembleDebug/assembleDebugAndroidTest: BUILD SUCCESSFUL; lint0errors/44warnings. Build đúng liveByDefault=true,signedMedia=true,presenceTrace=false,localhost8421.
- plan_check0lỗi/10cảnh báo đã có; git diff --check sạch.
- Full Python đã đạt trên bản API trước đó, không thay Python trong patch này.

## Đang dở / bước tiếp theo
1. Cài đè APK bằng cùng signer, giữ dữ liệu; kiểm probe TTS im lặng trên S24 FE và API/ADB.
2. Người dùng thử lại CCCD/quay đầu, theo dõi log mới; chưa được gọi nghiệm thu từ unit test hoặc probe.
3. Nếu QR còn decoded=true/formatValid=true/qrRead=false, kiểm bounding box/ROI/crop transform; không bỏ filter cho qua.

## Lưu ý và câu hỏi cho nhóm
- Không thay hợp đồng, server schedule, model, calibration, dữ liệu hoặc OTP mô phỏng.
- Review nêu cạnh cũ chưa có bằng chứng trên lượt này: khi face=null do timestamp không dùng được, TurnHeadContent liveAssist=false có thể không dispatch hủy lời nhắc cũ; faces=0 vẫn phát FindFace. Cần kiểm riêng nếu log cho thấy mất timestamp; không coi đây là nguyên nhân đã chứng minh.
- Tính trơn của giọng và khả năng thao tác vẫn cần người dùng xác nhận trên máy; probe im lặng chỉ kiểm engine/callback.
