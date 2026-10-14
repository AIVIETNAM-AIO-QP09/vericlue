# Kết quả đánh giá (R1–R6)

Mỗi file kết quả do code trong repo sinh ra (`ml/src/vericlue_ml/eval/`), **không gõ tay số liệu**.

| File | Nội dung | Task |
|---|---|---|
| `R1-baseline.md`, `R1-final.md` | PAD trên người Việt, trước và sau tinh chỉnh | FACE-01, FACE-04 |
| `R2-baseline.md`, `R2-final.md` | Deepfake khuôn mặt theo bộ dữ liệu × mức nén | FACE-02, FACE-04 |
| `R3-baseline.md`, `R3-final.md` | Giọng giả theo vùng miền × công cụ × mức nén | VOICE-01, VOICE-03 |
| `R4-thresholds.md`, `R4-final.md` | Ngưỡng Learn-then-Test; so sánh TrustRouter | ROUT-03, ROUT-05 |
| `R5.md` | Chạy thử ChromaPulse và CamProbe | PRES-04 |
| `R6.md` | Độ trễ | EVAL-02 |

**Mỗi file bắt buộc ghi:**
- commit;
- phiên bản mô hình;
- bộ dữ liệu và tập (calib/test);
- số mẫu theo nhãn và loại tấn công;
- khoảng tin cậy 95%;
- ngày chạy.
