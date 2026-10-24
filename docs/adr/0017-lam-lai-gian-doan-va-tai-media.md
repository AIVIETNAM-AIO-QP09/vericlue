# ADR-0017: Thông báo làm lại, xử lý khi bị gián đoạn, và cách tải media lên

- **Trạng thái:** đã chấp nhận
- **Ngày:** 2026-10-23
- **Người quyết định:** Trưởng nhóm (người dùng) cùng phiên điều phối
- **Liên quan:** ADR-0011 (token theo phiên, thử thách sống 120 giây), ADR-0013 (luồng eKYC), ADR-0016 (Dynamic Liveness)

## Bối cảnh
Rà lại luồng đăng ký mới (23/10), nhóm thấy ba chỗ dễ làm người thật bỏ ngang hoặc gây hiểu sai về bảo mật:

1. **Thông báo khi phải làm lại.** Nếu chỉ báo chung chung rồi bắt làm lại, người dùng bực và bỏ ngang. Nhưng nếu báo quá cụ thể ở các bước kiểm tra chống giả mạo, ta lại chỉ cho kẻ gian biết lớp nào đã bắt được họ.
2. **Bị gián đoạn giữa chừng.** Có cuộc gọi đến, hoặc ứng dụng bị chuyển xuống nền, khi phiên sắp hết 5 phút (ADR-0011). Bắt làm lại từ đầu thì phiền. Nhưng nếu cho làm tiếp giữa lúc đang quay mặt, ta lại phá nguyên tắc "camera bật liên tục" (ADR-0013, nguyên tắc 4), và đó chính là khe hở để tráo người, tráo nguồn hình.
3. **Tải video lên.** Video 20 giây trên mạng 4G chập chờn dễ làm người dùng chờ lâu. Nhưng nén quá mạnh sẽ xóa mất những chi tiết các lớp kiểm tra cần: màu da đổi theo ánh sáng, vân màn hình, viền mặt ghép. Ngoài ra có một hiểu nhầm cần ghi rõ: ký số video **không** chống được tấn công chèn luồng camera.

## Quyết định

### 1. Thông báo làm lại: chia hai loại
| Loại lỗi | Cách báo | Ví dụ chữ hiển thị |
|---|---|---|
| **Chất lượng** (độ nét, ánh sáng, khoảng cách, góc, lóa) | **Cụ thể, kèm cách sửa** | "Ảnh bị mờ, hãy giữ máy chắc tay" · "Hơi tối, hãy ra chỗ sáng hơn" · "Hãy giữ điện thoại ngang tầm mắt" · "Lại gần hơn một chút" · "Thẻ bị lóa, hãy nghiêng nhẹ" |
| **Thử thách** (ánh mắt, quay đầu, câu đọc) | **Hướng dẫn cách làm cho đúng**, không nói lớp nào không đạt | "Hãy giữ đầu yên, chỉ đưa mắt theo chấm sáng" · "Quay chậm hơn, rồi quay lại nhìn thẳng" · "Hãy đọc to, rõ từng chữ" |

- Lỗi chất lượng được nhắc **ngay trong lúc chụp** (viền khung đổi màu, chữ nhắc), để phần lớn được sửa trước khi gửi.
- Màn làm lại luôn hiện **số lần thử còn lại**.
- Giữ luật cũ: chất lượng tối đa 2 lần chụp lại; thử thách làm lại 1 lần với thử thách mới; quá giới hạn thì chuyển thẩm định. Không bao giờ hiện điểm số hay chữ "giả mạo" (AGENTS §6 luật 3).

### 2. Bị gián đoạn: gia hạn ở giai đoạn A, làm lại riêng phần khuôn mặt ở giai đoạn B và C
| Đang ở đâu | Xử lý |
|---|---|
| Giai đoạn A (đồng ý, OTP, căn cước, xác nhận) | **Tự gia hạn mã truy cập** khi người dùng quay lại; làm tiếp từ bước đang dở |
| Giai đoạn B hoặc C (camera trước đang bật) | **Giữ kết quả giai đoạn A**. Phần khuôn mặt (và câu đọc) **làm lại với gói thử thách mới**; dữ liệu khuôn mặt của lần dở bị bỏ |
| Tổng thời gian | Có **giới hạn trên cho cả phiên** (đề xuất 15 phút; chốt con số khi làm task). Quá hạn thì bên tích hợp mở phiên mới |

Điều này **thay một phần ADR-0011 mục 1–2**: mã truy cập vẫn ngắn (khoảng 5 phút) nhưng được gia hạn trong giới hạn tổng; "mỗi bước nhận một lần" vẫn giữ trong từng lượt làm phần khuôn mặt, mỗi lượt mới dùng gói thử thách mới. Hợp đồng API thay đổi: PR gắn `[contract]`.

### 3. Tải media lên
- Video dạng **WebM trên web** (trình duyệt tự quay) và **MP4 trên app Android** (CameraX quay ra MP4; server nhận cả hai, sửa 24/10 theo `apps/android/docs/can-chot.md` câu 6). Độ phân giải vừa phải; **không nén mạnh** tới mức mất chi tiết.
- Gửi kèm **ảnh tĩnh chất lượng cao** cho ba góc mặt (góc 1 lúc nền xám, góc 2, góc 3) để các mô hình cần chi tiết dùng.
- **Tải lên dần trong lúc quay**: chia video thành nhiều đoạn, gửi từng đoạn. Mỗi đoạn được ký, chuỗi chữ ký nối các đoạn với nhau và với mã phiên, nên máy chủ phát hiện được đoạn bị thiếu, bị đổi chỗ hay bị thay.
- **Đo thực tế** dung lượng và thời gian tải trên mạng 4G trước khi chốt độ phân giải. Con số ước lượng hiện có (khoảng 4–8 MB cho 20 giây) chưa đo.

### 4. Ký số chống được gì
- **Chống được:** video cũ gửi lại (phát lại) và video bị sửa giữa đường.
- **Không chống được:** chèn hình vào luồng camera, vì mã độc chèn hình **trước** khi điện thoại ký, nên điện thoại ký luôn hình giả. Chèn luồng camera do **phát hiện camera ảo** và **ánh sáng phản chiếu** đảm nhận (ADR-0016).
- Mọi tài liệu, slide, kịch bản phải nói đúng điều này.

## Phương án đã cân nhắc
- **Cho làm tiếp giữa chừng phần khuôn mặt sau khi gián đoạn:** loại, vì phá tính liền mạch của camera.
- **Bắt làm lại từ đầu khi gián đoạn:** loại, vì phiền và dễ bỏ ngang, trong khi giai đoạn A không có rủi ro tráo người.
- **Nén video mạnh để tải nhanh:** loại, vì làm mất bằng chứng cho các lớp kiểm tra.

## Hệ quả
- Task mới: **LIVE-06** (gia hạn phiên, làm lại riêng phần khuôn mặt), **LIVE-07** (thông báo làm lại hai loại). LIVE-03 thêm tải lên dần và ký từng đoạn.
- Cần bảng chữ hiển thị cho mọi tình huống làm lại, duyệt theo luật 3.
