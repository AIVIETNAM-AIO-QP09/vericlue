# Bàn giao · APP-01 · Ngoc-Quang+Codex · 2026-10-31 08:04

**Nhánh:** `codex/APP-01-demo-integration`, nền `3c7ce4e`
**Trạng thái task sau phiên này:** doing — APP-01/FLOW-04 chờ nghiệm thu người thật/hiệu chỉnh toàn luồng

## Đã xong
- Head rules tăng0.1→0.2: bỏ phủ quyết toàn video vì một yaw outlier. Mẫu
  abs(yaw)>50° không đóng góp bằng chứng giữ; vẫn ngắt run, không ghép các mẩu
  giữ ngắn. Coverage80%, gap300ms, biên200ms, hold300ms, baseline/thứ tự và
  kiểm pixel khung được chọn giữ nguyên. Pitch/roll15° vẫn chốt cứng.
- SessionFlow cho retry chất lượng góc tối đa một lần với HOLD_STILL và
  challenge/nonce mới, dọn bằng chứng cũ qua nhánh retry sẵn có. Chỉ áp dụng
  onboarding/recovery có quality/gaze/presence đạt, head degraded/unclear do
  pose_out_of_range và các kết quả mặt phù hợp; không áp dụng reauth.
- Dùng kết quả sau calibration của router để không che ERROR/E_INTERNAL,
  thiếu artifact hoặc kết quả đã vượt chốt. Gate fail/lỗi độc lập vẫn giữ review.
- Bỏ phần tập khỏi điều hướng Android, giữ quality gate trước ghi hình.
- TTS thêm trace opt-in ready/say/start/done/error với cue cố định, không dữ
  liệu cá nhân. Probe mặc định vẫn im lặng; `-e audible true` chỉ phát một câu
  cố định khi người thử sẵn sàng, không quay/thu âm/gửi lượt.
- Review cuối không còn P1/P2 ở helper retry. Không đổi schema/ngưỡng/OTP/SEC-09.

## Đang dở
- Người dùng đang bận điện thoại, chưa xác nhận nghe giọng hay thử lượt mới.
  Đã dừng thao tác/phát thêm tiếng sau khi nhận tin. Không ghi voice đã sửa xong.
- Artifact video-v2 PAD/GenD/match/consistency và quyền lưu mẫu còn thiếu;
  bản sửa không mở guard hoặc bảo đảm xác minh toàn luồng đạt.

## Bước tiếp theo
1. Khi người dùng rảnh, thử một lượt mới. Không bắt thử lại trước khi đọc kết
   quả đúng attempt nếu còn lỗi. Xem runbook head-turn-coaching/diagnostics.
2. Kiểm xem góc không hợp lệ được nhận retry chất lượng một lần; phần tiếp theo
   có thể vẫn review do thiếu hiệu chỉnh. Không dùng retry như bằng chứng pass.
3. Nếu không nghe lời, lấy tag VeriClueHeadSpeech ở lượt đang thử để phân biệt
   chưa ready, speak bị từ chối, callback trễ hoặc bị hủy khi đổi cue/ra nền.

## Quyết định, lưu ý, bẫy
- Lượt07:51:53 ngày31/10, commit3c7ce4e: quality/CamProbe/gaze pass; head
  pose_out_of_range. 124/125 pose hợp lệ,1 noface, yaw59,81°, pitch6,58°,
  roll14,3°. PAD/GenD E_LOW_QUALITY theo session_views phụ thuộc head; match cũng
  E_LOW_QUALITY (không tách riêng được do frontal hay view gate từ kết quả đó).
- Paired trace đúng attempt:165 cặp, offset≤83,26ms,0stale,0green ngoài giới hạn
  server. Chưa có bằng chứng app báo xanh trong khi server vượt góc ở lượt này.
- Replay giữ nguyên video/lịch với rules0.2 vẫn degraded pose_out_of_range,
  có19 mẫu yaw vượt50°. Không dùng mẫu này chọn ngưỡng hoặc gọi nó là accuracy.
- APK mới đã install -r Success cùng signer822e5e44…, giữ dữ liệu app. Probe
  phát câu với audible=true, engine offline/callbackdone=true; chưa có xác nhận
  nghe từ người dùng. Tên output silent_utterance_callback là nhãn cũ của runner,
  ở lần này command có flag audible; không suy ra tiếng nghe rõ từ callback.
- Artifact local private: `D:\vericlue\tmp\full-demo-setup\head-coaching\`.
  Không commit trace/video/âm thanh/trọng số/.env/khóa.
- Không push/PR. Người dùng đã hủy tắt máy; không hẹn lại.

## Câu hỏi cho nhóm
- Tiếp tục thu/fit artifact theo người đúng protocol, quyền lưu mẫu SEC-09 và
  nghiệm thu điện thoại. Không có cơ sở để đóng toàn bộ demo AI thật.

## Test đã chạy
```
TDD head: hai trường hợp v1/v2 outlier thoáng qua RED trước sửa, GREEN sau;
55 test head/protocol/session_views qua. Test quá góc lâu/thiếu/sai thứ tự,
tilt/mất mặt/nhiều mặt vẫn giữ không đạt.
TDD retry: capture retry RED trước sửa; calibration_missing và attack_probability
được kiểm hồi quy (đã tái hiện đúng AssertionError trước guard tương ứng).
Android testDebugUnitTest assembleDebug assembleDebugAndroidTest: BUILD SUCCESSFUL,
192 tests,0failure/error/skip. Có CitizenCopyTest/ThemeAccessibilityTest.
Ruff check toàn repo: sạch. plan_check.py:0 lỗi,10 cảnh báo kế hoạch có sẵn.
Full Python:4555 passed,80 skipped,2 warnings,709,28s; exit0.
Warnings: Starlette/httpx deprecated và Pydantic serializer khi test artifact
cố ý sai module. Không sửa phụ thuộc trong task. Hai lượt full trước đó đã
dừng sớm để sửa hồi quy/review, không
được coi là kết quả pass; chỉ dùng pose-verified-python.xml/log ở lượt cuối.
```
