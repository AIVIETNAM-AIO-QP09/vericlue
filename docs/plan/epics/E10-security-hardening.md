# E10 — Khắc phục sau rà soát bảo mật 28/10

Phạm vi được người dùng giao ngày 28/10: triển khai phương án xử lý các phát hiện
AUD-01…14, chia subagent và kiểm chứng trên dữ liệu tổng hợp. Không mở guard sinh
trắc, không sửa ngưỡng AI, không tự nhập/xóa dữ liệu đang triển khai. Không sửa UI
đang do nhóm app phụ trách. Chỉ trưởng nhóm cập nhật STATUS.md.

### SEC-03 · Kiểm quyền trước parser và giới hạn multipart

| Người | Ước lượng | Sprint | Ưu tiên | Phụ thuộc |
|---|---|---|---|---|
| M2 | 0,5 | S2 | P0 | PLAT-05 |

AUD-03/AUD-12: token sai/phiên hết hạn phải bị chặn trước khi parse/spool. Dùng
kiểm quyền chung, giao dịch ngắn trước upload; kiểm lại trong nghiệp vụ. Không
giữ row lock qua lúc client gửi body. Giới hạn file/field/byte theo endpoint,
không hiểu nhầm max_part_size là trần file.

- [ ] Token sai, token cũ, Authorization trùng không gọi parser.
- [ ] Upload hợp lệ chạy, hết hạn/thu hồi trong upload không được chấp nhận.
- [ ] File/field trùng hoặc ngoài allowlist và trần file bị chặn trong parser.
- [ ] Có test, tài liệu và bàn giao; không đổi hợp đồng bên ngoài.

### SEC-04 · Chuẩn hóa ảnh và vòng đời rescan

| Người | Ước lượng | Sprint | Ưu tiên | Phụ thuộc |
|---|---|---|---|---|
| M2 | 0,5 | S2 | P0 | PLAT-05 |

AUD-01/AUD-02: xác thực byte gốc trước sanitation với media ký; ảnh dựa vào nội
dung, không suffix. CCCD được kiểm trước OCR. Tên file do server cấp; rollback
không làm mất cặp cũ; dọn ảnh cũ sau commit và file mới sau rollback. Có trần
lượt/tổng dung lượng rescan, bền qua restart, không nới guard model.

- [ ] JPEG đổi đuôi vẫn qua cùng kiểm tra và xóa EXIF; file giả bị chặn.
- [ ] Bounds ảnh áp dụng trước OCR/ML, đúng thứ tự chữ ký và rollback nonce.
- [ ] Rescan/ghi lỗi/commit lỗi/concurrency không mất cặp đã commit hoặc xóa nhầm.
- [ ] Có trần tài nguyên cấu hình và kiểm thử; không commit ảnh thật.

### SEC-05 · Profile bảo mật và chặn cấu hình dev dùng nhầm

| Người | Ước lượng | Sprint | Ưu tiên | Phụ thuộc |
|---|---|---|---|---|
| M2 | 0,5 | S2 | P0 | PLAT-05 |

AUD-05/AUD-06/AUD-08: profile dữ liệu thật fail-closed khi thiếu privacy, ký media,
khóa hợp lệ hoặc dùng HMAC dev. OTP mô phỏng không chứng minh giữ số điện thoại;
luồng yêu cầu thật chưa có kênh thật phải đóng. Kiểm cấu hình toàn API/Compose;
không tự sinh/ghi đè khóa, không chạy npm audit BBS khi chưa có quyền egress.

- [ ] Cấu hình an toàn được kiểm trước nhận dữ liệu; dev/mock tách rõ.
- [ ] OTP real-mode không trả simulated_sms hoặc công nhận mã mô phỏng.
- [ ] Cấu hình mẫu/runbook phù hợp; guard sinh trắc vẫn giữ.
- [ ] Có kiểm thử âm/dương; không sửa UI, schema, ADR hoặc ngưỡng.

### SEC-06 · Khép kín retention và thao tác riêng tư

| Người | Ước lượng | Sprint | Ưu tiên | Phụ thuộc |
|---|---|---|---|---|
| M5 | 1 | S2 | P0 | PLAT-05 |

AUD-04/AUD-07/AUD-08/AUD-11: triển khai nền backend cho phạm vi eKYC không bàn
duyệt. Ca chưa xác minh có deadline hữu hạn (mặc định đề xuất 24h, cấu hình rõ),
không chuyển thành pass hoặc dựng quyết định nhân viên giả. Tách mode công cụ
future work. Consent/rút lại/xóa sớm phải khớp hợp đồng trước code nếu triển khai.
Không tự di chuyển hoặc xóa kho thật; giữ giới hạn thu hồi credential đã cấp.

- [ ] Review mở được dọn theo profile eKYC mới; mode công cụ giữ nghiệp vụ riêng.
- [ ] Không đọc/cấp kết quả từ dữ liệu hết hạn; polling không kéo dài retention.
- [ ] Thao tác consent/rút lại, nếu thêm, có schema/type/API/test thống nhất.
- [ ] Có bàn giao rõ những phần app/thiết bị/backup chưa nghiệm thu.

### SEC-07 · Vá dependency web và kiểm chứng tích hợp

| Người | Ước lượng | Sprint | Ưu tiên | Phụ thuộc |
|---|---|---|---|---|
| M2 | 0,5 | S2 | P0 | PLAT-02, PLAT-05 |

AUD-13/AUD-14: vá Next.js/eslint-config-next 16.4.3 theo advisory và release
đã đối chiếu, cập nhật lockfile không audit fix force. Tích hợp các bản sửa,
chạy kiểm tra phù hợp và ghi lại mức khắc phục theo từng AUD. Không gọi tất cả
advisory là đã khai thác được; giữ hạng mục chưa có bằng chứng ở trạng thái mở.

- [ ] Next/config/lockfile đồng bộ; unit/type/lint/build phù hợp đạt.
- [ ] Các kịch bản AUD-01…06 được chạy lại trên bản tích hợp.
- [ ] Python lint/contract/backlog và test liên quan đạt.
- [ ] PR/bàn giao nêu rõ phạm vi, kiểm chứng và giới hạn còn lại.
