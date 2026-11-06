# Bàn giao — Biên tập bộ tài liệu giới thiệu và đóng góp

**Ngày:** 06/11/2026. **Người thực hiện:** Codex.
**Phạm vi:** yêu cầu trực tiếp cải thiện README, CONTRIBUTING, LICENSE sau bản
`11fa9a9`; chưa có task card riêng, không cập nhật trạng thái tính năng/backlog.

## Thay đổi

- README đi theo mạch giá trị sản phẩm, trải nghiệm, kiến trúc, mô hình bảo
  vệ, tích hợp và cách phát triển. Giữ bốn ảnh tổng hợp có provenance.
- Giải thích trust boundary: chữ ký/L0 khác kiểm tra nội dung, server quyết
  định, BBS là nhánh tích hợp riêng; ví Android chưa nối hoàn chỉnh.
- Nêu ví dụ bên nhận vẫn lập hồ sơ và cấp quyền; không biến chia sẻ chọn lọc
  thành quyền bỏ qua thông tin bắt buộc. Giữ điều kiện nghiệm thu ở cuối.
- CONTRIBUTING chuyển thành quy trình theo hành vi và bằng chứng, có bất
  biến an toàn, kiểm theo thành phần và checklist review cụ thể.
- LICENSE chia năm mục về phạm vi, bên thứ ba, trọng số/dữ liệu, quyền khác
  và đóng góp. Giữ nguyên câu không cấp phép cùng chủ sở hữu/năm hiện có;
  không thêm quyền thương mại, chuyển nhượng hoặc nghĩa vụ CLA mới.

## Kiểm tra

- Link local, anchor, UTF-8, code fence/details: đạt.
- SHA-256 bốn ảnh tiếp tục khớp provenance; không sửa ảnh.
- `git diff --check`: đạt.
- `scripts/plan_check.py`: 0 lỗi, 10 cảnh báo tải/đường găng hiện có.
- Không chạy test ứng dụng/model vì không sửa code. Mermaid và cấu trúc
  Markdown được kiểm nguồn; chưa xác nhận render trực tiếp trên GitHub.

## Ngoài phạm vi

- Không thay license upstream, ngưỡng, schema, runtime, proposal, ADR, STATUS
  hoặc AGENTS. Không động tới file nghiên cứu untracked của người dùng.
- Giấy phép vẫn độc quyền; yêu cầu phát hành nguồn mở cần quyết định riêng.
