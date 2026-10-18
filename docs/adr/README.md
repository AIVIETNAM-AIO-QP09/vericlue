# Architecture Decision Records

Mỗi ADR ghi lại **một** quyết định quan trọng: bối cảnh, quyết định, phương án đã cân nhắc, hệ quả. Muốn đổi quyết định thì viết ADR mới và đánh dấu ADR cũ là "thay thế bởi ADR-XXXX". Mẫu: `0000-template.md`.

| # | Quyết định | Trạng thái |
|---|---|---|
| [0001](0001-monorepo-va-mock-truoc.md) | Monorepo, hợp đồng cố định, mô-đun giả lập trước | Chấp nhận |
| [0002](0002-chi-du-lieu-cong-khai.md) | Chỉ dùng dữ liệu công khai | Chấp nhận |
| [0003](0003-web-khong-lam-app.md) | Web trên điện thoại, không làm app | Chấp nhận |
| [0004](0004-mo-hinh-khuon-mat-gend-sbi.md) | GenD (chính) + SBI (dự phòng) + MiniFASNet | Chấp nhận |
| [0005](0005-giong-noi-antideepfake.md) | AntiDeepfake; kiểm tra câu đọc 8 bước | Chấp nhận |
| [0006](0006-trustrouter-ltt-mapie.md) | TrustRouter: Learn-then-Test qua MAPIE | Chấp nhận (bổ sung bởi 0010) |
| [0007](0007-chromapulse-camprobe.md) | ChromaPulse đo độ trễ tuyệt đối; CamProbe kiểm tra API | Chấp nhận |
| [0008](0008-giam-dinh-enfsi-nguon-goc.md) | Báo cáo ENFSI có chữ ký; quét nguồn gốc một chiều | Chấp nhận |
| [0009](0009-ha-tang-toi-gian-va-giay-phep.md) | Hạ tầng tối giản; chính sách giấy phép | Chấp nhận |
| [0010](0010-tach-tap-calib-va-luu-calibrator.md) | Tách `calib_fit` / `calib_ltt`; lưu calibrator trong `ml/configs/` | Chấp nhận (bổ sung 0006) |
| [0011](0011-token-phien-va-thu-thach.md) | Token theo phiên, mỗi bước nhận một lần; thử thách 120 giây; nhịp nháy màu an toàn | Chấp nhận |
| [0012](0012-mvp-chay-that.md) | Hồ sơ MVP `ROUTER_PROFILE=mvp`: chạy toàn đồ thật, bỏ ChromaPulse/khớp môi, calibrator tạm trên `calib_fit` | Chấp nhận (18/10) |
