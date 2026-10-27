# Bàn giao · APP-01 · Ngọc Quang+Claude · 2026-10-27 20:00

**Nhánh:** `feat/APP-01-ui-polish` (PR #87, xếp trên #69), commit `ffb9b28`
**Trạng thái task sau phiên này:** review (phần thử máy thật mới làm một phần)

## Đã xong
- Sửa 2 lỗi (Codex viết, Claude rà, commit `ffb9b28`):
  - **QR mặt trước:** thẻ CCCD gắn chip in QR ở mặt trước nhưng app chỉ gửi QR mặt sau. Giờ xóa QR mỗi lần chụp/chụp lại một mặt (`QrCaptureState`, bỏ kết quả quét cũ về muộn), gửi QR mặt sau nếu có, không thì mặt trước (`FlowRules.cardQr`), tính lại `cccd` từ cả 2 mặt.
  - **MP4 chưa đóng:** `finishedVideo()` trả `Ready` chỉ khi có `VideoRecordEvent.Finalize` của CameraX không lỗi; hết 3 giây thì không gửi gì, giữ file, ra màn "Video chưa sẵn sàng" (`Routes.UploadFailed`) có nút "Thử lại". Máy không quay video thì vẫn gửi không video như cũ.
- **Thử lần đầu trên điện thoại thật** Samsung Galaxy S24 FE (SM-S721B), bản debug `ffb9b28`, API mock của nhánh `feat/FLOW-01-voice-on-suspicion` (`d642814`, PR #86), `USE_MOCK_MODELS=true`, DB riêng `tmp/dev-flow01.db`. Thẻ thật là CCCD gắn chip (QR ở mặt trước); dùng mặt người thật, không bấm nút debug.

| Kịch bản | Kết quả trên app | Quyết định server (bảng `decisions`) | Ghi chú |
|---|---|---|---|
| `genuine` | Thành công, **không có bước đọc câu** | `pass` | Đúng luồng mới của #86 |
| `low_quality` | Chụp lại phần mặt 2 lần, lần 3 chờ duyệt | `retry`, `retry`, `review` | Mỗi lượt lấy `challenge` mới |
| `voice_clone` | Có bước đọc câu, rồi chờ duyệt | `voice_challenge`, `review` | `/voice` gửi WAV + MP4, `lipsync` chạy |

  Thứ tự gọi API mỗi phiên (log server, đều 200): `sessions` → `otp` → `otp/verify` → `id-card` → `challenge` → `id-card/confirm` → `media` → `signals` → `finalize` (→ `voice`). CCCD tự chụp được cả 2 mặt, `id-card` nhận ngay, không bị bắt chụp lại mặt sau (QR mặt trước được dùng).

## Đang dở
- Chưa kiểm trên máy thật: chiều quay đầu (`yaw`), rung (`CONTEXT_CLICK`), Home giữa lúc quay, từ chối quyền camera/micro, mất mạng giữa chừng, thẻ "Căn cước" 2024 (QR mặt sau), màn "Video chưa sẵn sàng" có xuất hiện không.
- Chưa thử qua HTTPS (cloudflared) và bản release.

## Bước tiếp theo
1. Chờ merge #69 → #86 và #87. Sau đó ghép `main` (Keystore, ký media, tài khoản SEC-02/PLAT-06) vào app; gọi biên nhận tài khoản ngay khi `finalize` trả `pass` (hiện `LiveFlow` trên `main` chỉ lấy khi bước giọng đạt, `accountReceipt` dòng ~313); sửa `MediaProof.manifest` cho phiên `reauth` (đang `require(purpose in onboarding, recovery)`); nối UI đăng nhập lại/khôi phục với tài khoản đã lưu.
2. Thử nốt các mục "Đang dở" trên S24 FE.
3. Build release `-Pvericlue.apiBaseUrl=https://<địa-chỉ>/`, chạy lại cả 3 kịch bản qua HTTPS, ghi checklist demo.

## Quyết định, lưu ý, bẫy
- Nối điện thoại: bản debug chỉ cho HTTP tới `localhost`/`10.0.2.2`, nên dùng `adb reverse tcp:8000 tcp:8000` và build `-Pvericlue.apiBaseUrl=http://localhost:8000/`.
- Dây USB tuột 2 lần làm mất `adb reverse` (app báo lỗi mạng). `adb pair` qua Wi-Fi trên Windows báo `protocol fault` (adb 37.0.1). Cách chạy được: cắm dây, `adb tcpip 5555`, `adb connect <ip>:5555`, rồi `adb -s <ip>:5555 reverse tcp:8000 tcp:8000`. Mất khi khởi động lại máy hoặc đổi mạng. `adb reverse --remove-all` trên kết nối USB cũng xóa luôn bên Wi-Fi.
- Log uvicorn ghi ra file bị dồn bộ đệm; chạy với `PYTHONUNBUFFERED=1` để thấy request ngay.
- Server FLOW-01 chạy từ worktree `D:\vericlue-wt\flow01` (detached `d642814`); xóa bằng `git worktree remove` sau khi #86 merge.
- Ảnh chụp màn hình có thông tin thẻ thật đã xóa khỏi `tmp/`; không ghi dữ liệu thẻ vào repo.

## Câu hỏi cho nhóm
- Không có câu mới. Vẫn chờ trả lời `apps/android/docs/can-chot.md` câu 27–29, 31–33; câu 29 sẽ đóng khi #86 merge.

## Test đã chạy
```
cd apps/android
./gradlew testDebugUnitTest assembleDebug        # 99 test, 0 lỗi; BUILD SUCCESSFUL (27/10, JDK 17)
./gradlew assembleDebug -Pvericlue.apiBaseUrl=http://localhost:8000/
adb install -r app/build/outputs/apk/debug/app-arm64-v8a-debug.apk   # S24 FE, Success
# Codex (cùng thay đổi, trước khi dọn UploadFailed): lintDebug 0 lỗi, 43 cảnh báo;
# recordPaparazziDebug --tests '*ScreensSnapshotTest*' thành công. Chưa chụp lại sau khi dọn.
```
