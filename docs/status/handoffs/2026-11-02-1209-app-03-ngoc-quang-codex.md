# Bàn giao · APP-03 · Ngoc Quang+Codex · 2026-11-02 12:09

**Nhánh:** codex/APP-03-shared-av-probe; base fbd72f3, DraftPR132.
**Trạng thái task sau phiên này:** doing; khôi phục/giọng trên người thật chưa nghiệm thu.

## Đã xong
- Lượt recovery trên API/APK d73dd773 đã qua toàn bộ mặt, nội dung Qwen sau một lần đọc lại, AntiDeepfake và continuity; chỉ lipsync không đạt. Tài khoản/khóa cũ giữ nguyên, recovery binding chưa commit. Không dùng best shifted confidence để thay điểm zero-offset hoặc chọn ngưỡng từ lượt thử.
- Kiểm tra cửa sổ SyncNet và mel không thấy lỗi cố định160/200ms; callback CameraX recordedDuration ghép với SystemClock vẫn có độ trễ encoder/executor. Chưa chứng minh đây là toàn bộ nguyên nhân SyncNet fail. Task APP-03 đã yêu cầu hình/tiếng chung clock; thay đường live ghi riêng WAV bằng một MP4 có AAC qua CameraX AudioConfig.
- Chỉ báo Recording khi có video duration dương và audio ACTIVE; native cap8giây, audio silenced/muted/error bị chặn. Chỉ chấp nhận ERROR_DURATION_LIMIT_REACHED khi chính bản ghi chung được cấu hình cap8giây. Hủy/late callback không gửi kết quả, file finalized phải đúng attempt.
- Giải mã PCM bằng MediaExtractor/MediaCodec trên IO, kiểm EOS/PTS liên tục/định dạng/kích thước và giải phóng native resource. Offset = first kept decoded PCM PTS trừ first video presentation PTS, có dấu, không lấy đồng hồ callback, không dịch theo output model. Decoder nhận trim metadata một lần; app không tự cắt priming/VAD hoặc chèn khoảng trống.
- WAV gửi API luôn PCM16 mono16k: downmix Double và centered Blackman-sinc có chống alias, không thêm filter delay. Policy nguồn `muxed-av-pcm-v1`, chuẩn hóa `pcm16-mono16k-sinc-v1`; diagnostics giữ nguyên rate/channel/framecount/PTS gốc. Không thay API/schema/ngưỡng/model/calibrator hoặc quyết định server.
- Probe tổng hợp gọi đúng production decoder, assets ngoài Git; giữ MP4/WAV/report trong thư mục riêng mỗi lần. Không camera/micro/upload/model hoặc media người thật trong probe. API regression kiểm WAV canonical và proof ký WAV+MP4+signed offset; tamper1ms bị từ chối và không tiêu proof.

## Đang dở
<!-- file:dòng, việc gì còn dang dở -->
- Phần mã và kiểm thử kỹ thuật đã qua; bản ứng viên đã cài-r cùng signer và giữ dữ liệu. Người dùng chưa tiện thử tiếp, nên nghiệm thu CameraX capture→upload→AI bằng người thật vẫn pending. Không lấy probe decoder làm kết quả nghiệm thu capture hoặc SyncNet.
- Calibration/evaluation theo người có quyền dùng và thử recovery người thật sau triển khai vẫn còn. Không dùng VIVOS32 parity để fit. Nếu lipsync tiếp tục fail phải kiểm crop/domain/calibration, không ép đạt.

## Bước tiếp theo
<!-- Viết đủ rõ để người khác hoặc AI khác làm ngay, không cần hỏi lại -->
1. Chạy full Python với PYTHONPATH trỏ đúng worktree, Ruff, plan_check; Android full tests/lint/Paparazzi record→verify/assemble.
2. Export tín hiệu tổng hợp qua chính normalizer JVM, so kiểm độc lập SciPy; build/install main+test APK khớp nhau, chạy3 fixtures PTS zero/positive/negative và cancellation. Kiểm WAV đầu ra bằng continuity guard thật.
3. Ghi commit/hash/signer/source và cài-r giữ dữ liệu. API frozen d73dd773 không cần đổi/restart cho thay đổi client này.
4. Sau các kiểm tra mới mời người dùng thử một lượt recovery; phân biệt xác nhận đường ghi/clock với xác nhận chất lượng SyncNet và nghiệm thu toàn luồng.

## Quyết định, lưu ý, bẫy
- Review độc lập code/test không thấy blocker; root vẫn phải kiểm bằng lệnh thật. CameraX native capture end-to-end chỉ được xác nhận sau lượt người thật, khác với native decoder fixture.
- Không merge main, không reset/uninstall/clear, không commit fixtures/media/APK/khóa; không sửa STATUS.md.

## Câu hỏi cho nhóm
<!-- Việc cần cả nhóm hoặc trưởng nhóm quyết. Trưởng nhóm gom vào STATUS.md -->
- Dữ liệu calibration/eval và artifact có quyền dùng vẫn chưa đủ. Ngưỡng demo tạm không phải hiệu suất đã đánh giá; OTP tiếp tục mô phỏng.

## Test đã chạy
- Agent báo TDD RED→GREEN cho controller/normalizer, root kiểm lại source/diff. API focused7/7 và Ruff đạt; plan_check0lỗi/10cảnhbáo.
- Full Python `PYTHONPATH=<worktree>/services/api/src;<worktree>/ml/src;<worktree>` rồi `python -m pytest -q`:100%, exit0, có ca skip theo điều kiện; warnings Starlette/Pydantic sẵn có. Lần gọi đầu chưa đặt PYTHONPATH trỏ nhầm editable install D:/vericlue, có31collection errors; đã sửa môi trường chạy lại toàn bộ, không sửa source để che lỗi.
- Ruff check sạch; format885files đúng; plan_check0lỗi/10cảnhbáo. `git diff --check` không lỗi whitespace.
- Android recordPaparazziDebug rồi testDebugUnitTest/verifyPaparazziDebug/lintDebug/assembleDebug/assembleDebugAndroidTest: exit0;294tests,0fail/error/skip khi bật export; lint0errors/44warnings. Baseline là source hiện tại, không tuyên bố visual parity với lịch sử. Export test mặc định không ghi file và skip nếu thiếu biến môi trường opt-in.
- Root chạy11fixtures JVM thật so kiểm độc lập SciPy Kaiser8.6: DC/identity/phase/impulse/alias/duration đạt; không tuyên bố byte parity giữa hai bộ lọc. File tổng hợp và script kiểm chi tiết giữ ngoài Git.
- Trên S24 FE, main+test APK cùng bản đã cài-r. Probe production-helper3/3đạt: offset0,+138666,-160000us, đúng native framecount và source tone onset; normalized WAV đều qua guard `wav_duration` thật (PCM16mono16k). Case positive giữ AAC priming nên không ép thành+160000us. Hủy sau một PCM buffer ở cả3fixtures: decoder từ chối, không xuất WAV dở dang, extractor/codec đều release.
- APK SHA256 `af2105b18d32781952be95a19981cf3586278ac62f6e1ce8485430b467968103`; signer giữ nguyên822e5e44..., v2verified, liveDefaulttrue/signedMediatrue/tracefalse. API vẫn frozen d73dd773, healthok và ADBreverse8421; không restart server, đổi policy hoặc migration.
- Báo cáo công khai đã lược PII: `docs/status/results/APP-03-shared-av-synthetic-2026-11-02.json`. Không media/khóa/transcript/attemptID/điểm cá nhân trong Git.

## Chốt bản ứng viên và thử tiếp sau
- Code commit `58a83e956c267ec01dacb78f6592f5f666aac782`; APK đang cài và gói demo có cùng SHA256af2105b1... (đã đọc hash base.apk trên máy để đối chiếu). Source API giữ d73dd773. Bản APK/gói metadata cũ đã backup, tài khoản/khóa không reset, media không xóa.
- Người dùng báo tạm chưa thử được, sẽ thử sau; không yêu cầu quay thêm hoặc gọi camera/micro. Probe chỉ đọc assets tổng hợp. API healthok; ADBreverse8421 có sẵn khi kết thúc, có thể phải nối lại nếu Wi-Fi/thiết bị đổi trạng thái.
- Khi người dùng sẵn sàng: kiểm API health và ADBreverse, họ tự mở app chọn Khôi phục, đợi “Đang ghi âm” rồi đọc nguyên câu. Đối chiếu đúng attempt mới nhất, proof/ASR/spoof/lipsync/continuity và binding; không kết luận từ màn hình riêng. Không nới gate nếu tiếp tục review.
- Việc còn thiếu: nghiệm thu chính capture/upload/khôi phục mới; kiểm chặn trường hợp lỗi/gián đoạn trên máy; dữ liệu/calibrator/eval có quyền dùng tách theo người; OTP thật/HTTPS/protected readiness theo task liên quan. Chưa gọi toàn demo AI thật là done. Không merge main.
