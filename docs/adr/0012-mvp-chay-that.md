# ADR-0012: Hồ sơ MVP — chạy hoàn toàn bằng mô hình thật

- **Trạng thái:** đã chấp nhận
- **Ngày:** 2026-10-18
- **Người quyết định:** Trưởng nhóm (phiên điều phối)

## Bối cảnh
Ngày 18/10, có 3 mô hình thật đã được cắm vào hệ thống: MiniFASNet, AntiDeepfake và PhoWhisper. Nhưng người dùng vẫn không tự thử được bằng mặt và giọng của mình, vì 3 lý do:
- web gửi ảnh và âm thanh giả để giữ chỗ (CAP-06, CAP-07 chưa làm);
- không có calibrator nào, nên mọi phiên đều ra `review`;
- router bắt buộc có ChromaPulse (PRES-02, CAP-04: khoảng 3,5 ngày công) và khớp môi (VOICE-05, chưa có dữ liệu giả để hiệu chỉnh).

Người dùng yêu cầu: **trong ngày 18/10 phải có một MVP chạy hoàn toàn bằng đồ thật**, luồng xử lý rõ ràng và đúng logic.

## Quyết định
1. **Thêm hồ sơ router `ROUTER_PROFILE=mvp`.** Giá trị mặc định vẫn là `full`, hành vi hiện tại giữ nguyên.
   - **Cổng hiện diện:** chỉ dùng `camprobe`. `chromapulse` không chạy và không bắt buộc. Lý do: theo quyết định 17/10, ChromaPulse là tín hiệu phụ.
   - **Cổng khuôn mặt:** dùng `face_pad` và `face_deepfake`, lấy max `prob_attack`, ngưỡng B và A theo `thresholds.yaml`.
   - **Bước giọng nói:** dùng `voice_challenge` và `voice_spoof`. `lipsync` không chạy và không bắt buộc. Cờ cắt ghép vẫn áp dụng nếu có.
   - **`quality` chạy thật ở phía server.**
   - Hồ sơ `mvp` chạy với `USE_MOCK_MODELS=false`. Orchestrator chỉ chạy các module có trong hồ sơ. Module nào thiếu, lỗi hoặc `degraded` thì phiên ra `review`, tuyệt đối không ra `pass`.
2. **Calibrator MVP = "giữ nguyên" (identity), tạm thời** (người dùng quyết 18/10). Lý do: hiệu chỉnh chỉ đổi thang điểm, không làm mô hình phân biệt tốt hơn; MVP cần chạy ngay.
   - Điểm thô `score` được dùng thẳng làm `prob_attack`, cắt vào khoảng [1e-4, 1 − 1e-4].
   - Áp dụng cho `face_pad`, `face_deepfake` và `voice_spoof`.
   - Lưu như calibrator thường (ADR-0010 mục 6), `method: identity`, ghi rõ `provisional` và "MVP — không dùng cho báo cáo". Router không cần đường lùi đặc biệt.
   - Ngưỡng B, A và `spoof_threshold` lấy từ `thresholds.yaml` hiện có.
   - **Biết trước:** ngưỡng trên điểm thô có thể cho một số ảnh giả qua (MiniFASNet chưa tinh chỉnh, yếu với ảnh giả Zalo).
   - Calibrator thật (fit trên `calib_fit`, theo ADR-0010) thay calibrator identity khi có dữ liệu. Các mục con dưới đây là kế hoạch cho bước thay thế đó, không chặn MVP:
   - `face_pad`: fit trên `calib_fit` của Zalo 2022, do DATA-03 phần ảnh sinh ra.
   - `voice_spoof`: fit trên `calib_fit` âm thanh. **Lớp dương chỉ gồm giọng tổng hợp (TTS/VC).** Mẫu `replay` bị loại khỏi tập fit, vì AntiDeepfake không nhắm tới replay. Replay do câu thử thách chặn (ADR-0005).
   - `face_deepfake` (GenD): **WildDeepfake được chia lại theo nhóm video** (`video_groups.jsonl`) thành `calib_fit`, `calib_ltt` và `test`. Phần này thay một phần quyết định "WildDeepfake chỉ làm test" ngày 17/10. R2 ghi rõ phần test còn lại. RTFS-10k vẫn chỉ dùng làm test.
3. **Không đổi ngưỡng.** Ngưỡng của `quality` và `camprobe` (chưa có trong `thresholds.yaml`) đặt thành hằng số có tên trong file mô-đun, giống `SECOND_FACE_AREA_RATIO` ở `pad.py`, chờ ROUT-03. `thresholds.yaml` giữ nguyên các giá trị tạm (`provisional: true`). Ngưỡng chính thức vẫn do ROUT-03 chọn trên `calib_ltt`.
4. **Không có kết quả R nào được lấy từ MVP.** Số liệu thử tay chỉ ghi vào bàn giao.

5. **Đợt 2 (18/10, người dùng yêu cầu cắm đủ mọi mô hình có sẵn):**
   - Khi `lipsync` thật (VOICE-05: SyncNet và CTC aligner) đã đăng ký, hồ sơ `mvp` đưa `lipsync` trở lại bước giọng nói và dùng calibrator identity như ba module trên.
   - Cờ cắt ghép từ aligner đi vào `splice_flags`, router hiện đã xử lý trường này.
   - Cách quy đổi độ tin cậy SyncNet ra `score` trong [0, 1] (tăng = nghi giả) là hằng số có tên, tạm thời, ghi trong file mô-đun.
   - Nếu bước giọng nói không có video, `lipsync` trả `not_applicable`. Router xử lý trường hợp này giống thiếu module bắt buộc (`review`), trừ khi trưởng nhóm quyết khác sau khi thử.
6. **Sửa mục 5 (18/10, sau khi duyệt PR #32): `lipsync` chạy ở chế độ "tham khảo"** cho tới khi đủ ba điều kiện bên dưới.
   - `lipsync` vẫn chạy trong hồ sơ `mvp`. Kết quả được lưu và hiện cho người duyệt. **Router chưa dùng nó để quyết định.** Bước giọng nói quyết bằng `voice_challenge` và `voice_spoof`.
   - Lý do: đo trong thực tế sẽ sai một cách có hệ thống, nên người thật gần như luôn bị đẩy sang `review`:
     - web ghi hình và tiếng bằng hai bộ ghi khác nhau, lệch đồng hồ không biết trước;
     - câu đề bài ngắn (khoảng 1,6–2,5 giây) không đủ cửa sổ cho SyncNet;
     - chạy CPU vượt trần 4 giây.

     Lỗi do cách đo, không phải do người dùng.
   - **Điều kiện để đưa `lipsync` trở lại phần quyết định:**
     - web ghi video kèm track âm thanh trong cùng một MediaRecorder, hoặc gửi độ lệch thời điểm bắt đầu;
     - có số đo trên câu thật cho thấy người thật đạt;
     - chạy trên GPU trong ngân sách thời gian.
   - Cờ cắt ghép (`splice_flags`) **vẫn được dùng để quyết định.** Router xét "đọc sai câu" **trước** cờ cắt ghép: đọc sai thì cho đọc lại, không bị đẩy sang `review` ưu tiên cao vì cờ sinh ra do căn câu đề bài vào một câu đọc sai.

## Phương án đã cân nhắc
- **Giữ hồ sơ `full`, chờ đủ PRES-02 và VOICE-05:** không kịp trong ngày, và người dùng không thử được.
- **Đặt GenD ở dạng "chỉ tham khảo" (không dùng để quyết định):** hệ thống chống deepfake mà bỏ qua bộ phát hiện deepfake thì sai logic. Không chọn.
- **Ép `pass` khi thiếu calibrator, hoặc cho router đọc điểm thô ngầm:** vi phạm ROUT-01 và ROUT-02. Không chọn. Thay vào đó dùng calibrator identity ghi rõ trong file (mục 2): minh bạch, và thay được sau này.
- **Chờ chia tập ảnh rồi mới fit calibrator thật:** đúng phương pháp hơn, nhưng làm MVP chậm. Để làm bước thay thế sau.

## Hệ quả
- Có luồng chạy thật từ camera và micro, qua mô hình thật, tới quyết định thật. Điểm yếu đã biết:
  - không có ChromaPulse và khớp môi;
  - calibrator ít mẫu (Zalo, MLAAD-vi);
  - MiniFASNet chưa tinh chỉnh, yếu với ảnh giả của Zalo.
- Hồ sơ `full` vẫn là mục tiêu nộp bài. Hồ sơ `mvp` không thay thế kế hoạch đã có.
- DATA-03 cập nhật phần chia WildDeepfake. FACE-02 thêm `calib_fit` WildDeepfake vào phần đánh giá.
