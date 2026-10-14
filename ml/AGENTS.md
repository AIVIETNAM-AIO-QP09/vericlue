# AGENTS.md — ml/ (gói vericlue_ml)

Bổ sung cho `AGENTS.md` ở gốc repo. Đọc thêm `ml/README.md`.

- **Mọi bộ phát hiện** kế thừa giao diện `Detector` và trả `ModuleResult` (`docs/architecture/architecture.md` §3, `packages/contracts/schemas/module_result.schema.json`).
- **Mọi bộ phát hiện có bản mock** cùng tên trong `src/vericlue_ml/mock/`. Phải đăng ký trong `src/vericlue_ml/registry.py` và `configs/models.yaml`.
- **Tiền xử lý đúng repo gốc** của mô hình. Ghi nguồn (repo + file + commit) trong docstring.
- **Không hard-code đường dẫn.** Dùng `MODELS_DIR` và `configs/*.yaml`.
- **Nạp mô hình một lần**, không nạp lại mỗi lần gọi. Phải chạy được trên CPU, dù chậm.
- **Test không cần GPU hay trọng số thật.** Dùng mock hoặc mô hình nhỏ giả; đánh dấu test cần mô hình thật bằng `@pytest.mark.slow`.
- **Không sửa `configs/thresholds.yaml`** trừ task ROUT-02, ROUT-03, PRES-04.
- **Đánh giá chỉ qua `src/vericlue_ml/eval/`.** Mỗi file kết quả ghi commit, phiên bản mô hình, bộ dữ liệu, số mẫu. **Không chọn mô hình hay ngưỡng bằng tập test.**
- Code trong `external/` chỉ được gọi qua lớp bọc (wrapper); không sửa trực tiếp.
