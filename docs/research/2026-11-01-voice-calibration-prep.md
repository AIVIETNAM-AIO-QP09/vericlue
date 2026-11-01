# Chuẩn bị dữ liệu giọng toàn câu — 01/11/2026

Người giao việc xác nhận dữ liệu này **chưa từng được chuẩn bị**, không bị xóa
khi dọn dẹp. Chưa có bộ giọng thật + TTS/VC/crosswalk đủ điều kiện fit. Giữ chốt
thiếu artifact; không dùng VIVOS parity, unit hoặc lượt thử điện thoại thay thế.

## Nguồn đã đối chiếu publisher

| Nguồn ghim revision | Quyền/metadata quan sát | Việc cần tiếp |
|---|---|---|
| [DNU-ViSpeech](https://huggingface.co/datasets/TrangLe2108/DNU-ViSpeech/tree/33b2a469901cb71b243403254d3cfef25170526c) | CC-BY-NC4.0, speaker_id/checksum/split; có public-release approval của publisher, card ghi giới hạn consent/phạm vi | Bảo toàn người test gốc; chia calib_fit/calib_ltt theo người từ phần phát triển. Xác nhận riêng phạm vi nếu sinh clone/VC |
| [Speech-MASSIVE vi](https://huggingface.co/datasets/FBK-MT/Speech-MASSIVE/tree/ff792febc16187a21e5bca38fb02a55daf91dc05/vi-VN) | CC-BY-NC-SA4.0, speaker_id, mono16k; train_115/validation trên repo publisher | Kiểm người/nguồn xuyên phần và quyền biến đổi; test ở repo riêng có bước chấp thuận |

Ở bước rà nguồn ban đầu chỉ tải card/license/biên bản/metadata; chưa tạo clone
hay fit. Metadata gốc/pin SHA tại
`D:/vericlue/data/diagnostics/nes2net-calibration-prep-2026-11-01/` ngoài Git.
Đã dựng `DNU-bonafide-proposed-manifest.json` từ metadata publisher, chọn bằng
hash seed42 trước inference và giữ người train/validation/test tương ứng
calib_fit/calib_ltt/test-only. Manifest ban đầu chỉ là ứng viên; kết quả tải
audio/kiểm PCM trên cloud và laptop được bổ sung bên dưới. Vẫn thiếu lớp tấn
công và quyền clone/VC chưa chốt.
Không chép code của bộ dữ liệu. Giấy phép dữ liệu không tự xác nhận tác giả
cho mọi ứng dụng định danh hoặc nhân bản giọng.

## Bundle cần chuẩn bị trên Kaggle/Colab

1. Lưu publisher/revision/license/quyền đúng tác vụ và mã nguồn âm thanh.
   Không trộn hai bộ khi chưa có crosswalk người/nguồn.
2. Chốt người/nhóm cho calib_fit/calib_ltt/test trước inference; giữ người test
   gốc, các bản gốc/clone/cắt/nén cùng nhóm. Chốt hệ TTS chỉ-test trước đo.
3. Cần cả thật và từng loại tấn công có quyền; giữ hệ/version/seed và
   reference/donor/target/parent audio. Thiếu một bên thì chưa fit.
4. Thật/giả qua cùng đường xử lý. Nếu resampling thì version hóa bước chuẩn bị,
   giữ hash gốc lẫn file đo, không âm thầm đổi protocol.
5. Xuất manifest theo [runbook](../runbooks/nes2net-utterance-calibration.md),
   chạy prepare kiểm trùng byte/PCM/người/nguồn và báo thiếu quota; không chuyển
   người test hoặc chọn mẫu bằng điểm NES2Net.

Chưa có accuracy/ngưỡng LTT hay nghiệm thu Android từ bước rà nguồn. Chuẩn bị
tấn công và chạy hiệu chỉnh/đánh giá vẫn còn phải làm.

## Tiếp tục tự động hóa sau yêu cầu người dùng

Đã có `scripts/prepare_nes2net_data.py` và notebook sinh từ source đã kiểm:
`ml/notebooks/prepare_nes2net_data.ipynb`. Source đã qua test trên Linux, gồm
symlink thoát thư mục, resume, lỗi bytes/WAV, trùng PCM và archive allowlist.
Đã smoke đúng downloader với một WAV publisher trong RAM, hash/header hợp lệ;
không lưu audio, không suy luận hoặc hiệu chỉnh từ smoke này.

Colab yêu cầu chấp thuận Điều khoản dịch vụ khi tạo notebook. Người dùng đã
ủy quyền rõ bước Đồng ý; job CPU thật đã chạy và nhận bundle như ghi dưới đây.
Việc này độc lập việc người dùng chưa thể thử điện thoại.

Nguồn lớp giả đã đối chiếu thêm:
[MLAAD publisher](https://huggingface.co/datasets/mueller91/MLAAD), revision
`30c3dec763fa4803f11c2df1557d3b0828395366`, CC-BY-NC4.0, gated auto. Public
file-tree tiếng Việt hiện có LEMAS-TTS, OmniVoice, VieNeu-TTS, VoxCPM2, vixTTS.
Chưa truy cập payload audio/meta.csv bị gate; cần quyền đã cấp trước khi kiểm
reference_speaker/original_file và chia nhóm. Không giả định mỗi hệ là một người,
không dùng mirror để lách quyền truy cập và không tự chấp thuận điều khoản.

## Kết quả chuẩn bị DNU thật trên Colab CPU (12:27, 01/11)

- Source commit `140beb55d27e7c4ae2f4bf8883117c7c2a1553e6`, script SHA-256
  `52c7a43c04f67893fb109f693a77e27805d07db2e1fbee1465dde7525a1baac5`.
  Cell thực thi đã đối chiếu nguyên văn với notebook sinh sạch trong repo.
- Lần đầu 517 WAV hợp lệ, 3 HTTPError. Giữ bằng chứng và chạy lại cùng cell:
  dùng lại 517, tải nốt 3, errors rỗng; không đổi mẫu/người/seed/split.
- 520 WAV native mono16k PCM16, 20 mẫu/người: calib_fit360/18người,
  calib_ltt80/4người, test80/4người. Không inference/fit/chọn ngưỡng.
- ZIP 114802930 byte, 527 tệp allowlist; SHA-256
  `972aaae1fa8a1da1b1bdf2efed56aa4668e6dce9eb2c8d56ceb9b50463677d74`.
  Manifest SHA-256
  `c4fc4b3498c210410a79bd00cc0ba11109cd88784260be18ccc9f43f0584a16b`.
- Đã nhận về `D:/vericlue/data/prepared/vericlue-dnu-bonafide-30ff4361.zip`,
  giải nén vào `D:/vericlue/data/prepared/nes2net-dnu-bonafide-2026-11-01-30ff4361/`.
  Kiểm containment/không symlink, allowlist, SHA ZIP và toàn bộ tệp trước giải nén.
- Kiểm độc lập bằng `vericlue_ml.eval.nes2net_utterance prepare` tại commit
  `bdea478c5ebe95aa912b03f4a3f3c2cfe48064d9`, Python3.12.15: 520 mẫu/26nhóm;
  hash/native decoder/trùng byte và PCM float32/người/nguồn qua kiểm tra.
  Báo thiếu attack cả ba phần và attack calib_fit0/100; calibration_fitted=false.
- Báo cáo, receipt/provenance, notebook lỗi lần đầu và ảnh Colab lưu ngoài Git tại
  `D:/vericlue/tmp/finish-2026-11-01/cloud-data/`; không commit audio hoặc ZIP.

Đây là **bundle lớp thật đã kiểm**, không phải bộ hiệu chỉnh đủ hai lớp. VIVOS
parity vẫn ngoài hiệu chỉnh. Chưa có calibrator/LTT hoặc bằng chứng nghiệm thu.
Chrome hiện chưa đăng nhập Hugging Face; đã mở đúng trang đăng nhập để chủ tài
khoản tiếp tục, chưa chấp thuận điều kiện MLAAD/chia sẻ thông tin tài khoản.

## Rà nguồn tấn công công khai bổ sung · 18:44 ngày 01/11

Chỉ rà tài liệu publisher, chưa tải payload hoặc dùng nguồn mới để fit/chọn
ngưỡng. Không coi việc có link công khai là đủ metadata/người/nguồn cho split.

- [VoiceSpoof-VN](https://github.com/coronatusvi/ASVspoof2025_VN),
  README tại commit `5b899f33c98e2c0a08d69fe4a0bc34029ae2f0f1`: tác giả mô tả
  corpus thật/tấn công có người nói và cho nghiên cứu học thuật,phi thương mại;
  dẫn Google Drive `LA.zip`. Git tree chỉ có README/ảnh sơ đồ, chưa có protocol
  hoặc crosswalk donor/target/source để kiểm. Đây là ứng viên cần kiểm archive,
  quyền đúng tác vụ và nguồn gốc từng nhóm trước khi quyết định dùng; không
  tự thêm vào data-plan hoặc gọi đủ dữ liệu hiệu chỉnh.
- [RADAR2026 publisher](https://zenodo.org/records/22110815): release ghi CC-BY4.0,
  tiếng Việt nằm trong **evaluation**, development chỉ tiếng Anh. Giữ phần VI
  làm ứng viên test độc lập, không chuyển sang calib_fit để lấp lớp tấn công.
  Các protocol công bố chưa cho thấy crosswalk người/nguồn; chưa tải archive.
- [VietPrism preprint v1](https://arxiv.org/html/2609.30005v1): mô tả ghép
  thật/giả theo người, nhưng lượt rà này chưa xác minh được publisher download,
  giấy phép corpus và metadata có thể nhận. Giữ nhận định chưa sẵn sàng trong
  data-plan; không lấy quyền của bài báo thay quyền dữ liệu.

Kết luận vận hành không đổi: lớp thật DNU đã kiểm, lớp TTS/VC còn thiếu bằng
chứng sử dụng/metadata đủ chuẩn. Chưa có calibrator hoặc nghiệm thu sinh trắc.

## Smoke toàn câu bằng DNU thật · 01/11

- Code nguồn sạch `6b7589692e4158335a07dc8307ea5d4704847803`. Chọn theo sample_id
  tăng dần, lấy mẫu calib_fit đầu tiên của3người khác nhau, trước inference;
  không đọc/chấm calib_ltt/test. Manifest gốc giữ SHA đã ghi phía trên.
- Native collect dùng checkpoint SHA `3158d10c6fc3c58e452a33981b409f5a65ecf91d548931b4ffbd675462799685`,
  version `nes2net-x@c9fe1177f44040f002cb40def928332d2e261f1e+hf4576-cpu-fp32-timeline4s-tail-maxmargin-v1`.
  Runtime Windows,Python3.12.15,Torch2.14.1+cpu,Transformers4.57.6,4CPUthreads;
  report parity canonical SHA `669bf62e4db134a46e8a0dd8f3d5b6a72bba90a984c3a7901fa8e866e8f21a48`.
- Cả3mẫu có raw score toàn câu khi đủ các cửa sổ, vẫn degraded/unclear,
  prob_attack absent/null. Chỉ3giọng thật, không thử fit/chọn ngưỡng/chạy test,
  không accuracy hoặc deploy, calibration_ready=false.
- Manifest subset/measurement/audit/summary ngoài Git tại
  `D:/vericlue/tmp/publish-review-2026-11-01/dnu-train-smoke/`.
  Measurement SHA `375ee672601f2a3291d126e0942eb1342df8c6436b24a16552091afcd3c8ce9d`.
  Native collect đã hoàn tất; helper ngoài Git từng import nhầm và xử lý thiếu
  keyprob_attack vốn bị bỏ khi null. Đã sửa summary đọc report có schema/provenance,
  giữ nguyên phép đo, không suy thời gian chạy từ lượt dựng summary.
