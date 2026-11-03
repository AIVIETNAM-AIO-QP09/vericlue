# Đối chứng tiền xử lý hình SyncNet (APP-03)

Đây là công cụ ngoại tuyến để kiểm tra khác biệt recipe căn mặt. Chưa nối API,
không có calibrator tương thích, không chứng minh khớp môi đạt hay độ chính xác.
Không chọn crop, dtype, offset hoặc ngưỡng bằng kết quả bản ghi điện thoại.

## Nguồn và phiên bản

- Caller tham chiếu: ByteDance/LatentSync
  `a229c3948406bc2cf6eaf4873e662e70c6a04746`,
  `latentsync/utils/image_processor.py`, `face_detector.py` (Apache-2.0).
- `voice.landmarks106.Landmark106Provider`: recipe crop/đảo kênh/ánh xạ ngược
  từ InsightFace MIT `3e6486942a1be2da0e5b475fac375ea73264bd21`.
  [Giấy phép và nguồn](../../third_party/README.md#app-03--landmark-106-cho-đối-chứng-frontend-khớp-môi).
- Trọng số gốc `buffalo_l` v0.7 / `2d106det.onnx`: 5.030.888 byte,
  SHA-256 `f001b856447c413801ef5c42091ed0cd516fcd21f2d6b79635b1e733a7109dbf`.
  Pin quan sát từ bản tải chính thức, không phải checksum do nhà phát hành
  công bố. Trọng số chỉ cho nghiên cứu phi thương mại, không commit.
- `eval.syncnet_frontend` là triển khai độc lập từ đặc tả toán học;
  không chép/biên dịch mã StyleSync không có giấy phép.
  Phiên bản CPU dùng ở probe:
  `syncnet-spatial-independent-v1-r256-numpy-float32+kornia-float32`.

Mô hình landmark đã chứa phép trừ 127,5 và chia 128. Input ngoài là float
pixel 0…255, không chuẩn hóa lần hai. `color_order="rgb"` mô tả input caller;
adapter đảo kênh đúng một lần như caller upstream, không tự sửa thành RGB.
Nạp byte đã kiểm hash vào một ONNX Runtime CPU session duy nhất.

## Cách ghép

```python
from vericlue_ml.face.pad import ScrfdFaceFinder
from vericlue_ml.voice.landmarks106 import Landmark106Provider
from vericlue_ml.eval.syncnet_frontend import SyncNetFrontendCandidate
from vericlue_ml.eval.syncnet_file_frontend_probe import prepare_file_frontend_probe

finder = ScrfdFaceFinder(verified_scrfd_session, input_size=512, scale=128, swap_rb=True)
landmarks = Landmark106Provider(landmark_path, color_order="rgb")
frontend = SyncNetFrontendCandidate(warp_dtype="float32", device="cpu")
probe = prepare_file_frontend_probe(
    video_path,
    fixed_starts,
    audio_offset_s=original_audio_offset_s,
    finder=finder,
    landmark_provider=landmarks,
    frontend=frontend,
)
```

Caller phải kiểm pin SCRFD, lưu phiên bản/source/runtime và tạo `fixed_starts`
từ cùng ForcedAligner + `_window_starts` của baseline. Dùng lại đúng audio,
mel, offset PTS và trọng số SyncNet. Không đưa câu mong đợi vào ASR.

API hiện dùng file video, vì vậy đối chứng phải dùng
`syncnet_file_frontend_probe` (`original-file-opencv-pts-v1`): đọc pixel gốc
bằng OpenCV, không JPEG, resize trước landmark, seek theo FPS hoặc dịch audio.
Giữ cách chọn nearest PTS/tie sớm hơn/EOF và giới hạn sai số 40 ms của
`voice.syncnet._read_windows`. Căn mọi khung theo thứ tự, kể cả đuôi không
được chọn, để giữ lịch sử bias. Lỗi ở đuôi cũng làm probe thất bại.

Giới hạn: 21 giây, 1.200 khung, 1.920×1.080 pixel/khung, tối đa 4 cửa sổ,
64 crop được giữ cộng khung làm việc hiện tại/trước đó. Thiếu mặt, nhiều mặt,
PTS sai, quá giới hạn hoặc số không hữu hạn đều dừng; không trả score giả.
`probe.windows` chỉ ở RAM; báo cáo chung chỉ chứa counts/provenance.

`syncnet_frontend_probe.prepare_frontend_probe` dành riêng cho `AVRecording`
RAM/JPEG của lab. Không dùng nó để tuyên bố parity pipeline file của API.
`ScrfdFaceFinder` vẫn mặc định 640; 512 là tham số riêng cho probe này.

## Bằng chứng và giới hạn ngày 03/11

- Oracle dùng session giả và mã InsightFace MIT độc lập: 166/166 trường hợp
  landmark khớp chính xác tensor và tọa độ; SCRFD512 48/48 trường hợp khớp
  tensor, box, điểm, landmark5 và thứ tự NMS. Đây chưa phải native smoke.
- Đối chứng hình học tổng hợp: 8 khung và 3 phép fit; điểm mốc khớp, sai lệch
  ma trận tối đa 3,0517578125e-5. Cùng ma trận thì warp/Lanczos byte khớp;
  ma trận tính độc lập gây sai lệch tối đa 1 mức byte ở 1.087 phần tử.
  Chưa cô lập khác biệt vào riêng SVD; có khác thứ tự tính/giảm float32.
- CPU FP16 cho phần tử không hữu hạn ở phép warp không đồng nhất; probe
  dùng FP32 được khai báo trước. Không suy ra parity GPU FP16/Torch 2.5.1.
- Runtime oracle: NumPy 2.5.4, OpenCV 4.14, Torch 2.14.1+cpu, Kornia 0.8.0.
  Không suy rộng bit-parity sang runtime khác.
- Root: 196 test cho file/RAM/frontend/landmark/PTS/A-V đạt, không bỏ qua.
  Báo cáo native riêng phải ghi commit, model/runtime và số đầu vào trước
  khi diễn giải; không lấy số tổng hợp này thay phép đo mô hình thật.

Sau khi có kết quả vẫn cần review phiên bản, ngân sách CPU/RAM và chốt
tương thích trước mọi đề xuất đưa vào server. Calibrator cũ không tự tương
thích khi thay tiền xử lý. Thiếu bằng chứng thì giữ trạng thái chưa nghiệm thu.

## Sửa biên số học khi đổi sang byte

Lượt native đầu dừng ở kiểm miền pixel trước Lanczos. Đối chứng tổng hợp
riêng (không model/media) tái hiện 4/9 trường hợp Kornia FP32: ảnh trắng có
pixel 255,00001525878906 hoặc 255,00003051757812; ảnh đen có -0,00001513958.
Đó là sai số làm tròn phép blend/fill, không phải bằng chứng lệch hình học.

Chỉ tại bước đổi byte, cho phép một biên số học kỹ thuật nhỏ hơn0,001 mức
byte, tính từ gamma32 và tổng trị tuyệt đối các hạng pixel/fill. Clip trong
biên này cho byte đúng bằng cách truncate trực tiếp; sai lệch0,002 trở lên
hoặc NaN/Inf vẫn lỗi. Không đổi ma trận, dtype warp, đồng hồ, ngưỡng AI.
Đây không phải chứng minh biên sai số phổ quát của Kornia hoặc parity FP16.
RED 4 ca lỗi đúng chỗ; root chạy frontend + file/RAM probe: **115 ca đạt**.
Lượt lỗi đầu vẫn được giữ trong vùng riêng.

## Native sau sửa biên FP32

Đã chạy trên commit `fb8c2bf2ad13c45461caeb4d58c85024b66e0e8c`, CPU với
NumPy2.5.4, Torch2.14.1+cpu, Kornia0.8.0, OpenCV4.14.0 và ONNX Runtime1.31.0.
Một bản ghi cũ được chọn bằng khoảng cài APK đã khóa trước khi chạy; không
lọc theo điểm/chọn lại clip. Child hoàn tất84,661 giây:4 cửa sổ,232 khung căn,
64 khung chọn,123.652 mẫu audio. Hai phía dùng cùng aligner/window starts,
audio/mel/PTS và trọng số; media nguồn cùng cấu hình/file đã dùng không đổi.

Đối chứng thay đồng thời detector512/landmark106/cănFP32, không cô lập nguyên
nhân vào từng thành phần. Visual input và phản hồi mô hình thay đổi; offset
ưu tiên không đổi và khác biệt với clock gốc vẫn còn. Vì vậy **chưa chứng
minh decoder/PTS có lỗi mới hoặc lipsync đã đạt**, không đưa frontend này vào
API, không chọn offset/crop/dtype/ngưỡng từ clip. Cần kiểm recipe/parity và
bằng chứng A/V có thời gian tham chiếu, sau đó hiệu chỉnh đúng phiên bản.

Báo cáo riêng `native-file-probe-private-v2/result-private.json` nằm dưới
`D:/vericlue/tmp/syncnet-frontend-2026-11-03`; giữ điểm/offset/ID/media ở vùng
riêng. Xem [bàn giao cuối](../status/handoffs/2026-11-03-0257-app-03-ngoc-quang-codex.md)
về triển khai và phần nghiệm thu còn mở.
