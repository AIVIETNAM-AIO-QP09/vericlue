# Thu dữ liệu ChromaPulse (task CAP-03)

Hướng dẫn từng bước cho **người không chuyên**. Làm xong, bạn có các file JSON để M3 phân tích ở PRES-01 (cổng quyết định **17/10**: giữ ChromaPulse làm cổng chính hay hạ xuống tín hiệu phụ).

> **Đây là kiểm thử phần mềm, không phải thu dữ liệu cá nhân.** File JSON chỉ chứa **con số màu và thời gian**, không có ảnh hay khung hình. Trang không gửi gì lên máy chủ. Sau demo, xóa file (`docs/data/data-plan.md` §4).

## 1. Cần gì

| Cần | Ghi chú |
|---|---|
| Một **máy tính chạy trang** (Windows) | Đã làm `./scripts/setup.ps1` (xem `dev-setup.md`) |
| **Android tầm trung** + **iPhone** + **laptop** | Cùng Wi-Fi với máy tính chạy trang (laptop có thể chính là máy chạy trang) |
| Một **màn hình thứ hai** | Điện thoại/tablet khác, dùng cho tình huống "phát lại" |
| **OBS Studio** | Chỉ trên laptop, cho tình huống OBS (https://obsproject.com) |

## 2. Chuẩn bị một lần (trên máy tính chạy trang)

Mở PowerShell trong thư mục repo, ví dụ `D:\Projects\vericlue-claude`:

```powershell
cd apps\web
npm ci
cd ..\..
uv run python scripts/fetch_web_assets.py
uv run python scripts/fetch_web_assets.py --check
```

Dòng cuối phải in `Đủ file MediaPipe cho chế độ offline`. Hai lệnh này chép file MediaPipe (bộ nhận diện khuôn mặt) vào `apps/web/public/mediapipe/` để trang chạy **không cần mạng**. Nếu `--check` báo thiếu, chạy lại lệnh `fetch_web_assets.py`.

## 3. Chạy trang và mở trên từng máy

### 3a. Laptop (cùng máy chạy trang)

```powershell
cd apps\web
npm run dev
```

Mở **http://localhost:3000/lab/chromapulse**. Với `localhost`, camera hoạt động không cần HTTPS.

### 3b. Điện thoại (Android, iPhone): cần HTTPS

Camera trên điện thoại **chỉ chạy với HTTPS**. Trên máy tính chạy trang:

```powershell
cd apps\web
npm run dev -- --experimental-https -H 0.0.0.0
```

1. Xem địa chỉ IP của máy tính: gõ `ipconfig`, tìm dòng **IPv4 Address** (ví dụ `192.168.1.23`).
2. Trên điện thoại (cùng Wi-Fi) mở `https://192.168.1.23:3000/lab/chromapulse` (thay bằng IP của bạn).
3. Trình duyệt báo "kết nối không riêng tư" (chứng chỉ tự tạo): chọn
   - **Android (Chrome):** *Nâng cao* → *Tiếp tục truy cập*.
   - **iPhone (Safari):** *Hiển thị chi tiết* → *truy cập trang web* → xác nhận.
4. Windows có thể hỏi về tường lửa: chọn **Cho phép** (mạng riêng tư).
5. Không vào được? Wi-Fi công cộng hoặc Wi-Fi khách thường **chặn các máy nói chuyện với nhau**. Dùng Wi-Fi của nhóm hoặc phát Wi-Fi từ một điện thoại.

### 3c. Đường dự phòng cho iPhone: `cloudflared`

Nếu iPhone vẫn **không bật được camera** với chứng chỉ tự tạo (Safari trên iPhone hay từ chối), dùng đường hầm HTTPS có chứng chỉ thật:

```powershell
winget install --id Cloudflare.cloudflared      # chỉ lần đầu
cd apps\web
npm run dev                                      # cửa sổ PowerShell thứ nhất
```

Mở **cửa sổ PowerShell thứ hai**:

```powershell
cloudflared tunnel --url http://localhost:3000
```

Lệnh in ra một địa chỉ dạng `https://tên-ngẫu-nhiên.trycloudflare.com`. Trên iPhone mở `<địa chỉ đó>/lab/chromapulse`.

- Địa chỉ này **công khai với ai có link**; trang không lưu dữ liệu, nhưng hãy **tắt đường hầm** (Ctrl+C) ngay khi thu xong.
- Nếu trang mở được nhưng nút bấm không phản hồi, báo M1 kèm ảnh chụp màn hình.

## 4. Thu một lần thử (làm trên màn hình điện thoại/laptop đang thử)

1. Điều chỉnh **độ sáng màn hình lên tối đa**. Tắt chế độ tối/tiết kiệm pin. Ngồi nơi **ánh sáng phòng vừa phải** (không ngược sáng, không nắng chiếu thẳng).
2. Mở trang, đọc hai mục **Dữ liệu được ghi** và **Cảnh báo nháy màu**, đánh dấu *Tôi đã đọc hai mục trên*. Người nhạy cảm với ánh sáng nhấp nháy **không nên thử**.
3. Gõ **Tên máy** (ví dụ `Redmi Note 12`, `iPhone 13`, `Laptop Dell`). Tên này nằm trong tên file.
4. Bấm **Bật camera và tải MediaPipe**, cho phép camera. (Trên laptop có OBS: ở hộp thoại xin quyền camera, chọn **OBS Virtual Camera** nếu đang thử tình huống OBS.)
5. Khi màn hình hiện hình camera, kiểm tra:
   - dòng trạng thái: **Thấy mặt**, **Bộ xử lý** (GPU hoặc CPU), **captureTime: có/không**;
   - các khung màu: trán, hai má, mũi, cằm phải nằm **trên da mặt**, không nằm trên tóc, kính hay mắt. Hai ô nền nằm ở **hai góc trên**. Nếu lệch nhiều, chỉnh tư thế; báo M1 nếu vẫn lệch.
6. Chọn **Tình huống** (xem mục 5) và **Lần thứ** (1 hoặc 2). Có thể gõ **Ghi chú** (ánh sáng, khoảng cách).
7. Cầm máy cách mặt **25 đến 40 cm**, mặt nằm giữa khung hình. Bấm **Bắt đầu thử**.
8. Trang đếm ngược 3 giây, rồi màn hình đổi màu khoảng **8 giây**. **Giữ yên mặt và nhìn vào màn hình**, không che camera. Muốn dừng, bấm **Dừng**.
9. Khi xong, trang hiện tóm tắt: số khung, số khung thấy mặt, số màu ghi được (phải là **8**) và mục **Cần lưu ý**. Nếu có lưu ý như "thấy mặt ở quá ít khung" hay "chỉ ghi được x/8 màu", bấm **Thử lại** và làm lại.
10. Bấm **Tải file JSON**. File được lưu với **tên tự động**, ví dụ `redmi-note-12_chrome_real_01.json`. **Không đổi tên.**
11. Muốn thử tiếp, bấm **Lần kế tiếp** (số lần tự tăng).

## 5. Cần thu những gì

Mỗi máy và mỗi tình huống thu **2 lần** (lần 1 và lần 2). Tổng cộng **14 file**:

| Máy | Người thật (`real`) | Phát lại (`replay`) | OBS (`obs`) | Số file |
|---|---|---|---|---|
| Android tầm trung | 2 | 2 | không | 4 |
| iPhone | 2 | 2 | không | 4 |
| Laptop | 2 | 2 | 2 | 6 |
| **Tổng** | | | | **14** |

Cách làm từng tình huống:

- **Người thật (`real`):** mặt của bạn trước camera, như mục 4.
- **Phát lại (`replay`):** trên **màn hình thứ hai** (điện thoại/tablet khác), phát một **video quay mặt người** (hoặc mở một ảnh chân dung to). Đặt màn hình đó **trước camera** của máy đang thử, cách 25 đến 40 cm, độ sáng tối đa. Tình huống này mô phỏng kẻ tấn công phát lại video.
- **OBS (`obs`):** chỉ trên laptop. Mở OBS Studio, thêm nguồn *Video Capture Device* (webcam), bấm **Start Virtual Camera**. Trong trang lab, ở hộp thoại xin quyền camera chọn **OBS Virtual Camera**. Sau khi bắt đầu, dòng `camera_label` trong file JSON phải chứa chữ OBS.

## 6. Nộp file

1. Gom các file JSON vào thư mục **`D:\Projects\vericlue-store\data\chromapulse\`** (tạo nếu chưa có).
2. **KHÔNG commit** các file này vào repo (kể cả khi chỉ có số màu; `AGENTS.md` §6 luật 5).
3. Báo M3 trong kênh nhóm: đã thu bao nhiêu file, và **trình duyệt nào có `captureTime`** (trang hiện dòng `captureTime: có/không` ở bước 5, ghi lại cho từng máy: Android/Chrome, iPhone/Safari, laptop/Chrome).
4. Xóa file sau demo.

## 7. Sự cố thường gặp

| Hiện tượng | Cách xử lý |
|---|---|
| "Camera trên điện thoại cần HTTPS" | Dùng mục 3b (hoặc 3c) |
| Không bật được camera trên iPhone | Dùng mục 3c (`cloudflared`) |
| Lỗi tải MediaPipe, báo thiếu file | Chạy `uv run python scripts/fetch_web_assets.py` (mục 2) |
| "Không hỗ trợ requestVideoFrameCallback" | Dùng Chrome mới nhất (Android, laptop) hoặc Safari từ iOS 15.4 |
| Luôn "Chưa thấy mặt" | Tăng sáng phòng, đưa mặt vào giữa, bỏ khẩu trang/kính tối màu |
| Màn hình tự tối trong lúc thử | Trang đã xin giữ màn hình sáng; nếu máy vẫn tối, tắt tiết kiệm pin |
| Bộ xử lý báo **CPU** chậm, ít khung | Bình thường trên máy yếu; ghi chú lại, vẫn nộp file |
| Muốn xem lại số liệu | Mở file JSON bằng trình soạn thảo (không chứa ảnh) |

## 8. Dành cho M3: đọc file JSON

Tên trường `color_events` và `frame_times` bám hợp đồng `Signals` (`packages/contracts/schemas/session.schema.json`). Mọi mốc thời gian cùng đồng hồ `performance.now()` (mili giây).

| Trường | Ý nghĩa |
|---|---|
| `scenario`, `take`, `note`, `device`, `camera.settings` | Tình huống, lần thử, ghi chú, thông tin máy; cài đặt camera thực tế (phơi sáng/cân bằng trắng tự động ảnh hưởng phép đo) |
| `support.has_capture_time`, `support.frame_metadata_keys` | Trình duyệt này có `captureTime` không; các khóa metadata mà `requestVideoFrameCallback` trả về |
| `config`, `sequence`, `timeline` | Bảng màu, nhịp (lấy từ `packages/contracts/chromapulse.json`), chuỗi 8 màu đã phát, mốc thời gian |
| `color_events[{index, rgb, painted_at}]` | `painted_at` = khung `rAF` đầu tiên vẽ bước này (bắt đầu chuyển sang màu mới, chuyển 150 ms) |
| `display_samples[[t, r, g, b]]` | Màu **thực sự vẽ** ở mỗi khung `rAF` (đã nội suy), dùng dựng tín hiệu `x(t)` |
| `frame_times[]` | Mỗi khung video: `now`, `media_time`, `presented_frames`, `capture_time` (hoặc `null`), `face_found`, `regions` |
| `frame_times[].regions.<vùng>` | `rgb_all` (trung vị mọi điểm ảnh), `rgb_trim` (bỏ điểm ảnh luma ≤ 55 hoặc ≥ 200, đồng bộ PRES-02), `excluded_fraction`, `pixels` |
| `region_defs` | Định nghĩa vùng: chỉ số landmark MediaPipe của 5 vùng da (trán, má trái, má phải, mũi, cằm; trái/phải theo khung hình) và quy tắc **vùng nền** (hai ô vuông ở **hai góc trên** của khung hình, cạnh = 12% chiều rộng, bỏ ô nào chạm hộp khuôn mặt cộng lề 10%) |

Khung bị lỡ (máy chậm) thấy qua khoảng nhảy của `presented_frames`. Khi không có `capture_time`, dùng `now`, `media_time` và nêu rõ đây là giới hạn (thẻ PRES-01).
