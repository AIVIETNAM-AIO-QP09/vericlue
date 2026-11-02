# Bàn giao · APP-03 · Ngoc Quang+Codex · 2026-11-02 20:29

**Nhánh:** codex/APP-03-micro-capture-diagnostic, PR134, base main332dad3.
**Trạng thái task sau phiên này:** doing, chờ thử người thật trên nguồn v3.

## Đã xong
- V2 giải mã được file đầu và gửi một lượt giọng đến API. Face7gates qua, voice spoof/continuity qua, Qwen yêu cầu đọc lại và lipsync chưa đạt. Các lượt đọc lại báo NoVoice trước gửi API; native replay tái hiện `audio_pts_discontinuity` sau175blocks. Người dùng không cần đọc to/rõ hơn để sửa lỗi parser này.
- Metadata có một bước PTS cục bộ khoảng1,417ms; log báo audio STARTED/ACTIVE/unsilenced đến controlled cap8s, không có bằng chứng đủ phân biệt clock correction với mất mẫu. Không tăng tiếp dung sai1ms hoặc lấy score/peakSyncNet để dịch media.
- Nguồn `muxed-av-pcm-v3-ptsgrid`, normalizer `pcm16-mono16k-pts-sinc-v2`: lưu anchor(frameindex,PTS), nội suy nghịch lên lưới16k, centered sinc1024phases theo fractional source position, antialias từ max local rate. Giữ firstPTS/offset có dấu; đuôi cuối không có timestamp riêng được ngoại suy nominal và ghi rõ.
- Rate DSP open(0.5,2) dùng bound floor/ceil nguyên bảo thủ, nominal/actual duration gồm tail≤12s, output≤192000frames. Đây là range phép biến đổi, không là bảo đảm thiết bị; không chứng minh continuity vật lý hoặc chất lượng AI. PTS trùng/lùi, rate/duration/EOS/format sai vẫn không tạo WAV.
- Màn NoVoice đổi thành “Chưa xử lý được bản ghi”, không quy lỗi cho độ rõ giọng. Chỉ hai snapshot61_no_voice sáng/tối đổi, đã xem ảnh và verify. DEBUGlog chỉ code cố định khi decode lỗi, không path/content/IDs.
- Candidate đã cài-r cùng signer trên S24 FE;5file đọc lại giữ từ trước đều decoded, canonical WAV qua guard thật, origin/signedoffset giữ.3fixtures synthetic WAV/PCM/offset byte-identical bản cũ khi clock nominal;3cancellation bị từ chối và resources release đủ.

## Đang dở
- Cần một lượt recovery mới từ màn đầu trên v3 khi người dùng tiện; không dùng session cũ đã lâu hoặc suy pass từ local replay. Qwen/lipsync/rawdemo/calibration toàn luồng chưa done.

## Bước tiếp theo
1. Chốt source/hash/policy gói demo và mốc monitor mới; API frozen d73dd773/model/policy/ngưỡng không đổi.
2. Theo dõi CI134 và nghiệm thu một lượt mới; account/binding chỉ coi thành công khi API commit đúng khóa/tài khoản và người dùng xác nhận.
3. Nếu còn lỗi, dùng DEBUGtagVeriClueVoiceCapture hoặc cached replay; không yêu cầu người dùng lặp vô hạn, không nới AIgate. Dữ liệu hiệu chỉnh/eval theo người vẫn còn thiếu, không dùng VIVOSparity đểfit.

## Quyết định, lưu ý, bẫy
- Reviewer độc lập thông qua semantics nội suy presentation-time có giả định tail. Không tuyên bố phân biệt được mẫu mất hay clock correction; các gap trong range có thể được biểu diễn bằng kéo giãn cục bộ. Range/mapping/version là policy dữ liệu, không là kết quả xác minh.
- RelativePTS được trừ checked trước khi chuyểnDouble; bound ngăn trường hợp một AACframe bị mất ở biên42666/42667us và compressed10666/10667us. PCM native vẫn nguyên trong collector; waveform đầu ra được resample theo clock map, không được mô tả là timing nguyên vẹn.
- Sources: [Android NDK clock/rate](https://developer.android.com/ndk/guides/audio/audio-latency#make-no-assumptions-about-audio-performance), [CameraX1.4.1](https://dl.google.com/dl/android/maven2/androidx/camera/camera-video/1.4.1/camera-video-1.4.1-sources.jar). Không copy code upstream.
- Media/log/PCM/transcript/samplehash/identifiers thật ngoài Git. Không sửa contracts/thresholds/ADR/proposal/STATUS hoặc khóa/tài khoản. Không chứng nhận security/accuracy từ tests.

## Câu hỏi cho nhóm
- Calibration/evaluation phải đo riêng cho recipe input mới khi chuẩn bị dữ liệu có quyền dùng; OTP còn mô phỏng, ngưỡng demo tạm.

## Test đã chạy
- Clock/normalizer focused24cases: RED14assertion failures→GREEN24; gồm uniform parity, drift±/step/tone/impulse, packet splitting, boundary/tail/rounding/overflow/cancel/alias/downmix.
- Fullrecord đầu thấy2fixtureoffset cũ chỉ có1mẫu48k, không đủ1mẫu16k: đổi fixture thành3mẫu để giữ nguyên assertions signedoffset/overflow. Không đổi production để né lỗi. Fullrecord sau đó và fulltest/verifyPaparazzi/lint/assemble main+test đều đạt:320cases/0failure/error/1exportskip, lint0errors/44warnings.
- Snapshot hashes chỉ61_no_voice sáng/tối thay đổi đúng copy; các ảnh khác không đổi. Review ảnh sáng đạt.
- Native5cached recordings decoded,5WAV qua continuity guard thật, mapped duration rounding≤nửa mẫu16k; resources release.3synthetic same rawPCM/normalizedWAVbytes/offset và3cancelrejections đạt. Không capture/playback/upload/model trong probe; nguồn gốc vật lý chưa được chứng minh.
- APK SHA256`ac27386f943efb9f392f7f9071e0fceaa6803ee8850c3e7f6399ebca54739552`, signer822e5e44.../v2verified, liveDefaulttrue/signedtrue/tracefalse, đã cài-r giữ dữ liệu. Cần ghi codecommit vào gói sau chốt.
