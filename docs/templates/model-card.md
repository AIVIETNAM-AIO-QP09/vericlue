# Thẻ mô hình — <tên mô hình> · <ngày>

> Lưu cùng trọng số ở `models/finetuned/<tên>/<ngày>/card.md`. Một bản sao ngắn ghi vào PR.

| Mục | Giá trị |
|---|---|
| Mô-đun | face_pad / face_deepfake / voice_spoof / … |
| Mô hình gốc | repo + checkpoint + giấy phép |
| Commit code huấn luyện | |
| Task | FACE-04 / VOICE-03 / … |
| Dữ liệu huấn luyện | bộ + tập (train) + số mẫu theo nhãn |
| Dữ liệu chọn mô hình | bộ + tập (**calib**, không phải test) |
| Tăng cường dữ liệu | liệt kê + tham số |
| Siêu tham số | lr, epoch, batch, lớp được huấn luyện |
| Phần cứng, thời gian | GPU gì, mấy giờ |
| SHA-256 trọng số | |
| Giấy phép trọng số | ví dụ CC BY-NC-SA (chỉ phi thương mại) |

## Kết quả trên tập calib
| Chỉ số | Giá trị | Khoảng tin cậy 95% | Số mẫu |
|---|---|---|---|

## Giới hạn đã biết
-

## Cách nạp
```python
```
