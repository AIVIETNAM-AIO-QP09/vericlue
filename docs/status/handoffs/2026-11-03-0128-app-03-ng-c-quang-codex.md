# Bàn giao · APP-03 · Ngọc Quang+Codex · 2026-11-03 01:28

**Nhánh:** `codex/APP-11-s24fe-integration`
**Trạng thái task sau phiên này:** `doing` — chưa nghiệm thu khôi phục thật.

## Đã xong
- Android: sửa FIT preview, giới hạn chờ phản hồi AI riêng và kiểm phản hồi trước
  giải phóng bản thu; APK `03b4abc03b43b1dbc511423f610ac37596f09287` đã build.
  Chi tiết RED/GREEN và lượt S24 FE nằm trong bàn giao `2026-11-03-0001`.
- Thêm `eval.dnu_asr_fit` và hướng dẫn cùng thư mục: 18 WAV/18 người calib_fit
  được khóa bằng protocol trước suy luận, chọn cố định theo hash ID. Kiểm
  crosswalk đủ 360 mẫu fit, nhãn train, checksum, revision, giấy phép/approval.
- Giữ toàn bộ lỗi trong mẫu số 18, WER thiếu là null; báo nguồn/config/model/
  runtime và thời gian nạp. Không transcript, ID người hay đường dẫn media
  trong báo cáo. Nhãn chỉ tới matcher/bộ đếm âm tiết, không đưa vào ASR context.
- PhoWhisper tải riêng theo manifest đã pin và kiểm hash; runtime riêng
  Transformers 4.57.6 đã chuẩn bị. Qwen dùng runtime 5.13.0 có sẵn. Chưa đổi API.

## Đang dở
- Chưa có số đo suy luận của phép so sánh này tại thời điểm commit adapter.
- Nhận dạng câu/khớp môi đã không đạt trên lượt thật trước. Không suy ra đạt
  từ kiểm thử tự động hoặc việc tải đủ mô hình.

## Bước tiếp theo
1. Xác nhận cài APK, giữ tài khoản/khóa/cấu hình. Người dùng đã đi ngủ, không
   tự mở camera hay tự đánh dấu nghiệm thu.
2. Chạy hai candidate tuần tự theo `ml/src/vericlue_ml/eval/DNU_ASR_FIT.md`,
   dùng output mới trong vùng riêng; ghi đầy đủ lỗi và giới hạn 18 mẫu.
3. Tiếp tục kiểm chứng frontend SyncNet bằng artifact nguồn hợp lệ và phép
   biến đổi độc lập; không chọn crop/ngưỡng theo điểm bản ghi điện thoại.

## Quyết định, lưu ý, bẫy
- Người dùng đã cho phép làm tiếp trong đêm và tắt máy sau khi kết thúc; lưu
  đầy đủ bàn giao trước khi tắt. Không force đóng tài liệu chưa lưu.
- OTP mô phỏng và ngưỡng demo tạm giữ nguyên. Error/degraded không thành pass.
- Không dùng điện thoại nghiệm thu, 32 VIVOS parity, calib_ltt hoặc test để
  chọn mô hình/ngưỡng. DNU fit chỉ là chẩn đoán nội dung, không phải đánh giá
  spoof, lipsync, LTT hay mức độ hoàn thiện xác thực.

## Câu hỏi cho nhóm
- Còn cần nghiệm thu người thật và dữ liệu/artifact đúng phiên bản để đánh
  giá ngoài phép chẩn đoán fit. Không lấy số paper thay số hệ thống chạy thật.

## Test đã chạy
- Root chạy `pytest ml/tests/test_dnu_asr_fit.py ml/tests/test_eval_voice_challenge.py`:
  42 ca đạt. Agent có RED khi module chưa tồn tại và review độc lập không còn
  blocker; riêng adapter 13 ca đạt. Ruff check + format check sạch.
- Protocol thật `--check-only`: 18 mẫu/18 người, `inference_performed=false`.
- Android mới nhất: 441 ca, 0 failure, 0 error, 1 export skip; lint 0 lỗi,
  44 cảnh báo/5 thông tin; hai APK build đạt. Plan check 0 lỗi/10 cảnh báo.

## Cập nhật trong đêm

- APK03b4abc đã cài lúc 01:28 ngày 03/11; hash/signer/reverse8421 khớp,
  toàn bộ hàng tài khoản/khôi phục và cấu hình riêng không đổi. Không mở app
  bằng ADB. Sau khi người dùng đi ngủ đã dừng đúng cây tiến trình API để đo
  offline, giữ DB/khóa/media. Lần mở máy sau chạy `START-DEMO.cmd` trong bundle.
- Hai phép đo đầu đã chạy cùng protocol/implementation/source-config hash:
  Qwen0.6 có macro WER 0,08384734, 1/18 câu không đạt; PhoWhisper 0,34766955,
  4/18 không đạt. Cả hai 18/18 status ok, không thiếu WER, không lỗi nạp.
  Nguồn `d81d2564f96a02a614c131957c9782c9d0188eda-dirty`; hậu tố dirty do
  phát triển frontend song song, các file nguồn/cấu hình đo được hash và
  kiểm không đổi trong từng lần, khớp giữa hai báo cáo. Đây là fit diagnostic,
  không phải số test/hệ thống hay kết quả nghiệm thu. Không đổi sang PhoWhisper.
- Đã tải ứng viên Qwen1.7B từ repo gốc tại revision
  `bcd2b5b7f32b480ab5790554cfa8347f246a14f3`, kiểm Git blob/LFS và safetensor
  header trước suy luận. Có adapter offline riêng; 0.6 vẫn giữ nguyên pin,
  cấu hình mặc định và đường API. Chưa có số đo 1.7 tại commit adapter.
- Root chạy nhóm hồi quy Qwen/DNU/PAD/notebook: **204 đạt, 1 bỏ qua, 0 lỗi**.
  Root chạy landmark/frontend/resize/PTS trên runtime có Torch: **125 đạt**.
  Kiểm thử này chưa thay smoke mô hình thật hoặc xác minh khớp môi.

## Đối chứng ASR đã chạy đủ ba ứng viên

Protocol `app03-dnu-asr-fit-v1`, SHA-256
`a2043267208e2203779b60a4b941fc8a97757591c5b96c44991f45ff6836b386`;
DNU revision `33b2a469901cb71b243403254d3cfef25170526c`.
18 mẫu/18 người, tổng 163,121 giây; cả ba đều 18 status ok, không thiếu WER.
Các số dưới đây là chẩn đoán **calib_fit**, không phải accuracy tập test/điện thoại.

| Mô hình (revision) | Macro WER âm tiết | Không đạt matcher cố định | Tổng suy luận CPU |
|---|---:|---:|---:|
| Qwen0.6B (`7f1569a48a89f3e3f4dc3a5c9d28bddd903bc76c`) | 0,08384734 | 1/18 | 61,393 giây |
| PhoWhisper-small (`a86b604c346caf7148c37512eafe783a16420adb`) | 0,34766955 | 4/18 | 67,295 giây |
| Qwen1.7B (`bcd2b5b7f32b480ab5790554cfa8347f246a14f3`) | 0,03851427 | 0/18 | 153,201 giây |

Qwen dùng wrapper `cpu-fp32-content-v2-assistant-prefix`, Transformers5.13.0;
Pho dùng `voice04-v2`, Transformers4.57.6; cùng Torch2.14.1+cpu.
Nguồn hai dòng đầu `d81d2564f96a02a614c131957c9782c9d0188eda-dirty`;
dòng cuối `7593ce77c77b69c7b4068b54e69a64d55c8d8a35-dirty`. Báo cáo có hash
nguồn/config trước–sau; dirty do phát triển frontend song song. Dữ liệu LTT/test
không được đọc. Không đưa nhãn vào context ASR, không đổi matcher/ngưỡng.

Báo cáo riêng: `D:/vericlue/tmp/asr-comparison-2026-11-03/`:
`qwen-fit18.json`, `phowhisper-fit18.json`, `qwen17-fit18.json`.
1.7B là ứng viên tốt hơn trên phép đo này, nhưng chậm hơn khoảng 2,5 lần và
trọng số FP32 khoảng 8,15 GB. Chưa chứng minh preload chung toàn stack đủ RAM,
ngân sách worker hoặc tương thích ràng buộc tài khoản. API vẫn dùng 0.6B.

## Frontend khớp môi ngoại tuyến

Đã thêm provider landmark106 có pin/giấy phép và triển khai hình học độc lập;
probe file giữ pixel/PTS gốc, probe RAM có provenance riêng. Không chép mã
StyleSync không có giấy phép. Runbook ghi oracle tổng hợp, sai lệch float32
và giới hạn CPU FP16, không tuyên bố bit-parity upstream GPU.
Review độc lập không còn blocker; root chạy **196 test đạt, 0 bỏ qua** cho
file/RAM/frontend/landmark/PTS/A-V. Native smoke còn phải ghi riêng sau commit.
