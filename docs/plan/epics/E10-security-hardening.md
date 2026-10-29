# E10 — Khắc phục sau rà soát bảo mật 28/10

Phạm vi được người dùng giao ngày 28/10: triển khai phương án xử lý các phát hiện
AUD-01…14, chia subagent và kiểm chứng trên dữ liệu tổng hợp. Không mở guard sinh
trắc, không sửa ngưỡng AI, không tự nhập/xóa dữ liệu đang triển khai. Không sửa UI
đang do nhóm app phụ trách. Chỉ trưởng nhóm cập nhật STATUS.md.

Sau merge PR #105 (`54acaad`), SEC-03/04/05/06/08 hoàn tất tiêu chí code trong
task card; CI nguồn `228be37` đạt 8 checks, Python/PostgreSQL 4448 passed,
61 skipped. `done` của các task này không bao gồm nghiệm thu app/OTP thật,
triển khai/backup hoặc bản vá web còn ở SEC-07.

### SEC-03 · Kiểm quyền trước parser và giới hạn multipart

| Người | Ước lượng | Sprint | Ưu tiên | Phụ thuộc |
|---|---|---|---|---|
| M2 | 0,5 | S2 | P0 | PLAT-05 |

AUD-03/AUD-12: token sai/phiên hết hạn phải bị chặn trước khi parse/spool. Dùng
kiểm quyền chung, giao dịch ngắn trước upload; kiểm lại trong nghiệp vụ. Không
giữ row lock qua lúc client gửi body. Giới hạn file/field/byte theo endpoint,
không hiểu nhầm max_part_size là trần file.

- [x] Token sai, token cũ, Authorization trùng không gọi parser.
- [x] Upload hợp lệ chạy, hết hạn/thu hồi trong upload không được chấp nhận.
- [x] File/field trùng hoặc ngoài allowlist và trần file bị chặn trong parser.
- [x] Có test, tài liệu và bàn giao; không đổi hợp đồng bên ngoài.

### SEC-04 · Chuẩn hóa ảnh và vòng đời rescan

| Người | Ước lượng | Sprint | Ưu tiên | Phụ thuộc |
|---|---|---|---|---|
| M2 | 0,5 | S2 | P0 | PLAT-05 |

AUD-01/AUD-02: xác thực byte gốc trước sanitation với media ký; ảnh dựa vào nội
dung, không suffix. CCCD được kiểm trước OCR. Tên file do server cấp; rollback
không làm mất cặp cũ; dọn ảnh cũ sau commit và file mới sau rollback. Có trần
lượt/tổng dung lượng rescan, bền qua restart, không nới guard model.

- [x] JPEG đổi đuôi vẫn qua cùng kiểm tra và xóa EXIF; file giả bị chặn.
- [x] Bounds ảnh áp dụng trước OCR/ML, đúng thứ tự chữ ký và rollback nonce.
- [x] Rescan/ghi lỗi/commit lỗi/concurrency không mất cặp đã commit hoặc xóa nhầm.
- [x] Có trần tài nguyên cấu hình và kiểm thử; không commit ảnh thật.

### SEC-05 · Profile bảo mật và chặn cấu hình dev dùng nhầm

| Người | Ước lượng | Sprint | Ưu tiên | Phụ thuộc |
|---|---|---|---|---|
| M2 | 0,5 | S2 | P0 | PLAT-05 |

AUD-05/AUD-06/AUD-08: profile dữ liệu thật fail-closed khi thiếu privacy, ký media,
khóa hợp lệ hoặc dùng HMAC dev. OTP mô phỏng không chứng minh giữ số điện thoại;
luồng yêu cầu thật chưa có kênh thật phải đóng. Kiểm cấu hình toàn API/Compose;
không tự sinh/ghi đè khóa, không chạy npm audit BBS khi chưa có quyền egress.

- [x] Cấu hình an toàn được kiểm trước nhận dữ liệu; dev/mock tách rõ.
- [x] OTP real-mode không trả simulated_sms hoặc công nhận mã mô phỏng.
- [x] Cấu hình mẫu/runbook phù hợp; guard sinh trắc vẫn giữ.
- [x] Có kiểm thử âm/dương; không sửa UI, schema, ADR hoặc ngưỡng.

### SEC-06 · Khép kín retention và thao tác riêng tư

| Người | Ước lượng | Sprint | Ưu tiên | Phụ thuộc |
|---|---|---|---|---|
| M5 | 1 | S2 | P0 | PLAT-05 |

AUD-04/AUD-07/AUD-08/AUD-11: triển khai nền backend cho phạm vi eKYC không bàn
duyệt. Ca chưa xác minh có deadline hữu hạn (mặc định đề xuất 24h, cấu hình rõ),
không chuyển thành pass hoặc dựng quyết định nhân viên giả. Tách mode công cụ
future work. Consent/rút lại/xóa sớm phải khớp hợp đồng trước code nếu triển khai.
Không tự di chuyển hoặc xóa kho thật; giữ giới hạn thu hồi credential đã cấp.

- [x] Review mở được dọn theo profile eKYC mới; mode công cụ giữ nghiệp vụ riêng.
- [x] Không đọc/cấp kết quả từ dữ liệu hết hạn; polling không kéo dài retention.
- [x] Thao tác consent/rút lại, nếu thêm, có schema/type/API/test thống nhất.
- [x] Có bàn giao rõ những phần app/thiết bị/backup chưa nghiệm thu.

### SEC-07 · Vá dependency web và kiểm chứng tích hợp

| Người | Ước lượng | Sprint | Ưu tiên | Phụ thuộc |
|---|---|---|---|---|
| M2 | 0,5 | S2 | P0 | PLAT-02, PLAT-05 |

AUD-13/AUD-14: vá Next.js/eslint-config-next 16.4.3 theo advisory và release
đã đối chiếu, cập nhật lockfile không audit fix force. Tích hợp các bản sửa,
chạy kiểm tra phù hợp và ghi lại mức khắc phục theo từng AUD. Không gọi tất cả
advisory là đã khai thác được; giữ hạng mục chưa có bằng chứng ở trạng thái mở.

- [ ] Next/config/lockfile đồng bộ; unit/type/lint/build phù hợp đạt.
- [x] Các kịch bản AUD-01…06 được chạy lại trên bản tích hợp.
- [x] Python lint/contract/backlog và test liên quan đạt.
- [x] PR/bàn giao nêu rõ phạm vi, kiểm chứng và giới hạn còn lại.

Dependency web đang chờ quyền npm registry (auto-review đã chặn egress metadata
và tải package; chưa được người dùng chấp thuận). Không đổi manifest một mình khi
lockfile chưa thể cập nhật. Protected overlay đưa service web cũ vào profile
opt-in `legacy-web`; đây là giảm bề mặt triển khai, không phải vá Next.js.

### SEC-08 · Công cụ vòng đời khóa và file tạm cho demo

| Người | Ước lượng | Sprint | Ưu tiên | Phụ thuộc |
|---|---|---|---|---|
| M2 | 0,5 | S2 | P0 | PLAT-05 |

AUD-08/AUD-14: CLI operator có dry-run để kiểm/rewrap DEK phiên và tài khoản
bằng master mới; không giải mã media, tự sửa .env hoặc ghi đè khóa. Apply yêu
cầu xác nhận dịch vụ đã dừng, giao dịch nguyên tử, lỗi giữ nguyên DB. Kiểm temp
orphan chỉ trong thư mục được cấu hình; không xóa lease đang chạy. Không gọi
công cụ trên kho thật trong task này; chỉ dùng dữ liệu tổng hợp.

- [x] Dry-run không đổi DB/tệp, output không có bí mật hoặc PII.
- [x] Rewrap thành công đọc bằng khóa mới; sai khóa/lỗi DB rollback toàn bộ.
- [x] Runbook nêu việc cập nhật cấu hình, backup/restore, ACL và ranh giới xóa.
- [x] Có test và bàn giao, không sửa UI/schema/ngưỡng.

### SEC-09 · Nối consent lưu mẫu và logic riêng tư vào app [contract]

| Người | Ước lượng | Sprint | Ưu tiên | Phụ thuộc |
|---|---|---|---|---|
| M5 | 1 | S2 | P0 | SEC-06, FLOW-06 |

**Mục tiêu:** triển khai bước tiếp theo sau khi nhóm thống nhất workflow FLOW-06.
D1 đã chọn: đăng ký tài khoản cần lựa chọn chủ động cho lưu mẫu mã hóa; từ chối
thì dừng tạo tài khoản. Không thêm chế độ xác minh một lần trong đợt này.

**Phạm vi hợp đồng được giao:** bổ sung biên nhận/mục đích lưu mẫu và điều kiện
ghi danh phù hợp vào `packages/contracts/` trước code, đồng bộ API/type/SDK và
client Android; iOS nhận cùng hợp đồng khi các nhánh được tích hợp. Phân biệt
quyền xử lý trong phiên với dữ liệu tài khoản và phạm vi rút lại/xóa, không tự
coi category hiện có là đã bao gồm lưu mẫu dài hạn. Không mở guard sinh trắc.

- [ ] Server chỉ ghi danh khi có lựa chọn lưu mẫu đúng phiên bản/phạm vi; không dùng cờ cấu hình thay biên nhận.
- [ ] Client có model/method privacy, lựa chọn theo phiên và logic ghi trước thu dữ liệu, refresh bearer, policy đổi và từ chối; không auto-grant.
- [ ] Rút lại dừng capture/upload mới, giữ trạng thái chưa xác nhận khi lỗi mạng và tôn trọng receipt/phạm vi xóa.
- [ ] Có test contract/server/client và checklist nối UI/máy thật; không lặng lẽ triển khai thay đổi điều hướng D2/D3 chưa thống nhất.

Điểm nối cụ thể và ca cần nghiệm thu:
[`mobile-privacy-integration.md`](../../architecture/mobile-privacy-integration.md).
