# Bàn giao · APP-03 · Ngoc Quang+Codex · 2026-11-02 22:50

**Nhánh:** codex/APP-03-micro-capture-diagnostic, Draft PR134.
**Trạng thái task sau phiên này:** doing; recovery chưa được nghiệm thu.

## Đã xong
- Người dùng xác nhận đã đọc đủ, đúng câu mới và sáu số ở cả hai lần của lượt recovery đã lưu. Ghi đây là xác nhận của người thực hiện, không phải bản chép lại độc lập từ audio. Không hỏi lại cùng câu hoặc kết luận người dùng đọc sai từ ASR.
- Rà soát độc lập đường prompt: Android hiển thị câu trả về; server chuyển đúng `session.voice_prompt`, thay câu ở lượt đọc lại. Cả hai kết quả lưu không có chuỗi chữ số dạng số; lỗi biểu diễn số liền thành số đếm không giải thích được ca này. Unicode NFC/NFD, hoa/thường và dấu câu có đối chứng tổng hợp.
- Trên đúng bản đọc lại đã lưu, VAD không bỏ bất kỳ mẫu PCM nào. Feature/mask hữu hiệu khớp đường Whisper128; tiếp tục kiểm bằng runtime gốc bên dưới để tránh chỉ so các helper trong cùng thư viện.
- Chuẩn bị runtime tham chiếu riêng ngoài repo: `qwen-asr==0.0.6`, Transformers4.57.6, tokenizers0.22.2, HF hub0.36.2; dùng cùng CPU Torch2.14.1. Không đổi môi trường server hoặc selected-models. Wheel có SHA256/Apache license; checkpoint gốc `Qwen/Qwen3-ASR-0.6B@5eb144179a02acc5e5ba31e748d22b0cf3e303b0` có kiểm HF blob/LFS và SHA256.
- Kiểm byte theo tensor, không nạp model: toàn bộ611 tensor của bản HF-native bằng checkpoint gốc sau đổi tên; LM head dư ở bản gốc bằng tied embedding. Đây là cùng trọng số, không thử/chọn mô hình khác.
- Đối chứng CPU FP32/eager/greedy offline với runtime gốc, cùng PCM/VAD/budget, không context/hotword: bản đọc lại có cùng prefix token, feature hữu hiệu, mask, token sinh và transcript; cả hai vẫn không khớp câu. Mẫu DNU calib_fit đầu manifest đã chọn từ trước đều khớp: văn bản sau chuẩn hóa giống nhau, token/văn bản thô không hoàn toàn giống. Không tuyên bố parity phổ quát, accuracy, hoặc chọn ngưỡng từ hai mẫu.
- Rà lại spatial recipe SyncNet: SCRFD square crop vẫn khác upstream căn106 điểm. Có nguồn MIT độc lập cho lõi Procrustes, nhưng template/aspect và temporal bias của phần StyleSync-derived chưa có provenance giấy phép đủ. Caller thật bật `smooth=True` trên mọi frame; căn riêng các frame được chọn không tái hiện lịch sử này. Không chép code hoặc thay recipe/ngưỡng để ép đạt.
- Sửa tài liệu còn ghi version Qwen v1/PhoWhisper quá rộng: version hiện tại v2-assistant-prefix; registry mặc định và session_voice opt-in là hai đường khác nhau. Mô tả mismatch là kết quả ASR không khớp, không khẳng định người dùng đọc sai.

## Đang dở
- Recovery vẫn `review`: nội dung nhận dạng và lipsync chưa đạt. Nhãn do người dùng xác nhận cùng đối chứng runtime cho thấy cần đánh giá chất lượng nhận dạng trên dữ liệu thu tương tự; không còn bằng chứng cho lỗi chuyển đổi HF ở riêng bản đọc lại này.
- Bản kiểm tra hai runtime không phân biệt được mọi yếu tố chất lượng thu, miền giọng hoặc giới hạn mô hình. Chưa có bản chép lại độc lập và dữ liệu đánh giá AV/giọng tách theo người đủ để chọn model/recipe/ngưỡng.
- Không có checkpoint106landmark đã pin trong manifest/bundle. SCRFD5 và MediaPipe478 không thay thế nguyên trạng topology106.

## Bước tiếp theo
1. Giữ server source95c9789, APK8049d6b, tài khoản và capture policy hiện tại. Chưa yêu cầu quay lại cùng kịch bản nếu không có thay đổi có căn cứ; không lấy xác nhận đọc đúng làm lệnh pass.
2. Đánh giá ASR trên dữ liệu thu đã gán nhãn độc lập, chia theo người và tách khỏi các bản điện thoại dùng nghiệm thu. Nếu so model, chốt protocol trên calib_fit trước; không đổi model/ngưỡng theo kết quả bản giữ lại này. VIVOS32 chỉ dành parity.
3. Với lipsync, cần nguồn/giấy phép cho đầy đủ recipe gốc và pin model106 điểm, hoặc nhóm chốt một recipe độc lập có version riêng và đánh giá/calib riêng. Không gắn nhãn upstream parity cho phép căn5 điểm hay template tự chọn.
4. Chỉ thử nghiệm thu recovery trên điện thoại sau khi có thay đổi liên quan đã smoke; onboarding và reauth đã có xác nhận trước đó không thay thế nghiệm thu recovery.

## Quyết định, lưu ý, bẫy
- Artifact riêng: `D:/vericlue/tmp/phone-demo-2026-11-02/diagnostics/voice-boundary-check-private.json`, `qwen-runtime-parity-summary.json`, `qwen-runtime-native-private.json`, `qwen-runtime-reference-private.json`. Chỉ chia sẻ bản tổng hợp sạch; các hash mẫu/transcript và số đo sinh trắc không vào Git.
- Chạy lại qua helper riêng `run_qwen_runtime_parity.py`: DB URI read-only + query_only, gắn đúng created_at của lượt đã giữ, giải mã bằng lease, đóng transaction trước hai subprocess tuần tự và nhả lease trong finally. Expected text chỉ vào bộ đếm budget/bộ so khớp, không vào model. Inference offline; không tạo phiên hoặc sửa quyết định HTTP/DB.
- Runtime/checkpoint tham chiếu: `D:/vericlue/tmp/qwen-reference-parity-2026-11-02/ready.json`; provenance và báo cáo611 tensor nằm cạnh đó. Không đưa runtime này vào bundle API.
- Lỗi harness đầu tiên: observer đọc EOS từ generation_config của thinker, trong khi wrapper gốc truyền EOS mặc định ở chữ ký generate. Đã sửa observer theo chữ ký, kiểm EOS/budget/greedy rồi chạy lại nhánh reference. Không phải lỗi server hay bằng chứng model pass; nhánh native được tái dùng với kiểm cùng hash PCM/budget.
- Agent thứ hai review harness và vòng đời lease trước khi chạy: xử lý cả Tensor/GenerateOutput, hash raw text trước repetition repair, phân biệt feature hữu hiệu với padding. Root kiểm code và kết quả cuối.

## Câu hỏi cho nhóm
- Dữ liệu thu giọng/AV có quyền sử dụng và nhãn độc lập vẫn cần chuẩn bị; thiếu dữ liệu không được biến thành pass. Chưa đề nghị đổi ngưỡng demo hoặc bỏ dấu/nonce.
- Nguồn MIT cho lõi căn mặt: [Matthew Earl, commit00cd826](https://github.com/matthewearl/faceswap/blob/00cd82651d7640159739066d855162333e104d98/faceswap.py#L119). Đây không chứng minh chuỗi bản quyền của StyleSync. [Issue giấy phép StyleSync](https://github.com/guanjz20/StyleSync/issues/15) và [caller LatentSync smooth=True](https://github.com/ByteDance/LatentSync/blob/a229c3948406bc2cf6eaf4873e662e70c6a04746/latentsync/utils/image_processor.py#L54) là các điểm cần giải quyết trước exact-recipe integration. Code InsightFace MIT, trọng số theo [điều khoản nghiên cứu phi thương mại](https://github.com/deepinsight/insightface/blob/3e6486942a1be2da0e5b475fac375ea73264bd21/python-package/README.md#license), cần pin riêng.

## Test đã chạy
- `run_voice_boundary_check.py`: exit0, không trim PCM bản đọc lại, feature/mask hữu hiệu khớp; không cần lặp inference no-VAD vì waveform không đổi.
- `check_weight_conversion.py`: exit0,611 tensor byte-equal và tied head bằng embedding; processor-only smoke runtime gốc đạt, không dùng media người.
- `run_qwen_runtime_parity.py` rồi `--reference-only` sau sửa observer: đối chứng hoàn tất, đúng kết quả từng mẫu đã ghi ở trên. Không fit, không chọn model/ngưỡng, không suy hiệu suất từ control.
- `verify_preprocess_deployment.py`: source/owned-process/bundle đúng, healthok/failed_modules[], SQLite quick_checkok; payload/key/device binding tài khoản không đổi, recovery cũ vẫn review và chưa có recovery binding.
- `verify_voice_followup_report.py`: bản tổng hợp sạch khớp các artifact riêng; JSON hợp lệ, không đưa hash mẫu/transcript vào Git. `git diff --check` sạch; plan_check0lỗi/10cảnh báo cũ. Lần đầu thêm cập nhật đẩy bảng metadata task quá xa đầu mục; đã đưa bảng lên ngay dưới tiêu đề APP-03, không sửa parser hoặc tiêu chí.
