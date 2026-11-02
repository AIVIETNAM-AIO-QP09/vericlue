# Bàn giao · APP-03 · Ngoc Quang+Codex · 2026-11-02 19:45

**Nhánh:** codex/APP-03-micro-capture-diagnostic; base main332dad3.
**Trạng thái task sau phiên này:** doing; chưa nghiệm thu khôi phục/giọng.

## Đã xong
- S24 FE kết nối lại Wi-Fi ADB; gói demo/API frozen d73dd773 đã khởi động và healthok, APK58a83e9/af2105b1... khớp bản đã cài. Không reinstall/reset hoặc tạo khóa mới khi nối lại.
- Người dùng thử recovery, báo “chưa có quyền dùng micro”. Android user0 RECORD_AUDIOgranted, AppOpsallow và app đã dùng micro hơn7giây; có MP4 cùngtrackvideo/audio. Không tự cấp thêm quyền hoặc nới chốt.
- Lưu bản ghi/log riêng ngoài Git. Probe opt-in `cached-voice-decode` chỉ đọc một basename `voice_<digits>.mp4` trong cache target, chạy đúng production decoder, giữ report/WAV riêng mỗi lần; không camera/micro/playback/upload/model/delete.
- Native RED trên file đó: `audio_pts_discontinuity` sau47PCM blocks, cleanup extractor/codec đầy đủ. Host metadata cũng thấy clock không khớp tuyệt đối nominal sample rate. Không dùng giọng/score/modeloffset để chọn ngưỡng AI.
- PcmTimeline mới: budget ứng dụng1ms so với mốc đầu VÀ đoạn liền kề, PTS tăng nghiêm ngặt, add/subtract kiểm overflow. Không cộng dồn dung sai mỗi buffer, không chèn/cắt/đổi PCM hoặc dịch firstPTS/offset. Policy `muxed-av-pcm-v2-clock1ms`, chuẩn hóa WAV giữ `pcm16-mono16k-sinc-v1`; decoder an toàn tối đa12s, luồng live cap8s.
- FlowRules định tuyến theo quyền kiểm lại hiện tại ở cả hai callback: Audio đã cấp→NoVoice, chưa cấp→ErrorMic; Camera đã cấp→ErrorDevice, chưa cấp→ErrorCamera. Permission launcher và các chốt không gửi khi lỗi giữ nguyên.

## Đang dở
- Full Android/native replay đã qua và ứng viên đã cài-r. Decode admission không phải nghiệm thu SyncNet, capture chuẩn hay recovery; chờ người dùng thử đúng lượt mới.

## Bước tiếp theo
1. Full Android/Paparazzi verify/lint/assemble main+test, cài-r cùng signer; replay cached file và3fixtures/cancel synthetic trên đúng production helper mới.
2. Ghi source/hash/policy vào gói demo, giữ APK cũ. API/model/schema/threshold/migration không đổi nên không restart/đổi server.
3. Khi kỹ thuật đã qua, bật monitor mới và mời thử đúng một lượt recovery; đối chiếu attempt sau mốc mới, không dùng phiên attestation hoặc lượt cũ. Chưa đánh dấu done đến nghiệm thu thật.

## Quyết định, lưu ý, bẫy
- Review độc lập thiết kế/code clock không thấy blocker; bổ sung adjacent guard để hai residual−900/+900us không che gap1.8ms. Source/version được ghi cả report lỗi và thành công.
- 1ms là budget app, không là bảo đảm phần cứng Android. [Android NDK về clock/sample rate](https://developer.android.com/ndk/guides/audio/audio-latency#make-no-assumptions-about-audio-performance) và [CameraX1.4.1 source](https://dl.google.com/dl/android/maven2/androidx/camera/camera-video/1.4.1/camera-video-1.4.1-sources.jar): AudioStreamImpl/AudioUtils nội suy AudioTimestamp bằng nominal rate, AudioSource đổi ns→us. Clock thực và nominal có thể khác; không suy được chất lượng AI từ đó.
- Không commit media/log/PCM/transcript/identifiers/hash của mẫu người thật hoặc khóa. Không đổi STATUS/ADR/proposal/contracts/thresholds. Data calibration/eval theo người, OTP thật và nghiệm thu vẫn còn.

## Câu hỏi cho nhóm
- Vẫn cần dữ liệu/calibrator/eval có quyền dùng, tách theo người; ngưỡng demo tạm và OTP mô phỏng giữ nguyên.

## Test đã chạy
- Routing RED4tests/2assertion failures→GREEN4/0fail/error. Root review diff, quyền từ chối vẫn đúng màn và error không qua submit.
- Clock RED15tests/5assertion failures→GREEN focused30tests/0fail/error (clock/controller/routing). Thêm clock±750us/8s ở3formats, boundary±1000, refusal±1001/2ms, cumulative budget, adjacentjump/overlap, repeated/backward PTS; giữ format/EOS/duration/overflow tests.
- Full `testDebugUnitTest verifyPaparazziDebug lintDebug assembleDebug assembleDebugAndroidTest` đạt;304tests/0failure/error/1opt-in-export skipped, lint0errors/44warnings. UI không đổi layout; verify dùng baseline hiện có, không record lại để che lỗi.
- Native replay đúng file từng lỗi: nay331blocks, decodedtrue, WAV PCM16mono16k qua guard continuity thật. First origin và metadata prefix47blocks giữ nguyên, native resources release đủ; không gửi file vào API hoặc chạy AI trong probe.
- Native3fixtures syntheticzero/positive/negative đạt, giữ offsets nhưv1;3ca cancellation bị từ chối/khôngWAVdởdang và release đủ. Clock source reportv2 và budget1000us, normalizationv1 ghi rõ.
- APK ứng viên SHA256`63b53b45b45b57b0ce0109d08168193de3f9de632f9478fc8164bfb1827026cb`; signer822e5e44.../v2verified, liveDefaulttrue/signedtrue/tracefalse; cài-r giữ appdata. API frozen d73dd773 giữ nguyên, healthok. Ruff sạch, plan_check0lỗi/10cảnhbáo, diff--check sạch. Pythonproduction/API/ML không đổi, không chạy lại full Python cho thay đổi Kotlin này.
