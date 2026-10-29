# Checkpoint chặng 2–3: luồng đầu và camera CCCD

## Phạm vi bản này

**Cập nhật chặng 4:** các đoạn mô tả checkpoint dừng dưới đây là lịch sử của
bản chặng 3. Sếp đã xác nhận 4 ca camera/QR/retake/Home đạt. Bản code hiện tại
đã bỏ màn dừng và nối confirm sau quay; nghiệm thu tiếp theo dùng
[checklist chặng 4](post-face-confirm-device-checklist.md), chưa coi đã đạt.

Đã đổi màn đầu/OTP/quyền và camera sau/review hai mặt. Chưa đổi pipeline quay mặt,
chưa nối confirm sau quay và chưa đổi theme. Bản này **cố ý dừng onboarding sau
`/id-card`** tại “Đã nhận ảnh CCCD”, trước quay mặt, để thử camera theo kế hoạch.
Không đánh dấu toàn bộ luồng mới hoàn tất và không dùng bản trung gian này thay
bản demo end-to-end. Chặng 4 chỉ bắt đầu sau xác nhận checkpoint iPhone.

Terms/consent lấy phân loại từ Android `f034fa9`: xử lý mặt/giọng bắt buộc,
lưu mẫu mặt và lưu CCCD tùy chọn. Sếp đã đồng ý giữ nhãn demo vì nguồn vẫn chờ
nhóm/pháp chế chốt. Không coi đây là nội dung pháp lý được duyệt; lựa chọn hiện
chỉ trong UI, chưa phải bản ghi consent có audit trên server. Đã bỏ lời hứa rút
đồng ý qua một màn Settings chưa tồn tại; không tự thêm cơ chế/chính sách mới.

## Chuẩn bị

1. Mac/iPhone cùng Wi-Fi; giữ backend kiểm tương thích cổng 8001 đã chuẩn bị.
   Mở `http://192.168.1.12:8001/healthz` trên Safari iPhone, phải nhận JSON.
2. Project iOS chính, scheme VeriClue, Debug, đích iPhone 14 Pro → Run.
   Debug.xcconfig hiện sếp đã chọn cổng 8001; không sửa Release/project.pbxproj.
3. Gallery chọn Đăng ký, API thật, genuine; về ngân hàng rồi bắt đầu luồng.
   Không dùng Gallery mở độc lập màn Review để thay cho nghiệm thu ảnh thật.
4. Dùng thẻ thử/QR tổng hợp phù hợp, không commit ảnh/QR/số định danh thật.

## A. Màn đầu và OTP

- [ ] Đăng ký → một màn Điều khoản và đồng ý; không có ô nào chọn sẵn.
- [ ] Chưa xác nhận đọc cuối + đồng ý điều khoản + mục xử lý bắt buộc thì nút
  tiếp tục khóa. Hai mục tùy chọn bỏ trống vẫn đi được sau khi đủ điều kiện bắt buộc.
- [ ] Tiếp tục tới số điện thoại, không chen Consent/Intro/Permission cũ.
- [ ] Chưa hỏi quyền camera/micro ở bước điện thoại/OTP.
- [ ] SMS mô phỏng có một mã hợp lệ thì điền sáu ô; không tự gọi verify hoặc tự
  chuyển màn. Xóa/sửa mã bằng keypad được; mã không rõ/không đủ/không ASCII không điền.
- [ ] Nhập sai một lần, sửa rồi xác nhận đúng; attempts lấy từ server.
- [ ] Sai hai lần còn 3 → chờ 45s gửi lại → vẫn còn 3, không về 5. Sai thêm ba
  lần thì khóa verify và resend, có nút bắt đầu lại. Cần backend có bản sửa ngân
  sách OTP; cổng 8001 đã được cập nhật, cổng 8000 cũ không tự reload.
- [ ] Sau xác nhận đúng, Back về OTP → hiện trạng thái đã xác nhận/khóa nhập mã,
  chỉ có Tiếp tục; không giả như đang verify một mã khác. Test mã sai trước lần
  đúng hoặc bắt đầu phiên mới. Tự điền từ SMS không tự xác nhận.
- [ ] Gửi nhanh hai lần không trùng phiên/request; resend đúng 45 giây kể cả ra Home;
  Back về điện thoại cùng số không gửi thêm trong cooldown và không ghi đè mã đã sửa.
- [ ] Recovery sau OTP → face_ready, không CCCD/confirm. Đây vẫn là luồng demo/mock
  của phiên, không phải đã hoàn thành khôi phục tài khoản thật/device proof.

## B. Camera sau và tự chụp

- [ ] Camera xin quyền khi mở bước CCCD; micro chưa bị hỏi.
- [ ] Từ chối camera → báo đúng, có Mở Cài đặt/Thử lại, không chụp/chuyển tiếp.
- [ ] Chỉ đưa nền phòng/chữ không liên quan vào khung: không tự chụp chỉ vì ảnh nét.
- [ ] Thẻ rõ, không lóa, có chữ thẻ: sau delay đầu 1,5 giây, hai mẫu đạt liên tiếp
  cách tối thiểu 500ms mới đề nghị tự chụp. Mẫu lỗi reset chuỗi; gián đoạn dài reset.
  Đây là thông số cấu hình tham chiếu Android, không phải số đo tốc độ iPhone.
- [ ] Cùng lúc máy sắp auto, bấm nút chụp tay nhanh: chỉ một ảnh/một lần chuyển màn.
- [ ] Ảnh vừa chụp giữ khoảng 1,5 giây và có Chụp lại; ảnh lỗi vẫn giữ để retake,
  không tự chuyển tiếp. Không bắt QR ở mặt sau; kiểm QR chung sau khi đủ hai ảnh.
- [ ] Preview/ảnh lưu đúng chiều, vùng thẻ không lệch hoặc crop mất cạnh bất thường.
- [ ] Home/Back khi đang phân tích/chụp/giữ ảnh: không có callback trễ tự chuyển màn.
  Quay lại ảnh đang giữ thì phải bấm Tiếp tục, không tự chạy tiếp từ tác vụ cũ.

Lỗi Home sếp báo đã được quan sát trực tiếp trong Xcode: NSInvalidArgumentException
do setVideoMirrored khi automaticallyAdjustsVideoMirroring=YES ở preview. Bản sửa
tắt auto-mirroring trước khi đặt mirror tại preview/photo/video output. Cần cài
lại bản mới và nghiệm thu lại; không coi đã hết crash chỉ vì build xanh.

OCR chữ dùng Vision tiếng Anh cho chữ in song ngữ trên thẻ; nếu OCR lỗi thì không
tự chụp, vẫn có nút tay. QR hợp định dạng là một tín hiệu nội dung thẻ, không phải
bằng chứng thẻ thật. Không dùng OCR local để thay fields server hoặc xác thực CCCD.
Chất lượng ảnh cuối vẫn đo lại sau chụp, không tin kết quả mẫu preview trước đó.

## C. Review chung và gửi

- [ ] Chụp trước → chụp sau → một màn có đủ hai ảnh, không còn hai route review cũ.
- [ ] Retake mặt trước giữ mặt sau; camera thực sự mở lượt mới, không hiện ảnh cũ
  từ NavigationStack. Retake mặt sau giữ mặt trước. Không bị vòng lặp chuyển màn.
- [ ] QR chỉ ở mặt trước → mặt sau vẫn chụp tiếp, gửi QR mặt trước cùng hai ảnh.
- [ ] QR chỉ ở mặt sau → gửi được; nếu cả hai mặt có QR hợp định dạng thì ưu tiên
  mặt sau theo Android, nếu mặt sau sai định dạng thì dùng QR mặt trước hợp lệ.
- [ ] Cả hai ảnh không có QR hợp định dạng → ở review, chưa gọi API. QR_INVALID
  từ server → giữ cả hai ảnh tại review, chọn retake mặt có QR; giữ mặt còn lại.
  Không gửi lại cùng bộ ảnh bị từ chối cho tới khi đã chụp lại một mặt.
- [ ] Thiếu/mờ/lóa → không gửi; hai ảnh hợp lệ mới gọi `/id-card`.
- [ ] Mất mạng lúc gửi → ở lại review, giữ cả hai ảnh; thử lại sau khi có mạng.
- [ ] Server nhận đủ hai ảnh; response fields/draft giữ trong IdentityFlow.
- [ ] Thành công → “Đã nhận ảnh CCCD”; chưa gọi `/id-card/confirm`, media hoặc finalize.
- [ ] Xem lại hai mặt mà không đổi ảnh → không upload lại. Retake sẽ vô hiệu hóa
  fields/draft cũ và lấy lại từ server khi gửi ảnh mới.

## Gửi kết quả để mở chặng 4

```text
iPhone / iOS:
Build: HEAD + dirty (chưa commit)
API/scenario: 192.168.1.12:8001 / genuine
A. Màn đầu, OTP, recovery bỏ CCCD:
B. Auto/manual, giữ ảnh, crop, Home/Back:
C. Review hai mặt, retake, QR, gửi:
Lỗi và bước tái hiện (nếu có):
```

Không dùng kết quả test/thiết bị cũ để đánh dấu các ô trên. Test chặng mới chỉ
được compile trong build-for-testing, chưa chạy theo quy ước sếp. Sau checkpoint
mới triển khai giữ MP4/evidence chờ confirm; không nối tạm đường upload thiếu confirm.
