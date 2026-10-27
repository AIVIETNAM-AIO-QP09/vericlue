# Giọng nói trong API phiên — VOICE-14

Opt-in nối các lõi đã có trong lab vào API, không thay UI, hợp đồng HTTP hoặc
ngưỡng. Bước giọng dùng cùng audio server đã nhận cho Qwen ASR, nhịp đọc CTC,
NES2Net theo đoạn và SyncNet. Câu cần đọc lấy từ phiên server; Qwen không nhận
nội dung câu làm gợi ý giải mã. CTC ép căn câu chỉ đo thời gian, không chứng minh
người dùng đã đọc đúng.

## Cấu hình

```powershell
$env:SESSION_VOICE_MODELS='true'
$env:VOICE_RUNTIME_PYTHON='<runtime av-lab-cpu>/Scripts/python.exe'
$env:VOICE_SPOOF_PYTHON='<runtime nes2net-cpu>/Scripts/python.exe'
$env:MODELS_DIR='<kho mô hình theo models/manifest.yaml>'
$env:SESSION_MODEL_TIMEOUT_SECONDS='30'
```

Cài runtime đầu bằng `ml/requirements/av-lab-cpu.txt`, runtime sau bằng
`ml/requirements/nes2net-cpu.txt`. Các editable package/PYTHONPATH cần trỏ cùng
checkout API. Không cài đè Transformers 5 của Qwen lên runtime Transformers 4 của
NES2Net. API chính không cần import Torch của hai worker để điều phối giọng.
Worker chỉ chạy CPU và offline; không tự tải mô hình hoặc truy cập thiết bị.

Kho mô hình cần đủ Qwen ASR 0.6B, CTC aligner, NES2Net, SCRFD và
`syncnet/stable_syncnet.pt` đã pin. Nếu đang giữ checkpoint SyncNet ở kho cũ,
chép vào kho cấu hình và kiểm SHA-256 theo manifest trước khi chạy. Không chép
trọng số vào Git. Runtime được kiểm đường dẫn lúc khởi động; trọng số nạp lười
ở lượt có đầu vào phù hợp, nên health lúc startup chưa chứng minh đã nạp mô hình.

## Điều phối và toàn vẹn

Mỗi API giữ hai worker, một cho Qwen/CTC/SyncNet và một cho NES2Net. Các mô hình
cache trong worker; nhịp đọc và SyncNet dùng chung một forced aligner. Không dùng
shell. Worker đóng theo ứng dụng; timeout hoặc hỏng framing làm worker không còn
khả dụng đến khi khởi động lại API. Lượt chờ hết hạn chưa gửi vào worker không
được giết worker đang xử lý lượt khác.

Mỗi request/reply ràng buộc mã ngẫu nhiên, hash byte request, version mô hình và
SHA-256 media trước/sau inference. Chỉ nhận tệp có giới hạn trong `MEDIA_DIR`.
Không nhận URL, đường dẫn ngoài kho hoặc playlist làm video. Đây là toàn vẹn
IPC nội bộ; chữ ký thiết bị và bằng chứng nguồn camera thuộc SEC-02.

`audio_offset_ms` có nghĩa: mốc bắt đầu WAV trừ mốc bắt đầu video. SyncNet lấy
khung tại `audio_time + offset`, không dùng FPS/seek để thay timestamp decoder.
Version worker thêm `+session-offset-v1`, không dùng lại calibrator cũ.
Chưa xác nhận độ lệch do client khai bằng clock phần cứng hay chữ ký thiết bị.

## Quyết định và giới hạn

Qwen trả kết quả nội dung câu; ModuleResult CTC nằm riêng trong evidence nội bộ,
có trạng thái riêng. CTC lỗi không giả thành đã đo, không ghi đè transcript Qwen.
NES2Net giữ từng đoạn 4 giây và độ phủ; SyncNet giữ điểm thô/offset. Ba đường đo
CTC/NES2Net/SyncNet luôn unclear, không cấp xác suất/đạt khi chưa hiệu chỉnh.
NES2Net degraded là bước bắt buộc nên phiên chưa được pass. Lipsync chỉ tham khảo
ở profile MVP; full vẫn bắt buộc. Không có kết quả accuracy hoặc ngưỡng mới.

Cờ này chạy mô hình thật ngay cả khi `USE_MOCK_MODELS=true`, phục vụ tích hợp
từng phần; thiếu runtime không được quay lại mock. Cờ tắt giữ hành vi cũ.
Khi bật mô hình phiên mặt/giọng, ngân sách inference dùng
`SESSION_MODEL_TIMEOUT_SECONDS` (mặc định 30 s, tối đa 90 s), cộng 0,8 s tại request
cho xử lý policy/lưu DB. Đây là cấu hình demo CPU riêng, chưa đạt SLO cũ 5 s.
Luồng dynamic real/mixed vẫn bị chặn cho đến khi đủ các cổng bắt buộc.
