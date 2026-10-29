# Nghiệm thu receipt và Keychain trên iPhone — chặng 1

## 1. Đã chuẩn bị và giới hạn

- Nền iOS: nhánh `feat/IOS-02-android-alignment`, chưa commit.
- Backend riêng: `tmp/receipt-backend`, detached tại `f034fa9406ea9aef1ee86365ce82142de517d553`.
- Venv/DB/media riêng; không dùng `tmp/dev.db`, không đổi backend cổng 8000.
- API kiểm tương thích: `http://192.168.1.12:8001/` (IP đo lúc chuẩn bị, kiểm lại nếu đổi Wi-Fi).
- Script local ignored: `bash /Users/mac/Desktop/project/vericlue/tmp/run-receipt-backend.sh`.
- Log: `tmp/receipt-backend/tmp/receipt-check.log`. Script/log/DB/media không commit.
- Mock thuần, `ACCOUNT_ENROLLMENT=false`, `REQUIRE_MEDIA_PROOF=false`,
  `SESSION_PRIVACY=false`, quota tạo phiên 50/giờ cho kiểm local. Đây không phải
  cấu hình nghiệm thu ghi danh hoặc bảo mật thật. Chỉ dùng mạng riêng, không mở tunnel/public.
- SQLite phục vụ kiểm tương thích local, không chứng minh hành vi PostgreSQL/concurrency.

**Đính chính điều kiện tích hợp:** backend đúng phiên bản là cần nhưng chưa đủ.
Code `accounts.py` từ chối mock/mixed tạo account. Ghi danh thật còn cần mô hình/
calibration, danh tính, mã hóa và khóa thiết bị. Không bật enrollment để ép mock
phát receipt; không sửa DB tạo tài khoản mẫu, không bỏ device proof.

## 2. Kiểm backend và nối iPhone

1. Mac và iPhone cùng Wi-Fi. Terminal Mac:

   ```bash
   curl http://127.0.0.1:8001/healthz
   ```

   Nếu có JSON thì backend đang chạy, không chạy thêm bản trùng cổng. Nếu báo
   không kết nối được, mở Terminal riêng rồi chạy script ở mục 1; giữ cửa sổ đó.
2. Trên Safari iPhone mở `http://192.168.1.12:8001/healthz`. Phải nhận JSON.
   Nếu không được, kiểm IP bằng `ipconfig getifaddr en0` trên Mac, Wi-Fi/firewall.
   Không coi Safari truy cập được là app đã lưu receipt.
3. Trong Xcode mở project iOS chính, không mở project trong worktree backend.
   Sửa tạm `apps/ios/Config/Debug.xcconfig` sang:

   ```ini
   API_BASE_URL = http:/$()/192.168.1.12:8001/
   ```

   Giữ cú pháp `$()`; thay IP nếu bước 2 đo được IP khác. Không sửa Release.
4. Chọn scheme VeriClue, Run Destination là iPhone 14 Pro ở thanh trên cùng.
   Product → Scheme → Edit Scheme → Run → Info → Build Configuration: Debug.
   Nhấn Run, cho phép Local Network khi iOS hỏi. Phải build lại sau khi đổi xcconfig.

## 3. Keychain thật, dữ liệu kiểm tra riêng

Không cần Internet/backend cho nhóm này. App phải chạy trên iPhone, không phải
Simulator. Từ ngân hàng → Xem tất cả màn → **Keychain receipt · Kiểm tra DEBUG**.

1. Bấm **1. Ghi dữ liệu kiểm tra** → thấy đã ghi. Dữ liệu tổng hợp, hạn 24 giờ.
2. Vuốt Home, mở danh sách app gần đây, vuốt VeriClue lên để đóng hẳn. Không gỡ app.
3. Mở lại VeriClue từ biểu tượng, vào lại Xem tất cả màn, bấm **2. Đọc lại sau khi mở app**.
   Phải thấy `ĐẠT: đọc đúng dữ liệu kiểm tra còn hạn từ Keychain`.
4. Khóa/mở khóa iPhone rồi bấm 2 lần nữa: đọc được sau khi đã mở khóa. Mục này
   không chứng minh Keychain trả lỗi trong lúc khóa; app không chạy probe khi khóa.
5. Bấm **3. Xóa item kiểm tra** → thấy đã xóa/đọc trả rỗng. Bấm 2 → kho kiểm tra rỗng.
6. Bấm **4. Kiểm dữ liệu hỏng / hết hạn** → phải thấy ĐẠT. Phần hết hạn dùng mốc
   thời gian truyền vào `load(at:)`, không yêu cầu đổi đồng hồ iPhone hoặc chờ 24 giờ.
7. Bấm **Đọc kho receipt của luồng thật** → với mock/kho mới phải báo rỗng.
   Nếu đã có receipt từ lần trước, nút chỉ cho biết có dữ liệu còn hạn, không xác
   nhận nguồn gốc hay đăng nhập. Không in account ID/device ID/token.

Probe dùng cùng AccountStore và Security backend với service riêng
`vn.vericlue.debug.receipt-check`; không ghi/xóa item của luồng thật. Dữ liệu kiểm
tra không trở thành receipt phiên. Màn này chỉ có trong `#if DEBUG`.

## 4. App pass nhưng không có receipt

1. Gallery: chọn Đăng ký, nguồn API thật, scenario genuine. Ra màn ngân hàng rồi
   bắt đầu đăng ký bình thường, không dùng mở độc lập màn Success trong Gallery.
2. Hoàn tất OTP/CCCD/mặt theo luồng hiện có, dùng dữ liệu thử, không đưa ảnh CCCD
   hoặc bản ghi lên Git. Server quyết định có yêu cầu đọc câu hay không.
3. Tới thành công thì dừng vài giây trước khi rời màn, để GET account hoàn tất.
4. Trên Terminal Mac khác:

   ```bash
   tail -f /Users/mac/Desktop/project/vericlue/tmp/receipt-backend/tmp/receipt-check.log
   ```

   Cần thấy `GET /v1/sessions/.../account ... 409`. Backend mock không tạo account,
   nên đây là lỗi lấy metadata dự kiến, không phải receipt đã cấp thành công.
5. App phải giữ kết quả xác minh pass, không tự quay lại thu mặt/giọng. Vào lại
   Gallery đọc kho receipt thật: vẫn rỗng nếu trước đó chưa có receipt thật.
6. Khôi phục Debug.xcconfig về cổng 8000 khi quay lại backend cũ; build lại app.
   Không commit việc đổi IP/cổng chỉ để nghiệm thu nếu không chủ đích giữ cấu hình đó.

Lỗi mạng metadata và storage retry đã có unit test; không ghi rằng đã thử trên
iPhone nếu chưa chủ động tái hiện được. Không tắt mạng trước finalize rồi gọi đó
là lỗi GET receipt. Gửi lại GET không được gửi lại finalize/voice.

## 5. Ghi kết quả và phần còn chặn

```text
iPhone / iOS:
Build iOS (commit + dirty):
Backend: f034fa9, mock, cổng 8001
Keychain ghi → đóng/mở → đọc:
Keychain xóa → đọc rỗng:
Keychain dữ liệu hỏng/hết hạn (mốc giờ truyền vào):
GET account trả 409 sau pass; app vẫn giữ pass:
Kho thật không được điền bằng dữ liệu probe:
```

Chỉ đánh dấu đạt cho mục đã quan sát. Chưa đánh dấu **GET 200 receipt thật → lưu
Keychain → đóng/mở đọc lại**: cần nhóm cung cấp phiên/account đủ điều kiện từ
backend thật và hỗ trợ khóa thiết bị. Không suy từ probe/MockURLProtocol thành
ghi danh thật, không ghi “đăng nhập lại thật đã xong”.

## 6. Kết quả người nghiệm thu xác nhận — 28/10/2026

Nguồn bằng chứng: sếp thao tác trên iPhone và xác nhận trong chat; agent không
trực tiếp quan sát màn hình. Model iPhone 14 Pro đã được xác định khi chuẩn bị;
chưa ghi nhận lại phiên bản iOS/build cài trên máy cho lượt này.

- [x] Keychain item kiểm tra: ghi → đóng hẳn/mở lại app → đọc đúng dữ liệu.
- [x] Xóa item kiểm tra → đọc rỗng.
- [x] Probe dữ liệu hỏng/hết hạn báo ĐẠT (expiry dùng mốc giờ truyền vào).
- [x] Sếp xác nhận app hiện thành công, sau GET account 409 vẫn giữ kết quả,
  không tự quay lại thu mặt/giọng.
- [ ] GET 200 receipt thật → lưu kho live → đóng/mở đọc lại: chưa kiểm chứng.

Log sếp cung cấp của phiên `ses_5b4ab2550e286be1`: media/signals/finalize HTTP
200, tiếp theo GET account HTTP 409. HTTP 200 riêng lẻ không chứng minh status
pass; bằng chứng giữ kết quả thành công đến từ xác nhận thao tác của sếp.
Không dùng kết quả này để tuyên bố ghi danh/đăng nhập lại thật đã xong.

Kiểm tra bổ sung chỉ đọc sau xác nhận: backend cổng 8001 health `mock_models=true`;
DB riêng có 1 phiên pass nhưng 0 hàng trong bảng accounts. `receipt_for_session`
đòi account thực sự tồn tại, còn `_validate_biometrics` loại mock/mixed. Vì vậy
không có phiên đủ điều kiện cho GET 200 trên môi trường này. Cần nhóm backend
cung cấp môi trường ghi danh thật đã cấu hình và phiên đủ điều kiện; không seed
account mẫu, không đổi DB/status hoặc hạ chốt để chứng minh thành công.

Kiểm tra sẵn sàng bổ sung: venv backend riêng không có torch/onnxruntime/cv2;
chưa cấu hình identity lab/calibration/master key và các opt-in thật đang tắt.
DB không có media_proof_uses/device_proof_uses. iOS chưa gửi public key trong
CreateSessionRequest. Vì ghi danh yêu cầu chữ ký media đã xác minh với key P-256,
chỉ bật enrollment không đủ. Phần ký media/khóa thiết bị và pipeline mô hình thật
cần công việc riêng, không thuộc nối receipt đơn thuần.
