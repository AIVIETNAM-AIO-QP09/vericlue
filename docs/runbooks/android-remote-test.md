# Test Android từ xa qua Tailscale

**APP-05 · Bản test nội bộ.** Cấu hình cơ sở bên dưới là API mô phỏng; profile
AI mặt từng phần ngày 29/10 được ghi ở mục 6. Laptop chạy FastAPI, điện thoại chạy
app Android hiện có; không cần web Next.js. Đường truyền riêng qua Tailscale Serve,
không bật Funnel hoặc mở cổng router. Cần Android 10 trở lên; APK được đóng gói
ở đây dành cho điện thoại ARM64.

## 1. Cho điện thoại truy cập laptop

1. Hai máy cài và đăng nhập Tailscale bằng tài khoản riêng của từng người.
2. Chủ laptop vào [Machines](https://console.tailscale.com/admin/machines), tìm
   laptop → **⋯ → Share → Copy invite link → Copy share link**. Để **Reusable
   link** tắt, tự gửi link cho người test; không gửi tài khoản/mật khẩu.
3. Người test nhận chia sẻ bằng đúng tài khoản trong ứng dụng Tailscale Android,
   bật kết nối. Chỉ cần quyền vào laptop, không cần thêm vào toàn bộ tailnet.
4. Trong Chrome, mở `https://<tên-máy>.<tailnet>.ts.net/healthz`. Phải thấy
   `status: ok`, `mock_models: true` trước khi mở app. Không bỏ kiểm tra chứng chỉ.

Tài liệu chính thức: [chia sẻ thiết bị](https://tailscale.com/docs/features/sharing),
[Serve riêng trong tailnet](https://tailscale.com/docs/features/tailscale-serve).

## 2. API trên laptop

Bản test ngày 28/10 dùng thư mục cục bộ **`tmp/remote-android/`**, khác DB/media
của lab và sản phẩm; thư mục này nằm ngoài Git. `.env` và các khóa tạo ngẫu nhiên
được giữ cùng DB để restart không làm mất khả năng giải mã. Không chạy lại
`prepare.py`, không thay khóa hoặc chép `.env` vào APK/CI.

| Cấu hình test | Giá trị |
|---|---|
| API | `127.0.0.1:8420`, một worker; SQLite đã migrate |
| Mô hình / sản phẩm | `USE_MOCK_MODELS=true`, `PRODUCT_MODE=ekyc` |
| Bảo vệ lưu trữ | `SESSION_PRIVACY=true`, khóa riêng cho test |
| Chữ ký media | `REQUIRE_MEDIA_PROOF=true` |
| Profile | `SECURITY_PROFILE=synthetic` |
| Consent API | `REQUIRE_PRIVACY_CONSENT=false` — app hiện chưa tích hợp |
| Tài khoản / BBS | `ACCOUNT_ENROLLMENT=false`, `PRIVATE_CREDENTIALS=false` |
| Hạn media | pass/chưa xác minh: 1 giờ; dọn mỗi 60 giây |
| Phiên / tạo phiên | tối đa 900 giây; 30 phiên/giờ/client |

Đây **không phải protected profile**. Chỉ test trong nhóm với CCCD/QR tổng hợp;
camera/micro vẫn thu dữ liệu thực của người test khi họ cấp quyền, nên giải thích
trước khi quay. Chưa dùng cho định danh người dùng bên ngoài. Thời hạn media không
có nghĩa mọi bản sao, log hoặc metadata đều bị xóa cùng lúc.

Sau khi chủ máy đã bật HTTPS trong Tailscale:

```powershell
& 'C:/Program Files/Tailscale/tailscale.exe' serve --bg --https=443 http://127.0.0.1:8420
& 'C:/Program Files/Tailscale/tailscale.exe' serve status
```

Giữ laptop thức và có mạng. Serve chạy nền nhưng không tự khởi động API khi
Windows restart. Bản runtime cục bộ có `launch.py` để nạp `.env`, migrate và chạy
Uvicorn; sau khi xác nhận cổng 8420 trống, khởi động lại bằng Python của repo:

```powershell
& './.venv/Scripts/python.exe' './tmp/remote-android/launch.py'
```

Lệnh này chạy foreground, `Ctrl+C` dừng API. Với API đã chạy nền, kiểm tra chủ
cổng bằng `Get-NetTCPConnection -LocalPort 8420 -State Listen` và đối chiếu
command line của PID là runtime này trước khi dừng. Không dừng mọi tiến trình Python.
Các helper runtime là cấu hình riêng của laptop, không có trong checkout mới.

Kết thúc đợt test, tắt đúng proxy được tạo cho đợt này:

```powershell
& 'C:/Program Files/Tailscale/tailscale.exe' serve --https=443 off
```

Sau đó dừng API và thu hồi chia sẻ MSI trên trang Machines. Không dùng `serve
reset` để tránh xóa cấu hình Serve khác.

## 3. Build và nhận APK

Workflow [Android remote test APK](../../.github/workflows/android-remote-test.yml)
nhận repository variable **`VERICLUE_REMOTE_API_URL`** là URL HTTPS ở bước 1,
kết thúc bằng `/`. URL là cấu hình định tuyến, không phải thông tin đăng nhập.
Không đặt key, token Tailscale hoặc token phiên trong biến này.

- Khi PR sửa Android/workflow và biến đã được đặt, CI chạy unit test rồi build
  APK debug với `-Pvericlue.signedMedia=true` và URL trên.
- Sau khi workflow có trên nhánh mặc định, có thể chạy **Run workflow**, tùy chọn
  nhập `api_base_url` để dùng endpoint riêng khác. Chỉ nhận tên miền `*.ts.net`.
- Tải artifact **`vericlue-android-remote-test`** trong trang run, giải nén. Có
  `vericlue-remote-debug-arm64-v8a.apk`, `SHA256SUMS.txt`, `build-info.json` ghi
  source SHA, URL, chế độ ký media và giới hạn chưa nghiệm thu phần cứng. Artifact
  giữ 7 ngày. CI không cần truy cập laptop hoặc có credential mạng riêng.
- So SHA-256 trước khi gửi APK; người test cài file, cấp quyền cài từ nguồn đang
  mở file nếu Android yêu cầu. Đây là debug APK để test nội bộ. Nếu khác chữ ký
  với bản đang cài, cần gỡ bản test cũ (mất dữ liệu cục bộ của bản đó).

## 4. Chạy các tình huống

1. Mở app → màn ngân hàng mẫu → **Xem tất cả màn (bản demo giao diện)**.
2. Chọn **API thật**, mục đích **Đăng ký**, kịch bản `genuine`. Nhãn này nghĩa là
   gọi HTTP tới server, **server vẫn dùng mô hình mô phỏng**.
3. Mở **Đăng nhập / Đăng ký** → **Đăng ký**, đi qua điều khoản, số điện thoại và
   OTP mô phỏng. OTP không phải SMS từ nhà mạng; không dùng số điện thoại thật.
4. Chụp mẫu giấy tờ tổng hợp ở bước CCCD; dùng **Dùng mã QR mẫu (debug)** ở màn
   xem lại. Không chụp CCCD thật. Cấp quyền camera/micro khi app hỏi.
5. Thực hiện giữ mặt, nhìn chấm, quay đầu và xác nhận thông tin theo app. Chỉ đọc
   câu khi server yêu cầu. Bản test không thay đổi UI hoặc rút gọn luồng.
6. Bắt đầu phiên mới cho từng kịch bản bên dưới.

| Kịch bản mô phỏng | Kết quả API mong đợi |
|---|---|
| `genuine` | Sau phần mặt: `pass` |
| `low_quality` | Sau phần mặt: `retry` |
| `voice_clone` | Sau phần mặt: `voice_challenge`; sau phần giọng: `review` |

`review` là trạng thái kết quả, không có bàn duyệt/nhân viên trong profile này.
`pass` không cấp tài khoản hoặc chứng nhận BBS. Không test đăng nhập lại/khôi phục
như đã hoàn thành: account enrollment tắt, guard account-bound vẫn chặn.

## 5. Bằng chứng và giới hạn

Probe HTTP qua HTTPS ngày 28/10 trên source API `54acaad`, `mock@0.1`: ba phiên
tổng hợp đi qua OTP, CCCD/confirm, media có chữ ký, signals, finalize và voice khi
cần; kết quả khớp bảng. Probe kiểm xác thực TLS, payload DB mã hóa và file media
có header mã hóa; route review/forensic trả 404, upload thiếu token bị từ chối.
Chỉ dùng ảnh/video/âm thanh tổng hợp, không phải kiểm thử camera Android. Kết quả
cục bộ được giữ trong `tmp/remote-android/smoke-results.json`, không chứa khóa,
token, OTP hoặc sinh trắc để commit.

CI build/unit test và probe HTTP không chứng minh độ chính xác AI hay trải nghiệm
thiết bị thật. Ghi nhận riêng sau khi người test xác nhận: model điện thoại,
phiên bản Android, source SHA APK, Tailscale/health, quyền camera/micro, từng
kịch bản và lỗi gặp phải. Không gửi log có token/OTP/CCCD lên issue.

## 6. Profile test mặt AI từng phần — 29/10

Người test đã báo đi hết luồng mock qua APK. Chuẩn bị lượt camera thật ngày
30/10 bằng các cờ opt-in **đã có**, không đổi app/API/contract hoặc mở guard:

| Thành phần | Trạng thái cấu hình trên laptop |
|---|---|
| Runtime API | `tmp/session-api-runtime`, CPU; bổ sung `cryptography==50.0.2` từ cache offline; dependency check passed |
| Kho test riêng | `tmp/remote-android-ai/`, ACL riêng, `.env.face`, `face.db`, `face-media/`; khóa khác kho mock |
| AI mặt | `SESSION_FACE_CHECKS=true`, `SESSION_FACE_MODELS=true`: FS-VFM-L, GenD, đo màu, mắt và quay đầu |
| Timeout / worker | 45 giây / 2 worker; app hiện có read timeout 60 giây |
| Tích hợp còn mô phỏng | `USE_MOCK_MODELS=true` cho OTP/CCCD, quality và CamProbe; voice models tắt |
| Đường riêng | Serve HTTPS trỏ loopback 8421; kho mock 8420 giữ làm dự phòng |

Health vẫn có `mock_models=true` vì đây là profile từng phần. Không sửa health
hoặc đổi thành `false` để làm giống toàn bộ chạy thật. `startup.json` cục bộ ghi
type/version 5 adapter đã nạp; probe HTTP đối chiếu version trong `module_results`
và kiểm payload mã hóa. Probe clip không mặt trả `review`, không thể thành pass.
FS-VFM/GenD đã forward trên tensor tổng hợp; chưa đo accuracy hoặc camera Android.

Mô hình mặt theo giao thức mới chưa hiệu chỉnh; **kết quả chưa đủ điều kiện xác
minh không được chuyển thành đạt**. OCR/LVFace, tạo tài khoản, BBS và consent API
chưa bật trong profile này. Chỉ test nội bộ có biết việc quay, dùng CCCD/QR tổng
hợp. Chưa phải protected profile hoặc đăng ký thật xuyên suốt.

Các helper **riêng trên laptop**, không nằm trong Git: `prepare.py` chỉ tạo lần
đầu; `start.py` giữ khóa cũ, kiểm ít nhất 3 GiB RAM trống rồi chạy `launch.py`;
`stop.py` đối chiếu command line trước khi dừng cây tiến trình đúng PID. Không
chạy lại prepare trên DB đã có. Sau restart Windows, từ gốc repo:

```powershell
& './.venv/Scripts/python.exe' './tmp/remote-android-ai/start.py'
# Chờ nạp model, kiểm http://127.0.0.1:8421/healthz trước khi test điện thoại.
```

`launch.py` yêu cầu Windows giữ hệ thống thức theo vòng đời tiến trình, không
đổi power plan. Khi API dừng yêu cầu này cũng kết thúc. Cắm sạc, giữ mạng, không
gập nắp hoặc chủ động Sleep. Nếu Serve đã được chuyển sang dự phòng 8420, sau
khi health 8421 ổn mới đổi lại bằng lệnh Serve trong mục 2 với cổng 8421.
Mỗi lần đổi kho server phải bắt đầu phiên Android mới; bearer cũ không dùng
được với kho/khóa mới. Khi dừng API AI bằng `stop.py`, Serve không tự đổi đích.

Giọng nói: NES2Net, CTC và SyncNet đã qua từng smoke test native bằng tín hiệu
tổng hợp trong runtime riêng. Qwen ASR bị resource monitor dừng vì thiếu RAM;
chưa đạt smoke test và không bật voice profile. Các probe riêng không chứng minh
đủ RAM khi chạy đồng thời hoặc luồng giọng Android hoạt động. Cần giải phóng RAM
và kiểm lại trước khi đưa giọng vào buổi test; không dùng kết quả mock thay thế.

Bằng chứng cục bộ: `tmp/remote-android/*-probe-resource.json`,
`face-activation-probe.json`; `tmp/remote-android-ai/startup.json`,
`http-probe-local.json`, `http-probe-https.json`, `readiness.json` và
`TEST-NGAY-MAI.txt`. Không có accuracy hoặc tuyên bố xác minh từ các probe này.
