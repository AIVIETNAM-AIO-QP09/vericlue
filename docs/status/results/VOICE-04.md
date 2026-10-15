# VOICE-04 — Kiểm tra câu đọc

- Bộ dữ liệu: ViMD selected_manifest (original human speech)
- Commit: 8ba9e6a0ccdf27e97b19f93a6a5667bd51a91d70 (dirty=False)
- Mô hình: phowhisper-small@a86b604c346caf7148c37512eafe783a16420adb+voice04-v1
- Revision dữ liệu: 3a5b30157034e7eadd5c75fae1a820c6f9383398
- Ngày: 2026-10-15T10:35:30.982650+07:00
- Ngưỡng cố định: WER ≤ 0.3; giống bỏ dấu ≥ 0.9.
- Tỷ lệ không đạt tính cả đọc sai và lỗi xử lý; không bỏ mẫu lỗi.

| Miền | Người | Câu | Đọc sai | Lỗi xử lý | Không đạt | Tỷ lệ không đạt | CP95 theo câu |
|---|---:|---:|---:|---:|---:|---:|---|
| North | 4 | 6 | 0 | 0 | 0 | 0.00% | [0.00%, 45.93%] |
| Central | 4 | 6 | 1 | 0 | 1 | 16.67% | [0.42%, 64.12%] |
| South | 4 | 7 | 1 | 0 | 1 | 14.29% | [0.36%, 57.87%] |
| Tổng | 12 | 19 | 2 | 0 | 2 | 10.53% | [1.30%, 33.14%] |

## Giới hạn

CP95 tính theo câu, giả định các câu độc lập; nhiều câu cùng người không độc lập. Chỉ có bốn người mỗi miền trong bản small; đây là thử nghiệm mô tả, chưa chứng minh công bằng theo miền. Lỗi xử lý được tính vào tỷ lệ không đạt. Không chọn mô hình hoặc ngưỡng từ các mẫu này. Thử nghiệm nhỏ; câu ViMD dài, chưa tương đương câu thử thách 8–12 âm tiết.

## Người theo miền

- North: spk_14_0070, spk_22_0049, spk_30_0148, spk_88_0111
- Central: spk_37_0269, spk_77_0056, spk_78_0243, spk_79_0063
- South: spk_70_0040, spk_71_0092, spk_83_0108, spk_93_0184

## TTS đọc đúng / đọc sai

2 ca: 1 đọc đúng, 1 đọc sai; 2 phân loại đúng, 0 lỗi xử lý.
