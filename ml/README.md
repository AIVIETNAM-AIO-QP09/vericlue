# ml — Bộ não phát hiện giả mạo (gói `vericlue_ml`)

**Phụ trách:** M3 (face/, presence/), M4 (voice/, forensic/provenance), M5 (router/, eval/)
**Trạng thái:** chưa khởi tạo — làm ở task **PLAT-03**.

## Cấu trúc

| Thư mục | Nội dung | Epic |
|---|---|---|
| `src/vericlue_ml/common/` | `ModuleResult`, hiệu chỉnh xác suất, đọc video/âm thanh | E0 |
| `src/vericlue_ml/mock/` | Mô-đun giả lập cho mọi bộ phát hiện | E0 |
| `src/vericlue_ml/face/` | PAD (MiniFASNet), GenD, SBI, gộp điểm theo khung | E4 |
| `src/vericlue_ml/presence/` | Phân tích ChromaPulse (độ trễ, mức khớp), chấm điểm CamProbe | E3 |
| `src/vericlue_ml/voice/` | AntiDeepfake, PhoWhisper, căn chỉnh câu, kiểm tra câu đọc, SyncNet | E5 |
| `src/vericlue_ml/router/` | Hợp nhất, cổng ngoài phạm vi, Learn-then-Test (MAPIE), chính sách | E6 |
| `src/vericlue_ml/forensic/` | Chia đoạn, quét nguồn gốc (thủy vân, C2PA), báo cáo | E7 |
| `src/vericlue_ml/eval/` | Script sinh kết quả R1–R6 | E8 |
| `configs/models.yaml` | Mô hình nào, phiên bản nào, đường dẫn trọng số | |
| `configs/thresholds.yaml` | **Ngưỡng đã khóa** — chỉ sửa qua PR có kết quả đánh giá kèm theo | |
| `tests/` | Test (pytest) | |

## Quy ước bắt buộc

1. Mọi bộ phát hiện kế thừa giao diện `Detector` và trả `ModuleResult` (`docs/architecture/architecture.md` §3).
2. Mọi bộ phát hiện **phải có bản mock** cùng tên trong `mock/`.
3. Không hard-code đường dẫn: dùng `MODELS_DIR`, `configs/models.yaml`.
4. Tiền xử lý **đúng như repo gốc** của từng mô hình (ví dụ GenD: SCRFD, căn chỉnh 5 điểm, tỷ lệ 1,3, 224 px). Ghi rõ nguồn trong docstring.
5. Notebook chỉ để thử; code dùng thật phải chuyển vào `src/` và có test.
6. Kết quả đánh giá ghi kèm: commit, phiên bản mô hình, bộ dữ liệu, số mẫu.
