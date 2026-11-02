# Bàn giao · APP-03 · Ngoc Quang+Codex · 2026-11-02 11:01

**Nhánh:** codex/APP-03-s24fe-voice-readiness; baseb30a8b0 của DraftPR129.
**Trạng thái:** doing; chưa nghiệm thu khôi phục/giọng, không gọi cả appdone.

## Kết quả máy thật trước sửa
- Đã có một đăng kýCCCD/mặt và một đăng nhập lại thành công trên APK1367c2e. Sau đó recovery nhiều lượt review, nguyên nhân tách theo từng lượt: gaze/head chất lượng; GenD raw chính diện vượt cutoff; không thay ngưỡng hoặc dùng các lượt này để fit.
- APK69d41d3 dùng5/5/2giây tổng12s; có các lượt gaze/head đạt nhưng GenD chặn. Một lượt diagnostic trace bật tạm (APKsourceb30a8b0, SHAfeb93bef…) qua toàn phần mặt/GenD và đến voice. AntiDeepfake/continuity qua, Qwencontent và lipsync chưa qua. Tài khoản/khóa cũ giữ nguyên; chưa commit recovery binding.
- Trace đúng attempt: không có mẫu stale>300ms, không có phản hồi xanh ngoài vùng pose server trong lượt này; dấu vết nhịp5/5/2 đúng. Đây là số đo phần mềm, không chứng minh hardware clock. Đã lấy trace private và cài lại bản thường69d41d3; trace/APK diagnostic không đưa lên GitHub.
- Nhận dạng6chữ số khớp, khác ở câu dẫn; không có numeric-run ASR, nên lỗi cardinal-number-normalization có thể tái hiện tổng hợp nhưng không phải nguyên nhân lượt này. CTC forced alignment đủ14âm tiết, degraded là nhãn diagnostic mặc định. WAV6.64s chưa chạm cap8s. Không công khai câu/mã/giọng/media/ID/token/embedding.

## Đã sửa
- API manual voice: kết quả thựcOK/FAIL/E_CHALLENGE_MISMATCH trước đây bị kết thúc ngay do guarderror_code, không dùng được lượt đọc lại. Cho đúng trường hợp này vào giới hạn đọc lại hiện có; một lần, ID/câu/proof mới. Giữ mọi lỗi bất thường/error/degraded failclosed, không đổi gate/cutoff.
- Android Preparing→Recording chỉ sau AudioRecord xác nhận. Micro native start thất bại không nhận là đang ghi; hủy/chạm lặp/native read trả muộn an toàn. Cap8s tự kết thúc một lần, không âm thầm cắt dữ liệu trong khi UI vẫn báo ghi.
- Offset lấy sau micro start/recording-state check, vẫn software estimate. CameraStatus cũ sauFinalize(success/error/cancel) không được xem là camera còn chạy. Không đổi lịch5/5/2, protocol, hợp đồng, ngưỡng, khóa hoặc dữ liệu.
- Công cụ compare_presence_trace đóng DB trước nativeMediaPipe, giữ đúng attempt/retention và lease cho tới hết native; cleanup trên mọi nhánh lỗi. Đây là lỗi công cụ, không phải nguyên nhân đã chứng minh của kết quả người dùng.

## Kiểm tra
- API rereadRED5case→GREEN11; toàn manualfile+realECDSAreplay70testđạt. Từ chối ID cũ, proofcũ, thiếu proof mới; lỗi ngoài allowedshape vẫnreview.
- Android recorder/coordinator RED các race/fail/cap; focused41testđạt. Review độc lập bắt thêm camera finalized readiness: RED3→GREEN26testliên quan. Root đọc diff và kiểm ảnh Preparing không clipping.
- Full Python: exit0,100%; Ruffcheckall sạch,881fileformatcheckđạt. WarningStarlette/Pydantic đã có.
- Full Android253test/0failure/error/skip; lint0errors/44warnings. recordPaparazzi→verifyPaparazziDebug/assembleDebug thành công. Golden tạo từ code hiện tại, không gọi là so sánh với baseline lịch sử.

## Cần tiếp tục
1. Đóng gói source có commit/manifest gồm models/manifest.yaml và third_party; backupSQLite/giữ source/APK/profile/khóa/DB/media trước đổi server. Cài-r cùng signer; không uninstall/clear hoặc restart giữa capture.
2. Kiểm APIownership/health/ADB và thử recovery+voice trên S24 FE với người dùng. Không đánh dấu từ test phần mềm.
3. Nếu vẫn không quaQwen/SyncNet/GenD, báo đúng module/cấu hình và cần dữ liệu/hiệu chỉnh tách người; không nới cutoff dựa trên các lượt nghiệm thu này. Numeric-code contextual normalization chưa được sửa, không phải lỗi hiện tại.

## Câu hỏi cho nhóm
- Chưa có dữ liệu thật/TTS/VC quyền dùng và mã người/nguồn cho hiệu chỉnh/eval; vẫn giữ chốt. Không dùng32VIVOSparity để chọn ngưỡng.
- Lipsync originalclockconfidence thấp, bestoffset cao hơn chưa chứng minh lệchhardware; không tự dịch audio theo optimum của model để cho qua. Mốc phần mềm mới cũng chưa là hardware firstsample timestamp.
