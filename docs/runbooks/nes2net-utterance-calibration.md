# Đo và hiệu chỉnh NES2Net toàn câu

Entry point `python -m vericlue_ml.eval.nes2net_utterance prepare|collect|fit`.
Đây là công cụ nghiên cứu offline, chưa nối phép gộp mới vào API/Android.

## Giao thức cố định trước khi đo

Version `nes2net-x@c9fe1177f44040f002cb40def928332d2e261f1e+hf4576-cpu-fp32-timeline4s-tail-maxmargin-v1`.
Giữ lưới 4 giây/đuôi neo cuối của VOICE-13. Điểm toàn câu là **max của margin
spoof − bonafide** khi **mọi** cửa sổ đã đo, kể cả cửa sổ chồng lấn. Cửa sổ lỗi
hoặc thiếu tiếng vẫn nằm trong evidence và làm score toàn câu null. Không chỉ
kiểm độ phủ rồi bỏ qua cửa sổ lỗi. Câu ngắn vẫn lặp theo recipe đã công bố.

Kết quả vẫn degraded/unclear, prob_attack=null; đây là candidate chưa đánh giá,
có thể tăng báo động với câu dài. Không chọn lại phép gộp bằng test. Artifact
first4s/timeline cũ không khớp version mới. Không thay thresholds/router.

## Manifest dữ liệu

JSON nội bộ `schema_version=1`, `dataset` và `samples` không rỗng. Mỗi mẫu cần:

| Trường | Nội dung |
|---|---|
| sample_id | ID duy nhất |
| subject_ids | Mọi người liên quan: giọng gốc, donor/target của VC; namespace/crosswalk nhất quán |
| source_group | Họ nguồn gốc; mọi bản gốc/clone/nén/cắt cùng nguồn dùng cùng nhóm |
| split | calib_fit, calib_ltt hoặc test, chốt trước inference |
| label / attack_type | 0 / bonafide hoặc 1 / loại TTS, VC, replay cụ thể |
| audio / audio_sha256 | Path tương đối dưới data-root, SHA256 file; mono16k, tối đa30giây/32MiB |
| source_dataset / source_revision | Publisher và revision bất biến |
| rights_reference | Bằng chứng quyền sử dụng đúng tác vụ, không suy từ tên bộ |
| usage | calibration_evaluation hoặc test_only |

`prepare` kiểm hash byte/PCM trùng, người/nguồn giao split, nhãn, đường dẫn và
giới hạn decoder. Quyền khai báo vẫn cần được xác nhận ngoài công cụ. VIVOS và
nguồn test_only không vào hiệu chỉnh. Không đổi tên nguồn/split để hợp thức hóa
32 mẫu parity. Không có mã người/nguồn thì chưa sẵn sàng.

Người và nguồn liên kết được hợp thành cùng nhóm cho cả split lẫn GroupKFold.
Không bịa người cho TTS không có reference. Chốt hệ TTS chỉ-test trước đo nếu
đánh giá hệ chưa thấy; test không chọn model, phép gộp hoặc ngưỡng.

Theo ADR-0015, tải/chuẩn bị dữ liệu dạy/hiệu chỉnh trên Kaggle/Colab, nhận bundle
đã kiểm nguồn/split để đo offline. Không tự thu hoặc nhân bản giọng khi quyền
đúng tác vụ chưa được xác nhận. [Nguồn và phần còn thiếu](../research/2026-11-01-voice-calibration-prep.md).

## Chạy

Dùng runtime NES2Net có SoundFile/WebRTC VAD và calibration hiện có:

```powershell
$env:PYTHONPATH = 'ml/src'
$py = 'D:/vericlue/tmp/nes2net-cpu/Scripts/python.exe'
$env:HF_HUB_OFFLINE = '1'
$env:TRANSFORMERS_OFFLINE = '1'
# Đặt NES2NET_PARITY_REPORT và NES2NET_PARITY_SHA256 theo bản đã review.
& $py -m vericlue_ml.eval.nes2net_utterance prepare --manifest <manifest.json> --data-root <bundle> --output <audit-moi.json>
& $py -m vericlue_ml.eval.nes2net_utterance collect --manifest <manifest.json> --data-root <bundle> --models-dir <models> --output <measurements-moi.json>
& $py -m vericlue_ml.eval.nes2net_utterance fit --report <measurements.json> --output <candidate-moi.json>
```

Collect/fit đòi source commit sạch. Collect cần parity đã bind; giữ mọi mẫu,
checkpoint/config/code/runtime, manifest/split và timeline/kết quả gộp. Input
đổi bị từ chối hoặc ghi E_INTEGRITY. Fitter tính lại gộp, kiểm provenance/group
và chỉ lấy mẫu đủ điểm trong calib_fit. Mẫu thiếu/lỗi có số loại riêng, không
đổi status thành ok. GroupKFold vẫn cần đủ nhóm và cả hai lớp; thiếu thì lỗi.

Output fit bọc Calibrator với hash report, commit đo và commit fit riêng. Không
tự cài vào CalibrationStore/API hoặc chọn ngưỡng LTT. Cần review artifact,
ROUT-03 trên calib_ltt và đánh giá test sau khi khóa protocol. JSON/media thật
để ngoài Git; unit/native smoke không thay kết quả thực nghiệm.
