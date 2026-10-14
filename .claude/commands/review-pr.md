---
description: Tự rà thay đổi hiện tại theo Definition of Done của dự án
argument-hint: "[MÃ-TASK]"
---

Rà thay đổi hiện tại (`git diff` so với `main`) cho task $ARGUMENTS:

1. Đối chiếu với tiêu chí hoàn thành trong task card và Definition of Done ở AGENTS.md §8.
2. Kiểm tra luật bắt buộc ở AGENTS.md §6, đặc biệt:
   - khớp `packages/contracts/`;
   - không lộ điểm số cho người dân;
   - `error` không bị coi là đạt;
   - không commit dữ liệu, trọng số hay bí mật;
   - giấy phép của code chép về.
3. Chạy lint và test liên quan, báo kết quả thật.
4. Liệt kê các vấn đề theo mức: **phải sửa / nên sửa / gợi ý**, kèm `file:dòng`.
5. Không tự sửa nếu người dùng chưa đồng ý.
