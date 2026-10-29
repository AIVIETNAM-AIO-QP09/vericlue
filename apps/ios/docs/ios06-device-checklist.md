# IOS-06 — Cổng 7: gián đoạn, retry và dọn file

Nhánh `feat/IOS-06-interruption-retry`, nền IOS-05 `58c36fd`.
Đây là checklist cho bản code mới, không suy rằng nghiệm thu IOS-05 tự bao phủ
IOS-06. Không gộp luồng đăng ký/theme Android mới vào lần thay đổi này.
Build thành công không đồng nghĩa test đã chạy hoặc các ca iPhone đã đạt.

## Chuẩn bị

1. Chạy API mock trên Mac như IOS-05, Debug.xcconfig đúng IP hiện tại. Mở healthz
   bằng Safari iPhone trước; Run lại app bằng Xcode nếu đổi IP.
2. Bật API thật/scenario genuine (hoặc voice_clone để tới giọng) trước tạo phiên
   mới. Không mở riêng route gallery để giả làm một luồng API thật.
3. Ghi model/iOS, commit + working tree IOS-06, IP/scenario. Không ghi token.
4. Sau một ca, cần bắt đầu lại từ chuẩn bị mặt, không tái dùng video/WAV cũ.
   Chỉ khi phiên hết hạn mới kết thúc phiên và làm lại từ ngân hàng.

## Mười ca bắt buộc

| Ca | Thao tác | Kỳ vọng | Nghiệm thu |
|---|---|---|---|
| 1 | Ra Home lúc căn mặt | Dừng camera, màn gián đoạn; Quay lại chuẩn bị về face_ready, lượt sau POST /challenge | Đạt theo sếp nghiệm thu 28/10/2026; không có log request máy thật đính kèm |
| 2 | Ra Home lúc quay mặt | MP4 dở bị hủy, trả brightness/idle state; không upload đoạn dở, không success | Đạt theo sếp nghiệm thu 28/10/2026 |
| 3 | Ra Home lúc ghi giọng | Dừng engine/video, bỏ WAV/MP4 dở; quay lại face_ready chứ không thu tiếp câu cũ | Đạt theo sếp nghiệm thu 28/10/2026 |
| 4 | Mất Wi-Fi lúc media | Báo lỗi; thử lại vẫn lỗi nếu chưa có mạng; có mạng chỉ gửi phần chưa ack | Sếp chốt nghiệm thu 28/10/2026; bằng chứng mạng thật chung + test retry/ack, chưa có log riêng endpoint máy thật |
| 5 | Mất Wi-Fi lúc signals | Media đã ack không gửi lại; signals giữ nguyên challenge/data | Sếp chốt nghiệm thu 28/10/2026; cùng giới hạn bằng chứng như ca 4 |
| 6 | Mất Wi-Fi lúc finalize | Không gửi lại media/signals đã ack; finalize lại, chỉ status hợp lệ mới điều hướng | Sếp chốt nghiệm thu 28/10/2026; cùng giới hạn bằng chứng như ca 4 |
| 7 | Mất Wi-Fi lúc voice | Giữ nguyên WAV/MP4/offset/voice ID khi gửi lại; không tự success hoặc thu lại | Sếp chốt nghiệm thu 28/10/2026; mạng thật chung + test tự động, chưa có log riêng payload máy thật |
| 8 | Bấm Back/Dừng giữa luồng | Hộp xác nhận; hủy hộp không bỏ lượt; Quay lại chuẩn bị bỏ lượt cũ và refresh; Dừng về bank/xóa dữ liệu | Sếp chốt nghiệm thu 28/10/2026. Bấm ngoài đóng hộp thay nút Tiếp tục; hộp không pause lượt. Thu lại từ đầu; Dừng về bank/file count 0 |
| 9 | Thu hồi quyền camera/micro, đổi input hoặc ngắt camera | Nếu process còn sống: báo lỗi/dừng an toàn; nếu bị kết thúc: bắt đầu phiên mới, không resume bản ghi dở | Sếp xác nhận phục hồi bằng phiên mới: quyền tắt báo thiếu quyền/mở Settings, không đóng khi vào bước thu; bật quyền app về đầu, chọn lại API thật thu được. Chấp nhận có ghi chú không khôi phục face_ready; chưa có log phân loại lần process bị đóng |
| 10 | Phiên/token hết hạn | Không thu/gửi tiếp bằng token cũ, không success; màn hết phiên, trở về bank/xóa payload | Đạt theo sếp nghiệm thu 28/10/2026 |

Ca 5/6 khó tắt Wi-Fi đúng thời điểm vì request nhanh. Đối chiếu log API chỉ đường
dẫn/status và các MockURLProtocol test theo từng bước; không giả rằng tắt trước
upload đã thử riêng cả ba bước. Test mô phỏng và thử mạng thật là hai bằng chứng
khác nhau. Không thêm log chứa header Authorization hoặc toàn bộ payload.

Ngày 28/10/2026, sếp yêu cầu chốt ca 4–8 với mức bằng chứng nêu trong bảng.
Đây là nghiệm thu được người dùng chấp nhận, không phải tuyên bố đã thu log từng
endpoint trên iPhone. Ca 9 chấp nhận phục hồi bằng phiên mới; tự trở về chế độ
giả lập sau khởi động lại là hạn chế UX còn giữ, chưa sửa trong bản này.

### Log API bổ sung do sếp cung cấp — 28/10/2026

- Hai phiên `ses_f006d902cf8ee863` và `ses_d3d3cb80a44d4e2c` đều có chuỗi
  `/media → /signals → /finalize → /voice`, mỗi endpoint xuất hiện một lần,
  đều HTTP 200 trong đoạn log được cung cấp. Không thấy request lặp trong đoạn đó.
- Phiên `ses_d3d3cb80a44d4e2c` có hai request `/challenge` HTTP 200 trước media.
  Phù hợp với lấy lại challenge, nhưng access log không chứa response nên không
  tự chứng minh challenge ID/token đã đổi.
- Các detector trong log dùng `mock@0.1`. HTTP 200 không tự chứng minh kết quả
  cuối là pass/review; dòng cleanup `deleted: []` không chứng minh client dọn file.
- Bằng chứng chốt ca 4–7: nghiệm thu mất mạng thủ công của sếp + log nhận đủ
  endpoint + test retry/ack xanh. Không có mốc tắt/bật Wi-Fi, response body hay
  đối chiếu payload, nên không ghi đã kiểm mất mạng riêng từng endpoint trên
  iPhone. Request không tới server cũng có thể không xuất hiện trong access log.

Chỉ lưu bản tóm tắt này; không đưa toàn bộ log, token hay media vào Git.

## Kiểm challenge và ack

- Khi bỏ lượt vì gián đoạn/Back: phải có `/challenge` mới trước upload kế tiếp;
  token được thay theo response, ID/challenge và media cũ không dùng lại.
- Sau retry chất lượng server cấp challenge mới: dùng gói đó như trước. Chỉ khi
  người dùng bỏ lượt đó mới buộc refresh; không refresh thừa trong retry mạng.
- Chỉ media/signals 409 step_already_received được coi là ack. Voice/finalize 409
  không là success. Nếu server đã xử lý nhưng response mất, có thể phải kết thúc
  phiên theo lỗi contract; không suy diễn pass khi thiếu phản hồi kết quả.
- Phản hồi đến muộn sau khi bỏ lượt không được bật camera, set ack, điều hướng
  success hoặc xóa file của lượt mới.

## Kiểm file và trạng thái hệ thống

1. Sau hủy/gián đoạn, chọn Dừng xác minh về ngân hàng. Mở Xem tất cả màn →
   **Kiểm tra file tạm · IOS-06**. Số file thu còn trong app phải về 0 sau teardown.
   Nút chỉ đếm, không xóa. Không mở checkpoint camera rồi đếm như trạng thái idle.
2. Sau server nhận media/voice, file MP4 tương ứng bị xóa; retry signals/finalize
   vẫn được vì ack và payload cần thiết còn trong RAM. Khi media chưa ack, file
   hoàn tất có thể còn để phục vụ retry; không xóa nó bằng thao tác ngoài app.
3. WAV được đóng thành Data trong RAM, không có WAV file handle chờ đóng.
4. File iPhone nằm trong sandbox app tmp/vericlue-capture; không phải tmp/media
   của server Mac. File trên server vẫn được giữ theo chính sách backend hiện có.
5. Nếu kill app lúc quay, orphan thuộc namespace app được dọn lần mở sau. App
   không lưu token để tự resume sau kill: bắt đầu lại từ bank, không giả khôi phục
   phiên. Thu hồi quyền trong Settings có thể làm iOS kết thúc process; kiểm cả
   đường mở lại này thay vì bắt buộc luôn có màn face_ready sau process đã chết.
6. Không xóa WAV/MP4 của app khác hoặc file đã xuất sang Files/Photos/Downloads.

## Trước khi chốt

- [ ] Mười ca có kết quả/người thử/model/iOS và bằng chứng đúng bước.
- [x] Test tự động mới nhất xanh: sau sửa Gallery/path binding, `/tmp/vericlue-ios06-navigationfix-20261028.xcresult` **105/105 Passed, 0 lỗi/0 bỏ qua**, 122 lượt tính tham số, gồm Gallery. Simulator iPhone 17 Pro iOS 26.3.1, 28/10/2026. Hai lượt lỗi 104/105 trước đó giữ trong bàn giao; không tăng timeout/bỏ assertion. Bằng chứng này không thay nghiệm thu phần cứng iPhone.
- [ ] File count/cleanup, trạng thái độ sáng và idle timer được xác nhận trên máy.
- [ ] Diff được review, bàn giao được điền; không có media/token trong staged.
- [ ] PR được duyệt/merge mới ghi done.
