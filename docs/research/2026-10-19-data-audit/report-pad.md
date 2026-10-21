# Nghiên cứu dữ liệu PAD cho VeriClue (19/10/2026)

> Agent không ghi được file này, nên phiên điều phối chép lại từ báo cáo trả về.
> - Số đo: `out\*_metrics.json` và `out\an\*_metrics.json`.
> - Ảnh ghép: `out\celeba_spoof_ar4ikov_{live,spoof}.jpg`, `out\an\axon_*.jpg`, `out\an\unique_asian_live.jpg`, `out\an\secondlife_*.jpg`.
> - Script: `scripts\dl.py`, `pad_an.py`, `celeb_ids.py`, `fasvn_minifas.py`.
> - Phiên điều phối đã tự xem `celeba_spoof_ar4ikov_spoof.jpg`. Ảnh gồm ảnh in cầm tay, poster, mặt nạ giấy cắt, phần lớn là người nổi tiếng phương Tây; có nhiều ảnh gần trùng nhau.

## Bảng tóm tắt

| Bộ | Giấy phép / cách lấy | Nội dung thực tế (đã xem) | Lộ đề | Vai trò | Rủi ro |
|---|---|---|---|---|---|
| FAS-VN | Trang ghi CC BY 4.0. Ảnh "thật" có vẻ lấy từ hệ thống eKYC thật. Đã có trên máy | Người Việt, không khẩu trang, tấn công chỉ là chụp lại màn hình. MiniFAS (chưa tinh chỉnh) để lọt 28–33% ảnh giả (n = 150/nhóm), AUC 0,909 (n = 599) | Chiều rộng ảnh 0,989; EXIF 0,991; ảnh trùng nằm cả ở train lẫn test | Dạy và hiệu chỉnh tấn công màn hình, **sau khi làm sạch** | Nguồn gốc ảnh và sự đồng ý của người trong ảnh |
| CelebA-Spoof | Chỉ nghiên cứu phi thương mại, cấm phân phối lại. Tải từ Drive: khoảng 77 GB, chia phần 1 GB | Ảnh thật là ảnh web người nổi tiếng. Ảnh giả gồm ảnh in, poster, giấy cắt, chụp bằng điện thoại. MiniFAS để lọt **59,5%** ảnh giả (n = 444) | Số điểm ảnh 0,783; độ sáng 0,771 | Dạy phần **ảnh in / giấy cắt** (lấy một phần), và làm test khác miền | Bản mirror trên HF mất ID người và loại tấn công. Bản gốc không vừa ổ D |
| Zalo 2022 | Link gốc trả về 404; mirror ghi MIT | Khẩu trang ở 63/64 ảnh; chỉ có tấn công phát lại | Thời lượng 0,80 | Chỉ làm test phụ | — |
| ROSE-Youtu | Học thuật, **chỉ cần đăng ký**, không cần giảng viên ký | 20 người, 5 thiết bị camera trước; ảnh in, màn hình, mặt nạ giấy cắt; có ID người | Chưa kiểm | Test khác miền; **đăng ký ngay** | Chưa biết thời gian duyệt |
| OULU-NPU, Replay-Mobile, CeFA, SiW, HiFiMask, CASIA, WFAS, PADISI, MSU | Phải có **giảng viên biên chế ký**, dùng email trường, cấm thương mại | OULU: 6 điện thoại camera trước. Replay-Mobile: iPad, LG G4. CeFA: 500 người Đông Á | Tài liệu đã báo cáo lộ đề nền và ánh sáng | Gửi đơn ngay, **không đặt vào đường găng** | Có thể không được duyệt kịp 06/11 |
| LCC-FASD | Không có giấy phép gốc; Kaggle 5,2 GB | 243 người, 83 thiết bị | Chưa kiểm | Tùy chọn | Giấy phép |
| Mẫu Axon | Kaggle CC BY-NC | Mỗi loại 5–14 video. MiniFAS để lọt **ảnh in cắt 86,7%, mặt nạ giấy 3D 96,7%**, ảnh in 17%, màn hình 8–25% | Ảnh tĩnh và video khác nhau (AUC 1,0) | Chỉ test APCER theo loại tấn công | n rất nhỏ |
| UniData Asian | CC BY-NC-ND | 10 người (2 người Việt), selfie + quay đầu; chỉ có ảnh thật | — | Đo BPCER khác miền | ND, quá nhỏ |
| secondlife-ai, mirror akahana | — | Gắn nhãn sai | — | **Loại** | — |

## Kết luận của agent
- Không có bộ công khai nào khớp miền của VeriClue.
- MiniFASNet yếu nhất ở **ảnh in cắt** và **mặt nạ giấy**.
- Agent đề xuất **tự quay bộ "VN-Self"**:
  - ≥ 30 người, quay bằng camera trước Android, 3 điều kiện ánh sáng;
  - mẫu thật, cộng các kiểu tấn công: in A4, giấy ảnh, poster, cắt lỗ mắt, phát lại trên điện thoại / tablet / laptop;
  - có phiếu đồng ý và subject_id.
- **Chú ý:** đề xuất này **trái với quyết định ngày 17/10** (không thu dữ liệu người thật, không dùng mặt thành viên). Trưởng nhóm cần quyết.

## Làm sạch bắt buộc
- Chia theo người (hoặc theo cụm ArcFace). Ảnh gốc và ảnh chụp lại của nó phải nằm cùng một phía.
- Lọc trùng bằng SHA + dHash ≤ 4.
- Cả hai lớp đi qua cùng một đường xử lý: SCRFD + đệm viền → cắt ×2,7 → resize → nén JPEG lại → bỏ EXIF.
- Mô hình chỉ dùng siêu dữ liệu phải cho AUC ≈ 0,5.

## Dung lượng
- Ổ D còn 62 GB, ổ C còn 76 GB.
- CelebA-Spoof bản gốc khoảng 77 GB: phải tải về ổ C hoặc ổ ngoài, giải nén một phần sang D, rồi xóa zip.
- Phương án dự phòng: mirror test 4,9 GB. Nhược điểm: mất loại tấn công và trái điều khoản.
- ROSE-Youtu: 5,45 GB.

## Câu hỏi cho nhóm
1. Có dùng FAS-VN không, khi nguồn gốc ảnh đáng ngờ?
2. Lấy CelebA bản gốc (cần ổ C hoặc ổ ngoài) hay dùng mirror?
3. Có giảng viên biên chế ký đơn ngay cho OULU, Replay-Mobile, CeFA không?
4. Có tự quay VN-Self không?
