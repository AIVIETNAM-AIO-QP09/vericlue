# Bàn giao · APP-03 · Ngoc Quang+Codex · 2026-11-02 21:49

**Nhánh:** codex/APP-03-micro-capture-diagnostic, Draft PR134.
**Trạng thái task sau phiên này:** doing; chưa nghiệm thu recovery.

## Đã xong
- Hai agent rà soát độc lập Qwen và SyncNet rồi review chéo. Có hai lỗi parity xác định từ source gốc, tách khỏi giả thuyết vì sao bản ghi của người dùng bị chặn.
- Qwen/Transformers 5.13.0 helper đặt Vietnamese ở system, khác assistant prefill gốc; dùng public chat continuation API với prefix cố định và version `cpu-fp32-content-v2-assistant-prefix`. Không truyền câu dự kiến vào model. Kiểm generated control IDs trước raw decode; giữ kiểm EOS/budget/rỗng/markup và repetitions.
- SyncNet khôi phục uint8 sau bicubic antialias rồi mới /255 và normalize(.5,.5), version `voice05-v3-u8resize`. Test ảnh tổng hợp bắt khác biệt rounding, frame/RGB packing và lower-half. Không đổi crop geometry, clock, trọng số hoặc threshold.
- Artifact lipsync v2 không được đổi nhãn cho v3. Test xác nhận artifact cũ không hiệu chỉnh version mới; đường manual demo dùng đúng version registry riêng, không lấy identity cũ làm bằng chứng hiệu chỉnh.
- Đối chứng riêng trên cùng waveform/model/VAD/greedy: Qwen cũ và mới đều không khớp bản đọc lại đã lưu; control DNU chọn sẵn từ hàng calib_fit đầu manifest khớp ở cả hai. Không fit/chọn model/ngưỡng hoặc dùng VIVOS parity. Chưa có nhãn nghe độc lập nên không kết luận người dùng đọc sai.
- Đối chứng SyncNet cùng CTC alignment/clock/weights: cả trước và sau sửa đều `ok/fail` dưới ngưỡng demo hiện tại. Không đổi kết quả phiên thật hoặc liên kết tài khoản. Chi tiết/scores/media/transcript/IDs ở ngoài Git.

## Đang dở
- Hai chốt người thật vẫn chưa đạt. Sửa wrapper có bằng chứng không đồng nghĩa đã tìm đầy đủ nguyên nhân thất bại trên điện thoại.
- Spatial input vẫn SCRFD square box, khác upstream 106-landmark alignment. Không copy `affine_transform.py` có nguồn StyleSync chưa rõ giấy phép; chưa có recipe tương đương đã kiểm chứng/cleared.
- Cần hoàn tất đồng bộ bundle server, kiểm readiness trên đúng source và CI commit mới; cập nhật phần triển khai sau khi xác nhận. Không cần APK mới cho thay đổi server này.

## Bước tiếp theo
1. Freeze code đã review vào source mới, sao lưu SQLite bằng online backup/quick_check, giữ nguyên .env/APK/models/keys/media; chỉ restart đúng server bundle.
2. Kiểm health/readiness/version mới, CI, và lưu provenance. Không gọi launcher connect/am start hoặc bắt người dùng quay lại khi chưa có giả thuyết mới.
3. Phân biệt giới hạn ASR với chất lượng capture bằng dữ liệu có transcript chuẩn; xử lý recipe căn mặt có giấy phép và kiểm parity trước khi tuyên bố lipsync hoàn tất. Dữ liệu hiệu chỉnh/eval theo người vẫn là việc riêng chưa đủ.

## Quyết định, lưu ý, bẫy
- Qwen nguồn chuẩn: QwenLM/Qwen3-ASR `c17a131fe028b2e428b6e80a33d30bb4fa57b8df`, inference/qwen3_asr.py445–465; upstream Transformers fix `c7f9c8815610d27e41a6b0b0cc9e2d3c49468d1d`, PR47111.
- SyncNet nguồn chuẩn: LatentSync `a229c3948406bc2cf6eaf4873e662e70c6a04746`, image_processor.py process_images; TorchVision0.20.1 _functional_tensor.py Resize byte semantics. Chỉ gọi API và tự viết regression, không copy source upstream.
- Native diagnostic đầu tiên trộn registry frozen v2 với candidate v3 nên candidate bị `degraded/unclear` đúng chốt version; đã sửa phép đối chứng để mỗi result được kiểm bằng đúng implementation registry của nó, không sửa server/chốt. Kết quả đúng cuối cùng vẫn `ok/fail` cho cả hai.

## Câu hỏi cho nhóm
- Chưa đề nghị bỏ dấu/nonce, thay câu, chọn threshold/model từ bản ghi người dùng hoặc dùng best-shifted confidence để dịch media. Recovery giữ chưa nghiệm thu; PR giữ Draft.

## Test đã chạy
- Qwen RED trước fix: 6fail/36pass, sau fix42pass; thêm control-ID guards RED4fail→GREEN47pass. Các ca adjacent ASR/matching trước guard117pass.
- SyncNet resize RED hai hướng resize, identity256 đã pass; sau sửa cả3 ca byte-exact. Scoped suite cuối gồm Qwen/resize/batching/timestamps/calibrator đã exit0 trong av-lab runtime.
- Opt-in `test_qwen_processor_local.py`: actual pinned processor/template/tokenizer + synthetic PCM/stub generation, không weights/inference; kiểm empty system/assistant suffix/feature/token dtype/control token. Đạt trên runtime thật; mặc định skip.
- Full Python qua D:/vericlue/.venv với PYTHONPATH trỏ đúng workspace: exit0, 5033 dấu pass/102skip ở snapshot thu thập trước các test control cuối. Suite focused cuối kiểm guards mới; CI trên commit cuối sẽ là xác nhận đầy đủ đúng revision. Lần đầu thiếu PYTHONPATH đã import nhầm checkout D:/vericlue và lỗi collection; không sửa code để né lỗi môi trường.
- Kiểm tra cuối đúng source: av-lab runtime121pass gồm actual processor test; runtime API66pass cho dynamic flows/voice runtime/audio offset. Không cài thêm thư viện: lần gộp API vào av-lab thiếu alembic/jsonschema ở bước collection, đã tách suite theo đúng runtime.
- Ruff toàn repo sạch, format891files sạch; plan_check0lỗi/10cảnh báo cũ. Native Qwen/SyncNet đối chứng trọng số thật hoàn tất riêng; không phải phép đo accuracy.
