# Bàn giao · APP-01 · Ngoc Quang+Codex · 2026-11-01 14:25

**Nhánh:** codex/APP-01-demo-integration; nền0261b9b, main GitHub7fc2ce9.
**Trạng thái task sau phiên này:** doing; chuẩn bị PR Draft, chưa nghiệm thu AI thật.

## Checkpoint tạm dừng và tiếp tục

- Người dùng đã yêu cầu `continue` sau checkpoint bên dưới; tiếp tục kiểm chứng
  và chuẩn bị ba Draft PR theo phạm vi đã cho phép, không merge main.
- Chẩn đoán renderer ghi nhận initial elapsedRealtimeNanos=0. Fixture gán capture
  cố định100ms là frame tương lai ở composition đầu; chỉ chuyển đúng trạng thái
  sau guide tick nên phụ thuộc lịch recomposition. Fixture cuối lấy capture từ
  chính clock renderer, clamp tối thiểu1ns (cùng millisecond0), chụp offset100ms.
  Không đổi clock global, guard production hoặc golden để nhận cảnh báo sai.
  Log chẩn đoán: android-clock-probe.log; kết quả cuối ghi bên dưới sau verify.
- Verify sau tiếp tục: `testDebugUnitTest assembleDebug verifyPaparazziDebug
  lintDebug` BUILD SUCCESSFUL trong1m32s,206tests/0failure/0error/0skip;
  lint0error/43warning/3information. Log android-resume-final.log. Không cần
  ghi đè golden để nhận trạng thái sai hoặc đổi chốt timestamp production.
- Reviewer Android đã đọc lại fixture cuối: không thấy must-fix. Ruff vừa
  chạy lại sạch850file; plan_check0lỗi/10cảnh báo. Audit184đường dẫn và45commit
  chưa thấy chữ ký token/khóa thuộc nhóm quét, dữ liệu/trọng số/file lớn hoặc
  notebook output; không coi đây là chứng nhận đầy đủ hết bí mật.

- Tại checkpoint người dùng yêu cầu tạm dừng trước khi xuất bản. Đã dừng; chưa push, chưa tạo
  PR hoặc nhánh review, chưa commit bản sửa review. HEAD vẫn0261b9b trên nhánh gốc.
- 17 file sửa review/test/README/bàn giao đang staged; giữ nguyên index/worktree.
  Không reset, xóa; đã chờ đúng yêu cầu tiếp tục của người dùng.
- Full Python cuối đúng worktree:4695passed/118skipped/2warning. Android unit206
  và build đã từng đạt; lint đạt0error/43warning/3info. Native NES2Net2passed,
  WSL17passed, web unit1319passed; web build còn SecurityFatalError Next16.4.0.
- Lượt `android-public-offset-final.log` mới nhất:206tests,1snapshot failure tại
  SmallFaceChallengeSnapshotTest.headAssistStates/assist_hold (delta3.240665%).
  OTP filled đã qua sau offset100ms; không ghi đè golden Hold bằng trạng thái
  sai. Cần phân tích delta/settling frame rồi verify lại trước xuất bản.
- Fixture tại checkpoint dùng ComposeView public snapshot offset100ms, capture100ms;
  không còn thay boot/global clock. API/policy/protocol/timestamp fixes vẫn giữ.
- Ba PR body nháp và toàn bộ log nằm ngoài Git tại
  D:/vericlue/tmp/publish-review-2026-11-01/. Chưa điền/publish validation cuối.
- Khi tiếp tục, giữ worktree đang chạy demo ổn định khi tạo các ref review;
  bảo toàn commit đo52cebaf và source job140beb5. Phương án refs/index riêng có
  thể tránh checkout nhánh trong worktree đang chạy; chưa thực hiện thao tác đó.

## Đã xong
- Người dùng đã cho phép kiểm lại và push/mở PR phần phù hợp; không merge main.
- Review độc lập API/Android/ML xác nhận bốn vấn đề cần sửa trước xuất bản:
  recovery mượn ngưỡng protocol cũ; timestamp camera bất định trở thành hiện tại;
  policy ngưỡng provisional vẫn mở đường chuẩn; MVP chuẩn thiếu ChromaPulse
  trong khi ghi danh/ký reauth vẫn cần mô-đun này.
- Đã sửa bằng chốt sớm và binding version chính xác, không đổi thresholds.yaml:
  recovery v2 dùng `RECOVERY_MATCH_VERSION + "+head12s-v2"`; kiểm cả ngưỡng
  consistency, identity gate, account validation và continuity. Giữ version v1
  riêng cho giao thức cũ. Protocol/version sai không thể đổi khóa tài khoản.
- Camera loại timestamp không nhận diện/không dương/tương lai trước metadata,
  JPEG và analyzer. Chuyển đổi CLOCK_MONOTONIC giữ tuổi khung; coaching không
  đếm timestamp thiếu hoặc khung lặp. REALTIME không chuyển sang miền nano.
- Standard mode từ chối router policy provisional và profile thiếu ChromaPulse
  cho luồng tài khoản. Không nới yêu cầu downstream hoặc bật pass để quay demo.
- Test RED tái hiện các lỗi; GREEN nhóm Python ảnh hưởng227passed. Android
  unit206/0failed, build debug đạt. Ba reviewer đã đọc lại patch, không còn lỗi
  bắt buộc sửa được xác nhận trong phạm vi đã review.

## Đang dở
- Full Python cuối đã đạt4695passed/118skipped/2warning trong517.42s với
  PYTHONPATH tuyệt đối của worktree. Lượt đường tương đối làm CLI subprocess
  ở cwd khác lấy ML editable từ D:/vericlue; không sửa rotate_master_keys.py
  để né sai môi trường này. Rerun riêng key rotation đúng đường14passed/1skip.
  Log mọi lần vẫn giữ ngoài Git.
- Web build bị Next16.4.0 SecurityFatalError, package/lock không đổi so với main.
  SEC-07 vẫn cần bản vá riêng; không bỏ qua cảnh báo hoặc gọi build đã đạt.
- Chưa có dữ liệu/artifact đủ hai lớp và protocol mặt/giọng; chưa có LTT/test
  được nghiệm thu, OTP mô phỏng, chưa nghiệm thu Android ba luồng bằng người.

## Bước tiếp theo
1. Xác minh full test cuối và ghi số thực; commit fix review riêng.
2. Tách nhánh review nối tiếp: main→a542a47+fix (Android/API/SEC09), tiếp đến
   measured parity/utterance ở194af1d+fix, rồi cloud prep ở0261b9b+fix. Giữ nguyên
   lịch sử các commit đo, không squash/rebase làm sai nguồn52cebaf/140beb5.
3. Kiểm diff/secret/data/schema từng nhánh, mở PR Draft có phụ thuộc rõ, ghi đúng
   CI/giới hạn và không merge. Theo dõi CI; lỗi còn lại phải được mô tả cụ thể.
4. Dữ liệu hiệu chỉnh/đánh giá và nghiệm thu thiết bị làm tiếp khi nhóm có đầu
   vào. Quyền Colab không bao gồm chấp thuận điều kiện MLAAD; không lách gate.

## Quyết định, lưu ý, bẫy
- Chỉ code/test/tài liệu được xuất bản; không audio/model/.env/DB/APK/ZIP/khóa.
- Giữ nguyên worktree/nhánh gốc và toàn bộ thay đổi, không reset/delete/rebase.
  Tạo ref review và cherry-pick fix/merge lịch sử có kiểm; không thay cấu hình
  server hoặc cài APK mới vào điện thoại trong lượt xuất bản này.
- APK đã cài trước thuộc sourcea542a47, chưa chứa fix timestamp review này;
  APK build mới chỉ kiểm build, không tự suy thành nghiệm thu thiết bị.
- Parity/NES2Net vẫn degraded/unclear/null probability. Các test kỹ thuật không
  phải số đo chống giả mạo; VIVOS32mẫu/9người luôn ngoài hiệu chỉnh.

## Câu hỏi cho nhóm
- Dữ liệu tấn công/người/nguồn và artifact đủ protocol; đăng nhập/quyền MLAAD;
  thao tác thử Android; SEC-07 vá web. Không đổi STATUS hoặc đánh task app done.

## Test đã chạy
- Python nhóm thay đổi:227passed; full cuối4695passed/118skipped/2warning.
- Android `testDebugUnitTest assembleDebug`:206tests/0fail, build đạt.
- Journey snapshot: các golden local chưa có checkbox lưu mẫu mới, đã đối chiếu
  hình thực, record lại đúng lớp Journey rồi verify đạt. Golden/ảnh vẫn ignored,
  không commit; không gọi ảnh synthetic là nghiệm thu camera/CCCD thật.
- Fixture FaceChallenge cuối dùng public snapshot offset100ms và capture theo renderer,
  không đổi clock global hoặc thêm ngoại lệ timestamp0 vào app. Review hình9ca
  assist trên3cỡ màn xác nhận đúng Hold xanh/tilt và quá góc vàng, không phải
  cảnh báo khung cũ. Lượt verify toàn bộ cuối đã đạt206/0fail như phần tiếp tục.
- Hai lượt verify full gặp frame nút OTP autofill chưa chuyển màu, dù digits đã
  đủ; isolated identity đạt. Đã sửa fixture riêng OTP filled chụp sau100ms để
  effect/màu nút settle, giữ golden nút navy; không sửa logic OTP production.
- Android lintDebug đạt:0error,43warning/3information; không gọi hết warning sạch.
- WSL prep/notebook17passed, gồm symlink containment thực.
- Native NES2Net checkpoint/repeatability + upstream head parity:2passed40.36s,
  dùng báo cáo canonical `docs/status/results/VOICE-09-parity-2026-11-01.json`.
  Lần đầu trỏ nhầm raw Windows comparison bị từ chối KeyError/checkpoint field;
  đã sửa đầu vào, không bỏ binding hoặc thay report để ép đạt.
- Web lint/typecheck/format và1319unitpassed/10skip; schema gen không diff.
  Build exit1 vì SecurityFatalError ở Next16.4.0 kế thừa main.
- Ruff sạch849file format; plan_check0lỗi/10cảnh báo đã có.
- Audit nội dung/history trước fix:180file đổi,0file cấm/lớn/notebook output,
 0high-confidence token/private-key signatures; đây không phải chứng nhận tuyệt
 đối hết bí mật. Kiểm lại staged/history trước push. Log ngoài Git:
 `D:/vericlue/tmp/publish-review-2026-11-01/`.
