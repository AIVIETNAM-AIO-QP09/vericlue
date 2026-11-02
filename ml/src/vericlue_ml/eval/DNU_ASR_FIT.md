# Đối chứng nội dung ASR trên DNU calib_fit

`python -m vericlue_ml.eval.dnu_asr_fit` dùng protocol riêng đã khóa trước suy luận:
một WAV native 16 kHz mono PCM16, dài 1–30 giây cho mỗi người trong 18 người
calib_fit. Chọn thứ tự SHA256 của `app03-dnu-asr-fit-v1:` + sample ID; không chọn
theo nội dung transcript hoặc kết quả điện thoại. Không mở audio/metadata
calib_ltt/test, không fit ngưỡng và không cài artifact vào API.

Protocol giữ SHA256 của manifest, metadata train, LICENSE và public-release
approval tại revision DNU `33b2a469901cb71b243403254d3cfef25170526c`.
Adapter kiểm crosswalk `DNU:audio_id`, `DNU:speaker_id`, `file_name`, checksum và
`text_normalized`; checksum WAV được kiểm trước/sau suy luận. Nhãn chỉ tới luật
so khớp và bộ đếm âm tiết, không tới context/hotword của ASR. Nguồn dữ liệu ghi
CC BY-NC 4.0; đối chứng nghiên cứu không cấp quyền nhân bản hoặc xác thực người
trong dữ liệu.

Chạy từ gốc checkout bằng PowerShell, dùng SHA protocol đã ghi tại bước chọn mẫu:

```powershell
$env:PYTHONPATH = (Resolve-Path ml/src).Path
$fitProtocol = 'D:/vericlue/tmp/asr-comparison-2026-11-03/protocol-preselected.json'
$fitProtocolSha = (Get-Content 'D:/vericlue/tmp/asr-comparison-2026-11-03/protocol-preselected.sha256').Trim()
D:/vericlue/.venv/Scripts/python.exe -m vericlue_ml.eval.dnu_asr_fit --protocol $fitProtocol --protocol-sha256 $fitProtocolSha --check-only
```

Hai candidate chạy tuần tự, trong runtime riêng: Qwen hiện tại dùng Transformers
5.13.0; PhoWhisper dùng 4.57.6, cùng CPU FP32 và VAD1. Không nâng runtime server.
Ví dụ đường dẫn runtime/model/output bên dưới thuộc vùng riêng, không commit:

```powershell
D:/vericlue/tmp/av-lab-cpu/Scripts/python.exe -m vericlue_ml.eval.dnu_asr_fit --protocol $fitProtocol --protocol-sha256 $fitProtocolSha --backend qwen --models-dir D:/vericlue/models/selected-2026-10-24 --output D:/vericlue/tmp/asr-comparison-2026-11-03/qwen-fit18.json
D:/vericlue/tmp/asr-comparison-2026-11-03/phowhisper-runtime/Scripts/python.exe -m vericlue_ml.eval.dnu_asr_fit --protocol $fitProtocol --protocol-sha256 $fitProtocolSha --backend phowhisper --models-dir D:/vericlue/tmp/asr-comparison-2026-11-03/models --output D:/vericlue/tmp/asr-comparison-2026-11-03/phowhisper-fit18.json
```

Mỗi file output phải mới. JSON/stdout không có transcript, đường dẫn media hoặc
ID người; từng người dùng số thứ tự cục bộ. Giữ mẫu lỗi/degraded trong mẫu số
18 của tỷ lệ không đạt; WER thiếu là null, không tính là 0. Mean WER chỉ trên
mẫu có kết quả phải đọc cùng số mẫu thiếu/lỗi; không so hai mean có mẫu số khác
để tuyên bố candidate tốt hơn. Báo riêng thời gian preload, độ trễ, revision,
hash nguồn/config/trọng số và phiên bản Python/thư viện thực tế.

Đây là chẩn đoán nội dung trên 18 mẫu bona fide, không đo spoof/APCER, LTT,
khớp môi hoặc khả năng nghiệm thu trên điện thoại. Không quyết định đổi model
từ kết quả ca điện thoại được giữ lại.
