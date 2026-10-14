# data — Dữ liệu (KHÔNG commit)

Thư mục này nằm trong `.gitignore`, trừ file README này. Dữ liệu được tải bằng script. Không ai copy tay rồi gửi cho nhau qua Zalo hay Drive.

```
data/
├── raw/          bộ dữ liệu gốc tải về (zalo2022/, rtfs10k/, mlaad_vi/, vimd/, ...)
├── interim/      đã cắt mặt, chuẩn hóa âm thanh, đã nén lại
├── synth/        dữ liệu tự tạo từ nguồn công khai (deepfake người Việt, giọng giả)
├── splits/       danh sách train / calibration / test (file .csv nhỏ, ĐƯỢC phép commit qua ml/configs nếu cần)
└── selftest/     video chạy thử ChromaPulse của thành viên nhóm (xóa sau dự án)
```

- **Danh sách bộ dữ liệu, giấy phép, cách tải:** `docs/data/data-plan.md`.
- **Lệnh tải:** `uv run python scripts/download_data.py --help` (task DATA-01).

## Quy tắc

1. Chỉ dùng nguồn công khai cho nghiên cứu. Bộ chưa rõ giấy phép ghi rõ “giấy phép chưa rõ — không phân phối lại”. **Không** thu dữ liệu sinh trắc học của người ngoài nhóm.
2. Dữ liệu tự tạo chỉ dùng nội bộ, không phát tán.
3. Chia tập **theo người**: một người không được xuất hiện ở cả tập train lẫn tập test.
4. Tập test **không được dùng** để chọn ngưỡng hay chọn mô hình.


## Kho dùng chung giữa worktree

Script đọc `DATA_DIR` (biến môi trường ưu tiên `.env`), mặc định `./data` tính từ
gốc repo. Ví dụ kho dùng chung ngoài worktree: `E:\shared\vericlue\data`.
Tất cả dữ liệu, cache và SOURCE.md nằm trong kho đó; không đưa vào Git hay upload.
Xem `scripts/README.md` để cài nhóm tùy chọn data và đặt credentials.

`raw/<tên>/SOURCE.md` ghi giấy phép và trạng thái thực; `selected_manifest.json`
(nếu adapter tạo) giữ đường dẫn, người/video/câu nguồn để DATA-03 chia đúng nhóm.
Thư mục `.cache/` và archive chưa giải nén không phải danh sách mẫu đã chọn;
không quét cache làm tập huấn luyện. Báo cáo lượt tải nằm ở `runs/*.json`.
NC chỉ dùng nghiên cứu, không phân phối lại; ViMD ND không phân phối bản phái
sinh, ví dụ biến thể nén DATA-05. SOURCE ghi thiếu identity khi nguồn không có,
không tự coi UUID/file number là người. ViSpoofDB giữ riêng làm test.


ViCocktail/WildDeepfake có `index.csv` cạnh SOURCE: video gốc, speaker ID nếu có,
archive/member cho mỗi clip/frame. Chọn shard/archive theo ngoại lệ trưởng nhóm
15/10; DATA-03 phải nối video và người xuyên shard. Wild báo video xuất hiện
trong nhiều archive đã tải. FAS-VN lưu nguyên ZIP (small = full).
Giọng thật ViSpoofDB lấy từ VIVOS; DATA-03 phải chia theo người xuyên hai bộ.
