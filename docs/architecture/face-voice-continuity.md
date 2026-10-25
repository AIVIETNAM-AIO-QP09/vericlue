# So cùng người giữa bước mặt và bước đọc câu — FLOW-05

## Phạm vi

`face_continuity` dùng **cùng instance SCRFD/LVFace-B** với `face_match` trong
orchestrator, dùng chung MediaPipe và tiền xử lý ArcFace112 RGB [-1,1]. Không
nạp thêm một bản LVFace. Kết quả riêng giữ nguyên kết quả CCCD–chính diện.
Mô-đun có mock, registry, config và trả `ModuleResult`; không trả embedding.

Đây là kiểm tra danh tính tại **ba mẫu thời gian**, không kiểm mọi khung hoặc
chứng minh liveness/nguồn camera. Người khác có thể xuất hiện ở khoảng chưa lấy
mẫu; cần đánh giá thực nghiệm và protocol theo dõi dày hơn nếu muốn kết luận
cho toàn video. PAD, GenD, ánh sáng và khớp môi vẫn là các kiểm tra độc lập.

## Đầu vào do server quản lý

Hợp đồng nội bộ thêm `DetectorInput.reference_video`: video bước mặt đã lưu.
`video` là video đọc câu, `audio` là WAV của lượt đó. Không nhận đường dẫn,
embedding, nhãn góc hay kết quả tham chiếu từ HTTP/signals của người dùng.
Server truyền challenge hiện hành, mã lần đọc hiện hành và `face_match` đã lưu
qua metadata. `Session.voice_video`/`voice_audio_offset_ms` giữ bản ghi của lượt
hiện tại trong snapshot, mã hóa nếu bật `SESSION_PRIVACY`.

1. Kiểm ràng buộc phiên/lượt, mã đọc, offset nguyên trong [-5000,5000] ms.
2. Lấy khung chính diện đúng lịch server từ video mặt; kiểm một mặt và tư thế.
   Đối chiếu hash video, hash pixel, target và PTS với bằng chứng `face_match`
   đúng `VIDEO_MATCH_VERSION`. Không fallback ảnh selfie người dùng gửi.
3. Đọc WAV PCM16/mono/16k, 1–10 giây, tối đa 1 MiB; kiểm số byte dữ liệu thật,
   không chỉ tin thời lượng header. Chọn ba thời điểm 10/50/90% thời lượng WAV,
   chuyển sang thời gian video bằng `video_ms = audio_ms + audio_offset_ms`.
   Thiếu offset dùng 0, cùng quy ước endpoint hiện tại; không suy từ FPS.
4. Decoder chọn khung gần nhất bằng PTS thật, lệch tối đa 100 ms, hòa chọn khung
   sớm hơn. Cả ba phải tồn tại, khác PTS, một mặt và đủ chính diện; sai/thiếu/lỗi
   không được đạt. Giới hạn video/decoder dùng chung `presence.views`.
5. Căn/chạy LVFace trên một khung tham chiếu và ba khung giọng, so ba cosine.
   Dùng **cosine nhỏ nhất**, không lấy trung bình để che một mẫu khác người.
6. Kiểm lại hash cả hai video và WAV sau suy luận. Bằng chứng gồm mã hai lượt,
   hash nguồn, PTS/pixel từng mẫu và ba cosine; không lưu hoặc log vector.

Nhận lại nguyên một tệp video mặt làm video giọng bị chặn; đây không phải bảo
đảm phát hiện mọi video phát lại. Chữ ký B4 ràng buộc byte với lượt hiện hành,
không chứng minh camera thật.

## Ngưỡng riêng và quyết định

Version `FACE_VOICE_VERSION = VIDEO_MATCH_VERSION + "+face-voice-v1"` xác định
protocol ba mẫu nói trên. Artifact `MatchThreshold` phải đúng version, tiền xử
lý và split `calib_ltt`, có dataset/số cặp/số người/commit/hash dự đoán. **Không
tái dùng ngưỡng CCCD hoặc ngưỡng nhất quán ba góc.** Không sửa thresholds.yaml.

Thiếu artifact hoặc tham chiếu chưa `ok/pass`: trả số đo thô với
`degraded/unclear`, không prob_attack. Có artifact đúng và tham chiếu đã đạt:
`ok/pass` chỉ khi cả ba cosine đạt ngưỡng; một mẫu dưới ngưỡng → `ok/fail`.
Artifact sai/thiếu mô hình/giải mã lỗi → không đạt. Lỗi preload được giữ tới khi
restart. Hiện chưa có artifact/ngưỡng thực hay số liệu accuracy/latency mới.

API opt-in qua `IDENTITY_VOICE_CONTINUITY=true`, yêu cầu `IDENTITY_LAB_URL` và
`IDENTITY_FACE_FROM_VIDEO=true`. `IDENTITY_VOICE_CALIBRATION` trỏ artifact riêng.
Khi bật, onboarding/recovery cần public key và chữ ký ở cả mặt/giọng; thiếu chữ
ký bị từ chối trước ghi tệp. Trước khi chạy phải có proof nonce của cả hai bước.

Bước `/voice` xếp mô-đun cùng nhóm giọng, dùng deadline/hàng đợi/lease hiện có;
ngân sách opt-in dùng `SESSION_MODEL_TIMEOUT_SECONDS`. Cả video mặt và video
giọng được giải mã vào lease; timeout không xóa tệp khi native job còn chạy.
`face_continuity` lỗi/thiếu/không đạt/sai version/sai context buộc `review` khi
pipeline định cho đạt hoặc đọc lại. Kết quả này không ghi đè PAD/giọng/so CCCD.
Reread/refresh/retry bỏ kết quả cũ, đổi lượt rồi phải kiểm lại.

Không thêm mô-đun vào full/MVP mặc định. Không thay HTTP response của người dân
hoặc UI. Chốt real/mixed của luồng dynamic **vẫn đóng**. AccountStore đọc kết
quả riêng này nhưng vẫn chặn mock/mixed/thiếu các cổng khác. Chưa có endpoint
ghi danh tự động, L0, xoay/thu hồi thiết bị hoặc recovery đầy đủ.

## Kiểm thử offline

Không tự thu camera/micro; dùng hai bản ghi đã có quyền sử dụng, ảnh tham chiếu
và JSON challenge do server cấp, mã đọc hiện hành:

```powershell
uv run python -m vericlue_ml.eval.face_continuity --face-video <face.mp4> --voice-video <voice.mp4> --audio <voice.wav> --reference-card <card.png> --server-response <session.json> --voice-challenge-id <vc_...> --audio-offset-ms 600 --models-dir <models> --device cpu --output tmp/continuity.json
```

Tùy chọn `--face-calibration` (mặc định xét `FACE_MATCH_CALIBRATION`) và
`--continuity-calibration` phải đúng hai protocol riêng. CLI ghi commit, version,
hash nguồn/artifact và sample_count=1; đây là diagnostic, không là benchmark
hoặc kết luận eKYC. Không commit báo cáo chứa dữ liệu/bằng chứng cá nhân.

Unit/integration test dùng pixel/WAV/vector/verdict tổng hợp; kiểm lấy mẫu theo
PTS/offset, đổi người ở một mẫu, sai/thiếu artifact, trộn phiên/lượt/nguồn, đổi
media trong lúc chạy, giải mã lease, gate và lưu/loại kết quả theo lượt.
