# Bàn giao · APP-01 · Ngọc Quang+Claude · 2026-10-27 22:20

**Nhánh:** `feat/APP-01-account-flow` (PR #98, vào `main`), commit `a458c1c`
**Trạng thái task sau phiên này:** review

## Đã xong
- Merge vào `main` theo thứ tự #69 → #86 → #87 (merge commit). #87 xung đột 1 dòng ở `docs/plan/backlog.md` với `main`, giữ bản của `main`; job Python của #87 đỏ do runner CI thiếu ổ đĩa, không do code.
- Nối tài khoản SEC-02 vào app (#98):
  - `data/AccountStore.kt`: lưu `AccountReceipt` trong SharedPreferences riêng app; hết hạn hoặc hỏng thì xóa và coi như chưa có.
  - `LiveFlow.receiptAfterPass()`: biên nhận từ bước giọng, hoặc `GET /v1/sessions/{id}/account` khi đăng ký đạt ngay ở `finalize` (FLOW-01). `LiveFlow.boundAccount` được `ensureSession` dùng mặc định, `reset()` xóa.
  - `App.kt`: màn thành công (đăng ký/khôi phục, bản live) lưu biên nhận, không có thì chỉ log. "Đăng nhập lại" dùng biên nhận đã lưu; không có hoặc tắt `signedMedia` thì báo ngắn và về đăng ký. Khôi phục gửi `account_id` đã lưu.
- `503 flow_unavailable` đã ra màn "Dịch vụ chưa sẵn sàng" sẵn (`ApiError.Busy` → `ErrorService`); `recovery_required` đã có màn riêng. Không phải sửa.
- Build release `assembleRelease -Pvericlue.apiBaseUrl=https://example.invalid/ -Pvericlue.signedMedia=true` chạy được; APK ký bằng khóa debug (`build.gradle.kts:47`), đủ để cài demo.

## Đang dở
- Chưa thử trên máy thật: server mock không tạo tài khoản (`account-enrollment.md`: mock/mixed bị từ chối), nên chỉ thử được khi chạy mô hình thật + `ACCOUNT_ENROLLMENT=true`.
- Chưa chạy release qua HTTPS thật (chưa cài cloudflared), chưa có checklist demo.
- Chưa thử máy thật: Home giữa lúc quay, từ chối quyền, mất mạng, quay đầu, rung.

## Bước tiếp theo
1. Duyệt và merge #98.
2. Khi nhóm ML chạy được server mô hình thật có `ACCOUNT_ENROLLMENT=true`: cài bản `-Pvericlue.signedMedia=true`, đăng ký → kiểm biên nhận đã lưu (`adb shell run-as vn.vericlue.app cat shared_prefs/vericlue.account.xml`) → đăng nhập lại (hiện sẽ ra "Dịch vụ chưa sẵn sàng" do server).
3. Có địa chỉ HTTPS thì build release với địa chỉ đó, chạy lại 3 kịch bản, ghi checklist demo.

## Quyết định, lưu ý, bẫy
- Một alias Keystore cố định (`vericlue.media.v1`); khôi phục chưa đổi khóa mới. Đổi alias cần thiết kế lại `AndroidMediaSigner`, để sau khi server mở recovery.
- Bản demo (không live) không đọc tài khoản đã lưu, vẫn đi đủ 3 luồng giao diện.
- `testDebugUnitTest -Pvericlue.signedMedia=true` lỗi 24 test LiveFlow ngay trên `main` gốc (test chưa viết cho chế độ ký); trên nhánh đã gộp là 26. Chế độ mặc định xanh.

## Câu hỏi cho nhóm
- Server: bước sinh trắc reauth/recovery có tài khoản luôn trả `503 flow_unavailable` (`session_flow.py` ~dòng 254), kể cả mock. Ai mở luồng này (FLOW-05/SEC-02) và khi nào, để app thử trọn đăng nhập lại trước 06/11?
- CI: runner thiếu ổ đĩa cho test tải dữ liệu (cần ~10 GB, có ~4 GB); job Python đỏ.
- Demo có bật sẵn `signedMedia` trong bản release không? Đăng nhập lại cần cờ này.

## Test đã chạy
```
cd apps/android
./gradlew testDebugUnitTest assembleDebug lintDebug    # 113 test, 0 lỗi; lint 0 lỗi (27/10, JDK 17)
./gradlew assembleRelease -Pvericlue.apiBaseUrl=https://example.invalid/ -Pvericlue.signedMedia=true   # BUILD SUCCESSFUL
uv run python scripts/plan_check.py                     # 0 lỗi, 10 cảnh báo
```
