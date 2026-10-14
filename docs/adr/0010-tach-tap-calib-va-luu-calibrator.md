# ADR-0010: Tách tập calib thành `calib_fit` và `calib_ltt`; lưu calibrator trong `ml/configs/`

- **Trạng thái:** đã chấp nhận — bổ sung cho ADR-0006
- **Ngày:** 2026-10-14

## Bối cảnh

ADR-0006 và các task DATA-03, ROUT-01…03 dùng **chung một tập `calib`** cho ba việc:
1. hiệu chỉnh điểm thô thành xác suất (ROUT-01);
2. học trọng số hợp nhất logistic (ROUT-02);
3. chọn ngưỡng bằng Learn-then-Test (ROUT-03).

Bảo đảm thống kê của Learn-then-Test chỉ đúng khi dữ liệu dùng để chọn ngưỡng **độc lập** với mọi thứ đã được học trước đó. Trọng số hợp nhất học trên chính dữ liệu đó thì bảo đảm bị lạc quan, tức là con số "tỷ lệ lọt ≤ α" không còn đáng tin.

Ngoài ra, task card ROUT-01 ghi lưu calibrator ở `models/calibrators/`, nhưng `models/` bị `.gitignore`. Trong khi đó **ngưỡng trong `thresholds.yaml` chỉ có nghĩa khi đi kèm đúng calibrator** đã dùng để chọn ngưỡng.

## Quyết định

1. **DATA-03 chia mỗi bộ dữ liệu thành bốn phần theo người:** `train`, `calib_fit`, `calib_ltt`, `test`. Phần calib (khoảng 20%) được chia tiếp, mặc định 50/50 theo người.
2. **`calib_fit`** dùng cho: chọn checkpoint và mô hình (FACE-04, VOICE-03), hiệu chỉnh xác suất (ROUT-01), trọng số hợp nhất (ROUT-02), tập tham chiếu kNN cho cổng ngoài phạm vi (ROUT-04).
3. **`calib_ltt`** chỉ dùng để chọn ngưỡng (ROUT-03) và tính p-value cho cổng ngoài phạm vi (ROUT-04). **Không được dùng để huấn luyện hay hiệu chỉnh bất cứ thứ gì.**
4. **Cỡ mẫu tối thiểu:**
   - `calib_ltt`: ≥ 60 mẫu mỗi loại tấn công chính (đủ chứng nhận α = 5%, δ = 0,05 — proposal Phụ lục C). Thiếu thì dồn thêm người sang `calib_ltt`.
   - `calib_fit`: ≥ 100 mẫu mỗi lớp (khớp điều kiện được chọn isotonic ở ROUT-01).
5. Trong các task card, cụm "tập calib" không ghi rõ phần nào thì hiểu là **`calib_fit`**.
6. **Calibrator lưu ở `ml/configs/calibrators/<module>/<model_version>.json`** và được commit cùng `thresholds.yaml`. JSON ghi:
   - phương pháp và tham số;
   - epsilon cắt xác suất (xác suất được cắt vào [1e-4, 1 − 1e-4], tránh tỷ số khả năng vô hạn ở báo cáo giám định);
   - `n_pos`, `n_neg` (để FOR-04 tính tiền nghiệm π);
   - các chỉ số trước và sau hiệu chỉnh, ngày, commit.

## Phương án đã cân nhắc

- **Giữ chung một tập calib:** đơn giản hơn, nhưng mất tính hợp lệ của bảo đảm thống kê — đúng điểm mới chính của đề tài (proposal §2.10).
- **Kiểm chéo để dùng chung dữ liệu:** phức tạp, khó giải thích trong 3 tuần.

## Hệ quả

- Mỗi phần calib nhỏ đi một nửa. Với các bộ lớn (RTFS-10k, MLAAD-vi) không ảnh hưởng; với Zalo 2022, SUMMARY của DATA-03 phải ghi rõ số mẫu và α thực tế đạt được.
- ROUT-05: khi kiểm tra bảo đảm bằng cách chia lại ngẫu nhiên, chia lại `calib_ltt`/`test` và giữ nguyên các thành phần đã học trên `calib_fit`.
