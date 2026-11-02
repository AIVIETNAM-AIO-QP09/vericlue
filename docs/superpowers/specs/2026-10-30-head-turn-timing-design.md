# Tăng thời gian quay đầu trên Android

Ngày 30/10/2026. Người dùng đã duyệt thiết kế 4 giây/hướng. Task LIVE-01/FLOW-04/APP-01.

## Mục tiêu và nguyên nhân đã kiểm tra

Người dùng chọn tăng thời gian từng hướng thay vì thêm bước tập riêng. Lượt thử
thứ hai có đủ độ dài video; dữ liệu chuyển động trong hai đoạn trái/phải vẫn
gần chính diện. Người dùng xác nhận thấy hướng dẫn nhưng chưa kịp làm theo.
Đây là bằng chứng hướng dẫn hiện hành quá gấp với người thử, không phải bằng
chứng model đã được hiệu chỉnh hay có thể xác minh đạt sau khi kéo dài lịch.

Hiện server phát tổng 6000 ms cho ba đoạn, Android chia thành 2000 ms/đoạn.
Hợp đồng và detector hiện chỉ nhận 6000; iOS còn kiểm dynamic version bằng 1.
Đây là thay đổi hợp đồng cần đồng bộ, không sửa riêng tốc độ hiển thị Android.

## Phương án chọn

Đề xuất **4000 ms/đoạn**, tổng **12000 ms**: hướng thứ nhất ngẫu nhiên,
hướng còn lại, rồi nhìn thẳng. Giữ tư thế theo hướng dẫn đến khi chuyển đoạn;
không quay về giữa ngay trong đoạn trái/phải. Không đổi yêu cầu góc, thời gian
giữ tối thiểu, coverage, tính liên tục hoặc chính sách quyết định.

3000 ms/đoạn giảm thời gian chờ nhưng ít thời gian phản ứng hơn; 5000 ms/đoạn
đưa tổng lượt gần giới hạn 30 giây hơn. Chọn 4000 như mức khởi đầu để nghiệm thu
UX trên điện thoại, không tuyên bố tối ưu khi chưa thử.

## Hợp đồng và tương thích

- Dynamic v1 giữ cặp `(version=1, head_duration_ms=6000)` để đọc lượt cũ.
- Dynamic v2 dùng cặp `(version=2, head_duration_ms=12000)` cho lượt mới.
- Schema ràng buộc hai cặp, không nhận tổ hợp chéo hoặc thời lượng tùy ý.
- `head_start_at_ms` vẫn ngay sau đường chấm sáng; `voice_start_at_ms` vẫn bằng
  head start cộng head duration. Video mặt và video giọng vẫn là hai bản ghi
  theo luồng hiện hành; không tự thu âm ở cuối timeline mặt.
- Generator phát v2; thử lại/gia hạn tạo gói mới đúng version, ID và nonce mới.
- Giữ trần 30000 ms và 64 MiB. Kiểm tổng lịch trước phát và trước decode;
  không nới giới hạn decoder/frame/timeout để hợp thức hóa video quá dài.
- Cập nhật schema trước, đồng bộ Pydantic/OpenAPI/examples/type SDK web,
  Android và tài liệu trong cùng thay đổi. Không đổi ADR/thresholds/STATUS.
- Android nhận cả hai version và kiểm cặp duration/version. Lượt đang mở cũ
  không được kéo dài bằng offset client. Sau cập nhật thử bằng phiên mới.
- iOS không triển khai trong đợt này theo phạm vi người dùng; ghi rõ client iOS
  hiện từ chối v2, không tuyên bố tương thích. Không dùng build này để demo iOS.

## App và ML

Android tiếp tục lấy mọi mốc từ gói server và t=0 của video. Ba đoạn v2 dài đúng
4 giây, không tự thêm delay sau khi quay đã bắt đầu. Thêm nhãn thời gian còn lại
và hướng tiếp theo bằng chữ tĩnh cập nhật; không thêm animation camera, không
đổi màu/tần suất nháy, không thêm TTS hay tự đổi lời nhắc thành điều kiện đạt.
Không thêm bước tập riêng vì người dùng chọn tăng thời gian.

ML chỉ nhận gói server gắn đúng phiên/lượt. Cùng yêu cầu trái/phải/giữa và
baseline hiện hành được kiểm trong cửa sổ dài hơn; video không đủ cửa sổ hoặc
sai chuyển động vẫn không đạt. Không đổi v1 thành v2 trong metadata video cũ.

Pipeline PAD/GenD và đối chiếu nhiều góc phụ thuộc lịch lấy khung. Phải gắn định
danh protocol v2 vào provenance/version hiệu chỉnh phù hợp, đồng bộ adapter và
collector; artifact v1 không tự áp cho v2. Cache calibrator theo đúng version,
không sửa `self.version` chia sẻ giữa các request để chọn artifact. Thiếu
artifact hợp lệ tiếp tục diagnostic/degraded; không tự fit từ video thử này.
Giọng và các detector chỉ dùng phần lịch không đổi cũng phải đọc được gói v2;
không coi đổi version gói là lý do bỏ kiểm phiên/nonce/challenge.

## Kiểm chứng và triển khai local

1. Test đỏ schema/API generator: nhận đúng hai cặp, chặn tổ hợp sai, phát v2,
   voice offset đúng và tổng thời gian không vượt trần dưới cấu hình màu hợp lệ.
2. ML regression cho cả hai protocol, đúng/sai thứ tự, thiếu đầu/cuối video,
   sai phiên/version, không mượn artifact v1. Các ngưỡng giữ nguyên.
3. Android test ranh giới chuyển đoạn 4 giây, thời điểm kết thúc, lịch v1,
   version/duration sai bị chặn và không tự fallback giả lập.
4. Kiểm OpenAPI/type, Python tests/lint, Android testDebugUnitTest và assembleDebug;
   Paparazzi màn có nhãn mới. Không cần build iOS.
5. Cập nhật task/backlog (giữ doing cho phần còn thiếu), handoff. Commit local
   có mã task và [contract], không push/PR.
6. Build/ký bằng cùng khóa debug đã cài, kiểm checksum/chữ ký, cập nhật APK bằng
   install -r, không gỡ app/xóa Keystore. Restart server, nối lại adb reverse,
   thử gói mới trước khi người dùng chạy lượt mới. Không export media người thử.

## Giới hạn bàn giao

Sửa này giúp người dùng có thời gian thực hiện động tác. Không giải quyết bằng
chứng chiều sâu, hiệu chỉnh PAD/GenD, danh tính/giọng, SEC-09 hoặc chốt ghi danh
mock/mixed. Bước theo mắt vẫn 7 giây và cần đánh giá riêng nếu tiếp tục không
khớp. Sau cài lại, phải nghiệm thu trên điện thoại trước khi kết luận UX đã tốt.
