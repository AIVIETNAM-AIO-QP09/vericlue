# ADR-0018: Chứng nhận riêng tư BBS — thử nghiệm độc lập trước tích hợp

- **Trạng thái:** đã chấp nhận cho bản thử nghiệm; thay ADR-0016 mục 5 ở lựa chọn mật mã.
- **Ngày:** 2026-10-27
- **Người quyết định:** trưởng nhóm đồng ý triển khai hướng BBS trong hội thoại.
- **Task:** LIVE-05.

## Bối cảnh

Người dùng muốn tính năng nâng cao có giá trị bảo mật và demo được: chứng minh
thuộc tính đã được VeriClue ký mà không đưa toàn bộ hồ sơ tới mỗi dịch vụ.
ADR-0016 mục 5 chọn zk-STARK/ML-DSA, nhưng người dùng vừa chọn nghiên cứu BBS,
holder binding và bí danh theo dịch vụ, với SD-JWT+KB làm đối chứng.

## Quyết định

1. Dùng BBS pseudonym/blind issuance của `@digitalbazaar/bbs-signatures` 3.1.0
   (BSD-3-Clause), khóa package-lock. API nâng cao chưa có public export: adapter
   dùng đúng file trong package đã cài, không chép/viết lại primitive mật mã.
   Test vector công khai upstream kiểm tương thích; pin này là điều kiện sử dụng.
2. Thêm `services/credentials`, chỉ chạy CLI/library độc lập với persona tổng
   hợp. Mọi claim và header bắt buộc `synthetic-demo`; không có endpoint cấp từ
   request công dân, không dùng key report/result thật, không mở chốt sinh trắc.
3. Holder cam kết một secret 32 byte và prover nym. Issuer chỉ nhận commitment
   có proof, ký các thuộc tính do chính issuer dựng. Secret/blind không tới issuer.
   Holder kiểm chữ ký trước khi tạo proof. Nym được ràng buộc bằng cùng BBS proof.
4. Verifier pin khóa issuer; tự cấp nonce, origin HTTPS, policy và hạn. Proof
   ràng buộc toàn ngữ cảnh. Dùng lượt một lần, kiểm thời hạn trước/sau crypto;
   khóa lượt trước await chống tranh chấp trong một process. State RAM có giới hạn.
5. Thuộc tính thời gian chung theo cohort để tránh thời điểm cấp quá chi tiết.
   `age_over_18` là boolean issuer tính và ký, không phải range proof trên DOB ẩn.
6. Profile mã hóa mảng claim riêng; không nhận là W3C VC/BBS JSON-LD hoàn chỉnh,
   OpenID4VP, FIDO hoặc giao thức đã được kiểm toán. SD-JWT+KB dùng flat disclosure,
   JWS Ed25519, nonce/audience/sd_hash; JWT+PoP là baseline profile riêng.
7. PQC độc lập với bản thử này, bỏ phụ thuộc LIVE-04 của LIVE-05. BBS không kháng
   lượng tử; thêm chữ ký ML-DSA bên ngoài không làm BBS proof kháng lượng tử.

## Phương án đã cân nhắc

- SD-JWT+KB: dễ tích hợp hơn nhưng issuer token lặp lại vẫn cho phép liên kết.
- zk-STARK tổng quát: giữ như hướng nghiên cứu sau, chưa cần circuit/range proof.
- Passkey: bảo vệ đăng nhập/ví là bước riêng; không gọi secret RAM là khóa phần cứng.

## Hệ quả

Demo cho thấy tiết lộ tối thiểu, holder binding và khác biệt bí danh giữa dịch vụ.
Nonce RAM chưa hỗ trợ nhiều worker; chưa có thu hồi từng credential, backup/ví,
phần cứng hoặc API cấp từ quyết định eKYC thật. Chứng minh đúng chữ ký không chứng
minh AI đúng, nguồn camera thật, người đang hiện diện hay danh tính pháp lý.
LIVE-05 giữ doing cho tới tích hợp và nghiệm thu; không lấy benchmark mật mã làm R1–R7.

## Bổ sung 27/10 — cổng cấp từ backend sau PR #96

Theo yêu cầu tiếp tục sau khi merge #96, thêm profile `server-decision` riêng và
API opt-in tái dùng nguyên cổng SignedResultService, chỉ reauth/recovery pass.
Khóa thiết bị hiện hành ký chấp thuận commitment/source/key/hạn; bearer đơn lẻ
không cấp được cho holder khác. Worker BBS và key tách khỏi khóa Ed25519 hiện có.
Cache mã hóa, unique session, retry idempotent, hạn không vượt kết quả nguồn.
Không thêm tuổi, không mở chốt sinh trắc thật hoặc nhận verdict client. Chi tiết:
[cấp chứng nhận](../architecture/private-credential-issuance.md).

## Bổ sung 27/10 — verifier HTTP sau PR #97

Tiếp tục tích hợp LIVE-05: HTTP verifier lưu challenge trong DB, lấy origin từ
credential tích hợp riêng, khóa hàng qua lúc kiểm BBS và commit tiêu thụ trước
response. Crypto stateless dùng chung với SDK; verifier chỉ cần public pin,
không cần khóa bí mật issuer. Không đổi header/profile, không nhận nonce/key/
policy từ người gửi proof. Không thêm tuổi, thu hồi hoặc mở chốt sinh trắc thật.
Giới hạn vận hành và giao thức: [verifier API](../architecture/private-credential-verifier.md).

## Bổ sung 27/10 — vòng đời issuer key sau PR #99

Thêm registry public pin trong DB, bật riêng trên issuer/verifier. Operator CLI
đăng ký staged, activate (nghỉ key cũ tối đa 60 giây) và revoke không hồi sinh.
Khóa hàng chia sẻ qua lúc cấp/kiểm phối hợp với khóa operator; key ID chỉ chọn
pin đã tin, không nhận public key hoặc claim client. Không đổi header/proof BBS,
không thêm status ID cá nhân. Đây là thu hồi theo key, không thu hồi riêng từng
credential. Chi tiết: [vòng đời khóa](../architecture/private-credential-keys.md).

## Nguồn

- [W3C BBS, bản 10/09/2026](https://www.w3.org/TR/2026/CRD-vc-di-bbs-20260910/).
- [Upstream pin tham chiếu](https://github.com/digitalbazaar/bbs-signatures/tree/1d4c17315a5d2e11c0f3f97e07dbdaf398fa3ebc).
- [RFC 9901](https://www.rfc-editor.org/rfc/rfc9901.html).
