# Nghiệm thu chống phát lại media — PLAT-06 / SEC-02

## Kiểm tra tự động

Từ gốc repo, chạy cùng dependency và migration test của dự án:

```powershell
uv run pytest services/api/tests/test_media_proof.py -o addopts= -q
```

Khóa P-256 sinh trong RAM, file tổng hợp; không dùng người thật, không đo độ
chính xác mô hình. Các bài kiểm tra đi qua API, transaction và storage thật,
detector là mock. Không gọi ngân hàng hoặc hệ thống bên ngoài.

- Đủ tám tên scenario mock: genuine, low_quality, print, replay, virtual_cam,
  faceswap, voice_clone, error. Mỗi lần đổi lượt ký theo context mới; nonce cũ
  được giữ, phiên đóng không nhận thêm bước hoặc ghi quyết định lặp.
- Sai byte/khóa/phiên/suffix/offset hoặc thiếu proof: không nhận upload.
- Proof cũ sau retry/refresh/đọc lại câu, kể cả đổi nhãn ID hiện hành: từ chối.
- Hết hạn đúng ranh giới trước hoặc trong lúc đọc file: không ghi thêm media,
  không claim nonce. Không sleep 120 giây trong test.
- Gửi trùng sau restart: từ chối, không ghi đè bản đã nhận.
- Lỗi storage sau kiểm chữ ký: rollback nonce; cùng proof gửi lại được khi
  request trước thất bại và thử thách vẫn còn hạn.

CI có PostgreSQL service, kiểm rollback và hai transaction tranh một nonce:

```powershell
uv run pytest services/api/tests/test_db_postgres.py -k 'signed_media_claim or media_nonce_unique' -o addopts= -q
```

Chỉ chạy khi TEST_DATABASE_URL trỏ **DB test riêng** theo README API. Không đặt
URL production. Thiếu biến thì skip; skip không phải bằng chứng PostgreSQL đạt.

## Phần cần thiết bị thật

Chưa đánh dấu PLAT-06/SEC-02 hoàn tất chỉ bằng các test trên. Trên API demo riêng
đã migration, Android bật `-Pvericlue.signedMedia=true`, server bật
REQUIRE_MEDIA_PROOF=true. Xem `media-proof.md` và README Android để cấu hình kết nối.
Không mở chốt sinh trắc real/mixed để ép kịch bản chạy qua.

1. Bắt đầu phiên có public key, quay bản ghi và tải lên. Xác nhận client thực sự
   dùng Android Keystore, gửi đúng challenge ID và nhận acknowledgment.
2. Ngắt kết nối sau khi server nhận upload nhưng trước khi client nhận response;
   gửi lại phải bị coi là bước đã nhận, không chạy lại detector hoặc ghi đè file.
3. Làm mới/làm lại lượt; gửi proof của lượt cũ phải bị từ chối. Ghi nhận kết quả
   và thời điểm mà không chép token, private key, media hoặc định danh vào Git.
4. Thử hết hạn mặt/giọng và khởi động lại API trong môi trường demo. Ghi commit,
   phiên bản app/OS, chế độ model, cấu hình proof và kết quả từng tình huống.

Keystore/hardware-backed key, camera thật, thời gian tải và kết quả mô hình phải
có bằng chứng chạy riêng. Laptop dùng để kiểm API/crypto và camera lab; không
thay thế bằng chứng Android Keystore.

## Cách hiểu kết quả

Đường unsigned cũ vẫn tương thích khi REQUIRE_MEDIA_PROOF=false và phiên không
gửi khóa. Không tuyên bố đường này kiểm được tuổi của byte media. Người giữ khóa
cũng có thể ký lại byte cũ theo thử thách mới: chữ ký không chứng thực thời điểm
quay/camera. Phản hồi thử thách, PAD/GenD và kiểm môi trường là các tín hiệu riêng.

Lỗi DB làm rollback transaction; file đã ghi trước một lỗi phát sinh muộn có thể
vẫn nằm trong kho cho tới cleanup TTL. Không tuyên bố rollback DB đồng nghĩa với
xóa an toàn mọi byte trên đĩa. Không dùng các test này làm số liệu chống deepfake.
