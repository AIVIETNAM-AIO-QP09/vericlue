# Bàn giao · VOICE-09 · Ngoc-Quang+Codex · 2026-11-01 10:30

**Nhánh:** `codex/APP-01-demo-integration`, sau commit tích hợp `a542a47`.
**Trạng thái task sau phiên này:** tiếp tục kiểm chứng; detector vẫn chỉ chẩn đoán, chưa bật quyết định chống giả giọng.

## Đã xong
- Tiếp quản các sửa parity của Anti chưa commit: kiểm tra PCM trùng, 32 mẫu riêng biệt mới đủ điều kiện xét PASS; giữ số liệu/hash từng input.
- Tải XLS-R chính thức (3808868242 bytes, SHA256 `b08927597f2c9eb2ebd7dcc3ac78ee4b5f6021cbac4b3a6c5a9deec445d80ed9`) vào kho models local. Tải VIVOS publisher revision `3cbfb2502e5e84776b4b778b020a09759f723f52` bằng downloader repo, không cần token. Chọn32 WAV/9 speaker/cửa sổ SHA riêng cho **parity số học**, không dùng làm calib_fit hoặc chọn ngưỡng.
- Sửa đường WAV thật gọi hàm không tồn tại `_read_pcm` → dùng bộ đọc native của detector; test WAV PCM RED→GREEN giữ nguyên từng mẫu.
- Dựng thêm interpreter HF Python3.12 trong WSL; `vericlue_ml` dùng StrEnum nên không chạy bằng Python3.10 của Fairseq. Hai môi trường/CLI chính xác trong `ml/scripts/README-parity-nes2net.md`.
- Khắc phục lỗi thực thi Fairseq thật: task cfg của XLS-R cũ có `multiple_train_files`/`eval_wer` không được dataclass Fairseq0.12.2 nhận. Truyền task inference-only khi dựng model, giữ nguyên cấu hình graph và toàn bộ trainedstate. Contract subprocess test tái hiện RED→GREEN. Không sửa nguồn upstream hay trọng số.
- Torch2.2 yêu cầu tên file kiểu str khi mmap; đổi `torch.load(str(path), weights_only=True,mmap=True)`. Không đổi tính toán, ngưỡng hay nhãn detector.
- Báo cáo parity mới lưu thêm phiên bản Torch/Transformers/NumPy, hash script và logits tham chiếu theo cửa sổ để truy vết sai lệch.

## Đang dở
<!-- file:dòng, việc gì còn dang dở -->
- Lượt thực tế HF torch2.8 / Fairseq torch2.2.2 trên32 WAV cho **FAIL**: max_abs_logit_diff `9.441375732421875e-05`, max_abs_margin_diff `0.00017642974853515625`, cùng dấu32/32. Margin vượt1e-4; không tăng tolerance hoặc tự gắn frontend_parity_verified.
- Hai bên cùng Torch2.2.2 nhưng reference1/converted4 threads vẫn **FAIL**,
  max margin diff `0.00017595291137695312`, cùng dấu32/32. Như vậy riêng đổi
  Torch không giải thích sai lệch. Sau khi đồng bộ **cùng4 threads**, lượt cuối
  trên source commit `52cebaf8890479d89638b0423a802af85c8cc0c6` đã **PASS**:
  max logit diff `1.3470649719238281e-05`, max margin diff `2.47955322265625e-05`,
  cùng dấu32/32. Không thay tolerance hoặc đổi acceptance. Kết luận giới hạn ở
  32 WAV/9 speaker và các runtime ghi trong báo cáo; không phải accuracy.
- Git WSL không đọc được `.git` trỏ `D:/...` của worktree Windows, báo cáo lượt
  trước ghi `commit:unknown`. Công cụ thêm `--source-commit` để truyền SHA thật
  đã kiểm trên Windows, cộng hash script/runtime để lần cuối có provenance đủ.
- Báo cáo cuối `D:/vericlue/tmp/finish-2026-11-01/nes2net-parity-matched-runtime.json`
  có scriptSHA `a449c9a3e523328c2a4fb671a5059937bfe52bbc512ab034d9e32fe3aaff6e32`,
  Torch2.2.2 cả hai bên, Transformers4.57.6, NumPy1.26.4, Fairseq0.12.2.
  Các báo cáo FAIL vẫn giữ nguyên.
- Kiểm riêng runtime Windows **cũng PASS** trên cùng32 PCM (kiểm hash toàn mảng
  và từng cửa sổ/thứ tự trước suy luận), so với logits Fairseq4threads đã lưu:
  max logit diff `4.839897155761719e-05`, max margin diff `7.271766662597656e-05`,
  cùng dấu32/32. Runtime Windows Python3.12.15/Torch2.14.1CPU/HF4.57.6/NumPy2.5.4,
  4threads; báo cáo `nes2net-parity-windows.json`, commit source52cebaf.
- Chưa tích hợp bằng chứng parity thành artifact được detector kiểm tra, chưa có
  bộ gộp điểm/hiệu chỉnh trên dữ liệu thật/giả đúng protocol và split theo người.
  Không đưa VIVOS test-only vào fit/chọn ngưỡng. Detector vẫn diagnostic/degraded;
  không coi parity PASS là chứng minh chống giả giọng hoặc quyền cấp tài khoản.

## Bước tiếp theo
<!-- Viết đủ rõ để người khác hoặc AI khác làm ngay, không cần hỏi lại -->
1. Dùng báo cáo32 WAV và runtime/hash để phân tích sai lệch frontend nếu còn FAIL; đối chiếu từng tầng thay vì nới tolerance.
2. Sau parity hợp lệ, xây và kiểm chứng quy tắc gộp điểm trên calib_fit đúng nguồn; fit calibrator, chọn ngưỡng theo quy trình hiện có, đánh giá test độc lập.
3. Xem `docs/runbooks/real-ekyc-next-steps.md` cho những dữ liệu/chốt/kiểm tra thiết bị còn thiếu. Không bật guard hay đổi degraded thành ok từ smoke/parity riêng lẻ.

## Quyết định, lưu ý, bẫy
- Log và báo cáo local: `D:/vericlue/tmp/finish-2026-11-01/`. Danh sách WAV và provenance giữ ở `D:/vericlue/data/diagnostics/nes2net-parity-vivos/` (không commit dữ liệu).
- Bản tóm tắt số đo không chứa audio/định danh từng người được ghi tại
  `docs/status/results/VOICE-09-parity-2026-11-01.json`, kèm commit/model/runtime,
  số mẫu/người, hash báo cáo local và giới hạn kết luận.
- Lượt parity đầu thực thi trên working tree nền c7613cc (trước commit tích hợp), dùng đúng sửa worker/reader được ghi trong thay đổi này. Báo cáo lượt tiếp theo có `script_sha256` để nối đúng source; kết quả không phải accuracy hay APCER/BPCER.
- Không sửa `thresholds.yaml`, không tạo artifact xác suất/ngưỡng giả, không thay .env hoặc server, không push/PR/tắt máy.

## Câu hỏi cho nhóm
<!-- Việc cần cả nhóm hoặc trưởng nhóm quyết. Trưởng nhóm gom vào STATUS.md -->
- Nhóm cần dữ liệu và quyền dùng cho các protocol chống giả giọng/lipsync/video phiên; thiếu chúng không thể kết luận đạt thật hoặc hiệu chỉnh chính thức bằng vài lượt dùng thử.

## Test đã chạy
<!-- lệnh + kết quả thật -->
```
ml/tests/test_nes2net.py:42 passed (audio runtime).
ml/tests/test_nes2net.py + test_nes2net_real_smoke.py:43 passed,1 skipped in27.92s;
  gồm checkpoint thật CPU/repeatability, ca head gốc thiếu source nên skip.
Sau khi cung cấp nguồn upstream đúng SHA: test_head_graph_matches_pinned_original_on_synthetic_features:1 passed.
Full Python toàn repo trước thay đổi Path->str cuối:4661 passed,81 skipped,0 failed (425.50s).
Ruff check/format sạch. Test không thay thế đối chiếu Fairseq trên audio thật hay đánh giá dữ liệu độc lập.
```
