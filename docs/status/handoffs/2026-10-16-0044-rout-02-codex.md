# Kế hoạch · ROUT-02 · Codex · 16/10/2026

**Nhánh:** feat/ROUT-02-decision-policy, từ origin/main5d98775.
**Trạng thái:** lưu kế hoạch lịch sử đã duyệt; kết quả triển khai ở bàn giao `2026-10-16-1258-rout-02-codex.md`.

## Đã đọc / kiểm tra
- Đúng worktree D:/Projects/vericlue-codex; git fetch/tạo nhánh và uv sync --all-packages thành công. ROUT-01/PLAT-08 done, ROUT-02 todo, không bị chặn.
- AGENTS gốc/ml/API, STATUS, E6 ROUT-02, ADR-0010/0011, architecture§6, README API/ML, code provisional_decision/session_flow/orchestrator/stores, calibration, voice challenge, ModuleResult và mock.
- Bàn giao PLAT-08 mới nhất0033, VOICE-04 1028 gồm bổ sungPR14. CAP-02 chưa trên main: đọc git show origin/feat/CAP-02-camera-quality:docs/status/handoffs/2026-10-16-0012-cap-02-m1-claude.md từ PR15 đang mở, không merge. Cổng web độc lập cổng server, không thay quality server; quá sáng hiện xử lý cục bộ, không tự thêm retry_hint mới.
- Ba subagent chỉ đọc song song yêu cầu/ADR, API, ML/mock; không sửa code/test/commit.

## Kế hoạch đề xuất
1. Tạo router/config.py đọc/validate thresholds.yaml và giữ snapshot bất biến cùng SHA-256 nội dung file. YAML có provisional:true, B0,15/A0,60 từ PLAT-04, nguồn từng giá trị; voice WER0,3/similarity0,9 từ VOICE-04. Xóa bản số trùng API Settings/env/Compose và matcher; evaluator VOICE-04 cũng dùng loader này. Nạp config một lần, đường dẫn override qua env cho Docker/wheel. Không để default literal âm thầm khi thiếu/hỏng YAML.
2. Thêm fusion.py: hiện dùng max(prob_attack) ghi rõ provisional, không tạo trọng số logistic giả. API fit tương lai chỉ nhận calib_fit, subject_ids, feature order/module versions và dữ liệu đủ hai lớp; artifact ghi tham số thật, provenance/split. Test tổng hợp không tạo artifact production. Không fit/chọn trên calib_ltt/test. Hợp nhất hiện trên thang xác suất[0,1], không đổi sang likelihood ratio với ngưỡng0,15/0,60.
3. Thêm policy.py/TrustRouter thuần: nhận ModuleResult và context/counter, không ORM, không sửa session. Xét thiếu/non-ok module bắt buộc thành review, rồi validity/quality/presence/OOD nếu đã có/fusion face/voice. Không lấy score WER vào fusion. Kết quả chỉ action/retry_hint/priority/reason và metadata nội bộ; không đưa Lambda/ngưỡng/lý do ra response công dân.
4. CalibrationStore ROUT-01 dùng theo module/version trước fusion; mock được miễn. Lỗi thiếu/hỏng calibrator chuyển error/review, không dùng score thô. Bắt buộc face_pad/face_deepfake; voice bước tương ứng bắt buộc voice_challenge/voice_spoof/lipsync. SBI chưa có module riêng, OOD/feature chất lượng/cắt ghép chưa có nguồn thật không tự bịa thành phần bắt buộc mới.
5. API SessionFlow sở hữu counters: tăng retries_used khi retry, cấp challenge mới; reset/tăng voice_rereads_used và cấp câu đọc lại. Policy chỉ kiểm giới hạn được truyền (hai chụp lại/một đọc lại), không tăng ở nơi khác. Session_closed/voice_not_requested, queue/deadline/preload/lock_timeout/row locks/transaction giữ nguyên. Auth HTTP401/409 không bị đổi thành mở ca; policy validity là context nội bộ, không làm HMAC/máy trạng thái PLAT-06.
6. SessionStore ghi decisions với snapshot ngưỡng/phương pháp fusion thực dùng +config_version sha256:<64hex>; dùng JSON hiện có, không cần migration. Cùng config snapshot dùng xuyên vòng request và VOICE-04; review AI đọc cùng policy/config, giám định giữ verdict riêng nhưng đọc cùng nguồn B/A, không giữ literal rời.
7. Subagent viết >=12 test riêng: mọi nhánh, required missing/error/degraded/timeout/busy/not_applicable, biên B/A, hai retry/một reread, calibration lỗi, hash/snapshot, không lộ response; 7 mock scenario. Main implementation; reviewer chỉ đọc theo task/AGENTS6/8; chỉ main commit. Fullpytest/ruff/plan_check/uvlock và Docker smoke rồi down; backlog đúng dòng/thẻ/handoff/PR.

## Phân chia logic
- ML router: validate kết quả/context, chọn nhánh/fusion/ngưỡng, trả quyết định thuần và provenance.
- API: xác thực/giao thức, giữ hàng khóa/queue/deadline, sở hữu counters/challenge/prompt/case, persist và serialize schema an toàn.
- Không đổi hợp đồng dự kiến. Nếu cần reason/priority public mới, dừng đề xuất schema trước; hiện priority/reason nội bộ đã đủ.

## File dự kiến
- Mới: ml/src/vericlue_ml/router/{__init__,config,policy,fusion}.py và ml/configs/thresholds.yaml.
- Sửa matcher voice/challenge.py và eval/voice_challenge.py để đọc ngưỡng cùng nguồn; ml/README.md, test router/config/fusion riêng.
- API: adapter provisional_decision.py, session_flow.py, session_store.py, state/config, review_store/routers/review và forensic_service nếu cần loại B/A trùng; injection cùng snapshot vào VoiceChallenge preload khi cần. Orchestrator execution/queue không đổi.
- .env.example, docker-compose.yml/API Dockerfile khi cần THRESHOLDS_CONFIG; README API, thẻ/backlog/handoff. Không sửa web, common/result.py, Detector protocol, ADR hay STATUS; mock chỉ đổi nếu trưởng nhóm duyệt rõ.

## Bảng mock mong đợi đề xuất (không phải kết quả thực nghiệm)
| Kịch bản | Finalize | Sau voice / ghi chú |
|---|---|---|
| genuine | pass | Không gọi voice |
| print | review, ưu tiên cao | Chroma fail |
| replay | review, ưu tiên cao | Chroma fail |
| virtual_cam | review, ưu tiên cao | Chroma/Cam fail |
| faceswap | review, ưu tiên cao | Chroma fail |
| voice_clone | voice_challenge | review do voice_spoof/lipsync cao |
| low_quality | review nếu giữ yêu cầu mọi degraded bắt buộc phải review | Mock hiện có hai module mặt degraded; khác luồng retry cũ, cần chốt dưới đây |

Bổ sung scenario error ->review. Nhánh retry2lần/reread1lần vẫn test bằng fixture riêng với toàn bộ module bắt buộc statusok.

## Câu hỏi cho nhóm
1. low_quality hiện qualityfail và hai module mặt degraded. Luật tạm retry2lần→review, còn chỉ thị mới yêu cầu mọi degraded bắt buộc→review. Đề xuất ưu tiên fail-closed và giữ mock hiện có, nên low_quality→review ngay. Nếu muốn giữ bảng retry cũ, cần duyệt rõ thay fixture mock (statusok ở module mặt) hoặc chỉ xét module bắt buộc khi tới cổng đó; không tự tạo ngoại lệ.
2. Ngưỡng voice attack chưa có riêng trong thẻ. Đề xuất voice dùng tham chiếu face.B hiện tại0,15 như API cũ, không chép thêm một literal; chuyển ngưỡng WER/similarity đúng giá trị đã chốt. Biên theo task: face<=B pass, >=A review; voice<=ngưỡng pass — khác strict< của luật tạm, cần xác nhận cùng kế hoạch. Fusion hiện dùng max cả mock và real đã hiệu chỉnh, luôn provisional; không fit artifact thật.
3. Cờ cắt ghép thật chưa có (mock hiện có evidence splice_flags, VOICE-04 thật chỉ WER/similarity/transcript). Đề xuất cờ rõ positive thì review, vắng thì giữ absent và không đưa feature đó vào fusion tạm; chưa bắt buộc tới VOICE-05. Quality features/logistic/OOD chỉ khai báo/hỗ trợ để tích hợp sau, không điền0 giả. Nhờ duyệt phạm vi này.

## Kiểm tra đã chạy
- Git/uv setup thành công; chỉ đọc bối cảnh và ghi kế hoạch. Chưa chạy test mới hoặc sửa code trước duyệt.


## Trưởng nhóm đã duyệt — 16/10, trước triển khai
- low_quality giữ thứ tự cổng: quality fail -> retry, retry, review; chưa xét face degraded khi quality fail. Quality error/degraded -> review. Khi quality đã pass và tới bước mặt thì face error/degraded -> review. Có test riêng hai tình huống này, không sửa mock để che khác biệt.
- Voice dùng **voice.spoof_threshold riêng0,15**, provisional:true, nguồn "tạm — chờ ROUT-03"; không alias face.B. Face <=B pass, >=A review; voice <=ngưỡng pass. Ghi đổi dấu bằng trong bàn giao và test đúng biên.
- Cờ cắt ghép dương -> review; vắng -> absent, không điền0 và không đưa feature vào fusion tạm, chờ VOICE-05. Sáu scenario còn lại theo bảng đã duyệt. Ba câu hỏi ở trên đã được thay thế bằng các chốt này.
- Làm hotfix trước trên fix/PLAT-08-slot-release: PR18, commit02f7a74. Nguyên nhân publish result trước nhả slot; đã sửa nhỏ +4regression, test gốc200/200 lần, fullpytest1424pass25skip. Chờ gộp vào main rồi merge origin/main vào nhánh ROUT-02 trước code; không cherry-pick lẫn hotfix vào PR policy.
- Claude sắp REV-01: tránh review_store.py và routers/review.py. Cần giữ consumer B/A cũ bằng adapter/property đọc YAML không có literal trùng; nếu bắt buộc sửa hai file đó phải báo trưởng nhóm trước. Lưu metadata quyết định tự động qua SessionStore; phối hợp metadata quyết định nhân viên với REV-01, không tự sửa code của phiên kia.
- ROUT-02 đã được duyệt, không cần xin duyệt lại kế hoạch sau khi hotfix vào main. Chưa sửa code ROUT-02 trong lượt hotfix.
