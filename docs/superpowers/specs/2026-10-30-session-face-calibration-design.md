# Hiệu chỉnh PAD/GenD theo video phiên — thiết kế

Ngày: 30/10/2026. Nguồn: `94be648`. Phạm vi đầu tiên của mục 2 trong rà soát demo.

## Mục tiêu và giới hạn

Hoàn thiện đường code từ số đo PAD/GenD trên video phiên tới xác suất hiệu chỉnh
đúng protocol. Người dùng sẽ tự thử điện thoại sau. Có thể hoàn thiện công cụ và
test bằng dữ liệu tổng hợp; chỉ xuất artifact hiệu chỉnh sử dụng thực tế sau khi
có dữ liệu phù hợp chạy qua đúng pipeline. Không tạo số liệu hay ngưỡng giả.

Không mở guard `SessionFlow.ensure_flow_available`, không đổi
`ml/configs/thresholds.yaml`, không hạ lỗi/degraded thành đạt, không coi phần này
là đã hoàn thành giọng, ánh sáng, danh tính hay ghi danh tài khoản. Quyền lưu mẫu
SEC-09 là hạng mục tiếp theo với thiết kế hợp đồng riêng.

## Lựa chọn thiết kế

Dùng lại `CalibFit`, `fit`, `CalibrationStore` và version đầy đủ của
`SessionAttackDetector` thay vì tạo bộ hiệu chỉnh thứ hai hoặc dùng ngưỡng tay.
Các thành phần hiện có đã kiểm lớp, nhóm người, tham số và phiên bản. Viết thêm
lớp điều phối cho dữ liệu video và kiểm điều kiện sử dụng artifact; không dùng
script `fit_calibrators.py` cũ vì script đó chạy sampling/model cũ.

## Luồng dữ liệu

1. Manifest nghiên cứu cục bộ có mã mẫu/nhóm người, split, nhãn 0/1, đường dẫn
   video và lịch thử thách tương ứng. Đường dẫn phải nằm trong data root. Mỗi
   lịch phải khớp phiên/lượt trong đầu vào; không sửa lịch để hợp thức hóa video.
2. Lệnh đo trong `vericlue_ml.eval` dùng chính `session_views` và backend hiện có;
   giữ đúng tiền xử lý và phiên bản `frames_version + session-video-v1`.
   Không xuất ảnh, embedding hoặc nội dung CCCD. Ghi hash nguồn/lịch, module,
   phiên bản, commit, trạng thái/lỗi, raw score và nhãn/nhóm trong báo cáo local.
3. Không âm thầm loại mẫu lỗi. Báo cáo giữ mọi mẫu, thống kê mẫu chấm được và
   không chấm được theo lớp. Từ chối trùng hash, trùng mã hoặc nhóm người xuất
   hiện ở nhiều split. Kiểm các split trước khi lọc mẫu lỗi.
4. Lệnh fit chỉ nhận mẫu `calib_fit` có raw score hợp lệ, đủ hai lớp và đủ nhóm
   cho cross-validation. Dùng phương pháp chọn Platt/isotonic hiện có. Nhãn
   `calib_ltt` và test không tham gia fit/chọn phương pháp. Ghi provenance/hash
   báo cáo đầu vào trong artifact; không ghi đè artifact đang dùng mặc định.
5. Artifact có đúng module và version đầy đủ. Các số trong báo cáo lấy từ lần
   chạy, kèm số mẫu/lớp/nhóm và phạm vi group OOF, không gọi đó là kết quả test.

## Áp dụng trong detector và router

- Mặc định chưa có artifact: giữ `degraded/unclear`, `prob_attack=None`, raw
  score vẫn dùng cho chẩn đoán. Giữ tương thích các lần demo hiện tại.
- Chỉ chấp nhận `Calibrator` đã fit, đúng module/version, không phải identity
  hoặc artifact provisional. Calibrator ảnh tĩnh, video cũ hoặc ba góc chưa có
  hậu tố phiên không được dùng thay thế.
- Backend phải trả `ok`, đúng version gốc, score hữu hạn và đúng phạm vi; video
  vẫn phải qua kiểm hash và chọn khung hiện hành. Không phục hồi score từ error,
  degraded hoặc not_applicable. Kết quả không chứa xác suất do backend tự gửi.
- Khi đủ điều kiện, adapter giữ raw score, gắn version phiên và xác suất từ
  artifact; đánh dấu calibrated trong quality. Gate phân loại không tự đổi
  thành pass. Router vẫn quyết định bằng policy hiện hành. Router tính lại từ
  raw score nên không hiệu chỉnh xác suất hai lần.
- Cấu hình kho qua `CALIBRATORS_DIR` hiện có. Nạp/cache một lần theo version;
  đổi artifact cần khởi động lại. Không tải model hoặc artifact lúc inference.
- Artifact thiếu/hỏng/sai version hoặc điều kiện đầu vào không đạt đều không
  được tạo đường pass; không fallback sang ngưỡng hay calibrator cũ.

## Kiểm chứng bắt buộc

- Test đỏ trước code: thiếu artifact, identity/provisional, sai module/version,
  score thiếu/NaN, lỗi backend, video thay đổi; valid artifact phải khớp kết quả
  tính trực tiếp của calibrator, không tin prob_attack/gate do backend gắn sẵn.
- Test manifest/fit: trùng video, nhóm giao nhau dù mẫu lỗi, nhãn ngoài 0/1,
  thiếu lớp, đường dẫn thoát root, fit từ test/calib_ltt đều bị từ chối.
- Test API/router: artifact hợp lệ không mở guard sinh trắc; mọi mô-đun bắt buộc
  lỗi/degraded vẫn không được pass. Không ảnh hưởng OTP demo.
- Chạy test ML/API liên quan và Ruff. Không cần camera, GPU hoặc model thật cho
  unit test. Kết quả tổng hợp chỉ chứng minh code, không phải đánh giá AI.

## Bàn giao

Code detector/công cụ, format manifest và lệnh chạy; test và handoff nêu rõ còn
thiếu dữ liệu thật. Không ghi task ROUT-03 hoặc toàn bộ demo là done. Sau phần
PAD/GenD mới thiết kế tiếp artifact/đánh giá cho giọng, danh tính và ánh sáng;
không tái dùng một calibrator chung cho các loại điểm khác nhau.
