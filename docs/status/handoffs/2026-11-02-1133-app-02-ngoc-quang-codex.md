# Bàn giao · APP-02 · Ngoc Quang+Codex · 2026-11-02 11:33

**Nhánh:** codex/APP-02-single-turn-guidance, base60505eb của DraftPR131.
**Trạng thái:** doing, chờ thử lại; app/khôi phục chưa done.

## Thay đổi
- Người dùng xác nhận app nhắc lặp cùng bên. Backend quan sát hai đợt giữ mỗi bên; UI có thể tái yêu cầu hướng cũ khi local hold850ms chưa hoàn tất nhưng người đã về giữa trong đoạn5s.
- SegmentReturnTracker chỉ ghi một excursion đúng phía rồi về giữa bằng quan sát mới/hợp lệ, riêng từng segment. Chờ trung tính, ẩn mũi tên quay ra, cue nhìn thẳng; không bắt lặp cùng bên. Không đặt SegmentHoldTracker.completed, không đổi phase/API/ngưỡng/hằng góc/hold/lịch5/5/2.
- Cảnh báo vẫn ưu tiên. Stale/no-face/sai hướng không tạo latch; quan sát đúng phía đã có được giữ trong cùng đoạn, nhưng chỉ neutral mới/hợp lệ mới chuyển chờ. Reset khi đổi segment.

## Kiểm tra
- TDD REDoldbehavior7case/3fail; thêm ca observationgap và wrongsidehistory RED rồi GREEN. Focused36/36.
- Root review diff, fullAndroid262test/0failure/error/skip; lint0errors/44warnings, assembleDebug và Paparazzi record→verify đạt. Baseline code hiện tại, không so sánh lịch sử.
- Python/API không đổi; toàn suite Python đã đạt ở parent. plan_check cần chạy trước commit; không commit trace/media/APK/khóa.

## Tình trạng máy thật
- API/voicecapture fixesD73 đã cài. Sau đó một recovery qua toàn bộ mặt, Qwencontent (sau một lần đọc lại),AntiDeepfake vàcontinuity; còn lipsyncfail. Tài khoản/khóa cũ giữ nguyên, chưa commitrecovery binding.
- SyncNet rawzero-clockconfidence thấp, bestshiftedconfidence cao hơn; không tự dùngpeakoffset sửa clock hoặc nới gate. Audit chưa thấy lỗi cửa sổ cố định160/200ms; crop/hardwareclock/hiệu chỉnh còn thiếu bằng chứng.
- Bản latch mới cần cài đè cùng signer, không restart server vì API không đổi. Chưa có kết quả thật cho APK này. Người dùng được nghỉ tay, không yêu cầu lặp vô hạn.

## Bước tiếp theo
1. Cài-r APK mới, ghi hash/source/kiểm health/ADB; giữ account/profile/media/source cũ.
2. Rà cách ghi AV/cropSyncNet, lập proof bằng fixtures/giao thức đúng trước khi sửa. Chỉ mời thử thêm khi có thay đổi cụ thể cần nghiệm thu.
3. Không đổi ngưỡng từ các lượt máy thật, không dùngVIVOSparity đểfit; dữ liệu hiệu chỉnh/eval theo người vẫn cần nhóm chuẩn bị có quyền dùng.
