# Trình diễn AI thật với ngưỡng thủ công

## Cấu hình local được yêu cầu ngày 03/11: WeChat và preset cố định

Người dùng đã cho phép bật `MANUAL_FULL_DEMO=true` cùng
`MANUAL_DEMO_PRESET=phone-demo-fixed-v1` và đổi bộ đọc QR server sang WeChat.
Đây là thay đổi vận hành riêng, không tự thay cấu hình của người kéo repo.
Sáu ngưỡng lấy từ đối tượng preset hiện có; không sửa `thresholds.yaml`,
không tạo artifact hiệu chỉnh. Hash policy:
`ebe8835e33f9e0cdc187bf450a0793b105084d7258509455e71be0923294fed9`.

Trên máy `D:/Projects/Data4Life`, runtime thực tế là `tmp/vericlue-server`,
Python API `tmp/session-api-runtime/Scripts/python.exe`. Không dùng đường dẫn
gói `D:/vericlue/...` lịch sử bên dưới. Sao lưu `.env` riêng trước khi đổi;
giữ nguyên DB, media, khóa và phiên cũ. Kiểm tra không còn tài khoản hiệu lực
trước khi chuyển policy. Phiên cũ không được đổi nhãn: bắt đầu lượt mới.

WeChat dùng bốn file đã pin SHA-256 và OpenCV contrib (extra `face`/`cuda`):

```powershell
uv sync --all-packages --extra face
uv run python scripts/download_wechat_qr.py --models-dir <MODELS_DIR>
```

Đặt `IDENTITY_QR_BACKEND=wechat`; ZXing-C++ vẫn kiểm cùng ảnh, SCRFD vẫn kiểm
chân dung ảnh gốc. Hai decoder không được tự bỏ QR xung đột. Thiếu/sai trọng
số hoặc lỗi backend làm bước đọc thẻ chưa sẵn sàng. Chỉ có `opencv` được chọn
tường minh mới dùng decoder cũ. Tránh cài nhiều biến thể package OpenCV vào
cùng môi trường vì chúng cùng cung cấp `cv2`.

Cấu hình full demo ở dưới vẫn bắt buộc. Local chọn Qwen 0.6B có sẵn,
`VOICE_RUNTIME_PYTHON` và `VOICE_SPOOF_PYTHON` cùng trỏ executable riêng trong
`tmp/av-lab-runtime`; hai worker vẫn là hai tiến trình độc lập. Nạp thử thật
AntiDeepfake/Qwen/CTC/SyncNet trước khi khởi động API. Cho phép tối đa 300 giây
nạp worker, 600 giây khởi động API; inference vẫn tối đa 90 giây và timeout
không được coi là đạt. Không nới guard RAM 3 GiB của launcher.

Sau khi API sẵn sàng, kiểm profile đang chạy bằng phiên tổng hợp riêng:

```powershell
tmp/session-api-runtime/Scripts/python.exe -X utf8 scripts/smoke_android_stage_a.py --run-synthetic --expect-manual-preset
```

Smoke xác nhận mode/hash từ response API, consent, OTP và QR thật, đồng thời
từ chối thẻ tổng hợp thiếu chân dung; tự rút consent phiên test. Đây không
phải nghiệm thu xác minh sinh trắc đầu cuối hoặc đo độ nhạy trên CCCD thật.
Không cần đổi APK để chọn decoder server; điện thoại vẫn cần thử lại lượt mới.

## Bản chuẩn bị thử điện thoại ngày 02/11/2026

APP-01/FLOW-04/SEC-09: source `7904d7092baaa338f06351688286c1f4dc440ea0`
hoàn thiện `MANUAL_FULL_DEMO` cho đăng ký, đăng nhập lại và khôi phục tài khoản
thử nghiệm. Phần triển khai trước khi có điện thoại đã sẵn sàng; **chưa nghiệm
thu ba luồng trên thiết bị thật**. Không phải cấu hình sản phẩm đã hiệu chỉnh.

Gói riêng trên laptop: `D:/vericlue/tmp/phone-demo-2026-11-02/`. Gói dùng DB,
media và khóa demo riêng; không khởi động launcher cũ trên DB/media gốc.
Các helper của gói là `START-DEMO.cmd`, `STATUS-DEMO.cmd`, `STOP-DEMO.cmd` và
`CONNECT-PHONE.cmd`; đọc checklist/build-info đi kèm trước khi chạy. API ở
`http://127.0.0.1:8421`, điện thoại nối bằng `adb reverse tcp:8421 tcp:8421`.
Không uninstall hoặc clear dữ liệu để đổi bản cài.

APK 0.3.0 của gói dùng `signedMedia=true`, `liveByDefault=true`,
`presenceTrace=false`, cùng khóa debug laptop. Fingerprint chứng chỉ SHA-256:
`822e5e44be42ce365f186a6c73af5bf36eb262c3cc65011b4269363adc695c75`;
chữ ký APK v2=true, v3=false. Đây không phải khóa phát hành được pin trong repo.
Đối chiếu signer bản đã cài trước khi dùng `adb install -r`.

Bằng chứng tại thời điểm cập nhật: preload native AntiDeepfake, Qwen, CTC và
SyncNet đã qua; full Python trên source trên đạt 4998 test, bỏ qua 100 test.
Smoke frozen-source đã chạy AntiDeepfake/Qwen/CTC trên một mẫu `calib_fit`
chọn sẵn, không fit hoặc chọn ngưỡng; CTC vẫn `degraded/unclear` diagnostic.
SyncNet forward tensor audio/video cho embedding hữu hạn, chưa phải video
nói thật. API/DB0011 khỏe, phiên đúng mode/hash, thiếu consent bị chặn và không
cấp receipt. Xem [bằng chứng smoke](../status/results/APP-01-phone-demo-preflight-2026-11-01.json).
CCCD/mặt/giọng/Keystore và ba luồng trên
điện thoại đều `not_run` cho gói mới. Không suy accuracy từ các test phần mềm.

## Policy `manual-full-demo-v2`

| Cấu hình | Mặc định | So sánh |
|---|---:|---|
| `MANUAL_DEMO_PAD_MAX` | 0.50 | Điểm thô FS-VFM không vượt mức này |
| `MANUAL_DEMO_GEND_MAX` | 0.50 | Điểm thô GenD chính diện không vượt mức này |
| `MANUAL_DEMO_MATCH_MIN` | 0.30 | Cosine tham chiếu–chính diện tối thiểu |
| `MANUAL_DEMO_CONSISTENCY_MIN` | 0.30 | Cosine thấp nhất giữa ba góc tối thiểu |
| `MANUAL_DEMO_SPOOF_MAX` | 0.50 | Điểm thô AntiDeepfake không vượt mức này |
| `MANUAL_DEMO_LIPSYNC_MAX` | 0.50 | Điểm thô SyncNet không vượt mức này |

Đây là các mốc minh họa thủ công, không fit/chọn trên VIVOS, DNU hoặc tập test,
không chứng minh FAR/FRR hay chất lượng chống giả mạo. Không tự nới theo lượt
người thử. Mọi tham số nằm trong hash policy v2; với giá trị mặc định, hash là
`2f7e8becee1dff4d23831acd791adc449af3e12c2e0f314501930b1109b25ca8`.
Không sửa `thresholds.yaml` hoặc tạo artifact/provenance giả để mở chốt.

Kết quả manual giữ `prob_attack=null`, `calibrated=false`, marker
`manual_demo=true`, `demo_policy_id` và hậu tố version
`+manual-demo-<policy_id[:16]>`. Policy v2 làm thay đổi hash so với bản demo cũ;
phiên/tài khoản khác mode hoặc policy bị từ chối, không chuyển đổi ngầm.

## Preset cố định `phone-demo-fixed-v1` (03/11)

Chỉ bật bằng `MANUAL_DEMO_PRESET=phone-demo-fixed-v1` trong cấu hình đã có
`MANUAL_FULL_DEMO=true`. Không bật được ở đường chuẩn hoặc `MANUAL_FACE_DEMO`.
Nếu không đặt preset, sáu cấu hình thủ công và mặc định ở bảng trên giữ nguyên.

| Tham số | Giá trị cố định |
|---|---:|
| PAD tối đa | 0.70 |
| GenD chính diện tối đa | 0.95 |
| AntiDeepfake tối đa | 0.70 |
| SyncNet tối đa | 0.60 |
| Cosine nhận dạng tối thiểu | 0.30 |
| Cosine nhất quán tối thiểu | 0.30 |

Đây là lựa chọn kỹ thuật chưa hiệu chỉnh để nới cổng điểm thô cho demo; không
chọn từ điểm lượt điện thoại, không fit tập test, không chứng minh giảm báo
nhầm hoặc FAR/FRR. Tăng ngưỡng tấn công có thể tăng bỏ lọt. SyncNet dùng điểm
`max(1-confidence, abs(offset_ms)/500)`: mốc 0.60 yêu cầu confidence ít nhất
0.40 và độ lệch không quá 300 ms. Nhận dạng/nhất quán giữ 0.30; ASR vẫn yêu cầu
WER không quá 0.30 và độ giống bỏ dấu ít nhất 0.90.

Một đối tượng bất biến trong `common/manual_demo.py` cấp sáu giá trị cho API
và worker. Hash policy v2 tiếp tục tính trên **giá trị thực dùng**, không đổi
nhãn thành đã hiệu chỉnh. Khi bật preset, bỏ các biến `MANUAL_DEMO_*_MAX` và
`MANUAL_DEMO_*_MIN` cũ hoặc đặt đúng các giá trị trên: cấu hình truyền tường
minh khác preset bị từ chối lúc khởi động; mặc định chưa truyền không gây
xung đột. Worker, kết quả và phiên vẫn bị ràng buộc cùng hash/version.

Preset không bỏ kiểm tra thiếu trọng số/bằng chứng, lỗi/degraded/timeout,
splice, câu đọc, chất lượng, quay đầu/ánh mắt, nhận dạng, continuity hoặc consent.
Model thật vẫn chạy; `prob_attack=null`, `calibrated=false` và banner demo giữ nguyên.

**Chuyển policy:** tài khoản/phiên cũ khác hash không được đổi nhãn hoặc tự
chuyển. CCCD của tài khoản chưa hết hạn vẫn bị ràng buộc duy nhất: đăng ký
lại ngay sẽ bị từ chối, dù tài khoản cũ không dùng được với policy mới.
Để chuyển mà không đặt lại dữ liệu, chuẩn bị bản mới trước và chỉ kích hoạt
sau khi tài khoản policy cũ hết TTL 24 giờ; tạo phiên mới để đăng ký lại.
Quy trình hết hạn sẵn có giải phóng ràng buộc CCCD. Không tự xóa tài khoản,
receipt/khóa trên app hoặc sửa thời hạn để né ràng buộc. Thay preset là đổi
cấu hình vận hành riêng; thêm code/runbook không tự kích hoạt server đang chạy.

## Cấu hình full demo

```dotenv
MANUAL_FULL_DEMO=true
MANUAL_FACE_DEMO=false
SECURITY_PROFILE=synthetic
PRODUCT_MODE=ekyc
USE_MOCK_MODELS=true
SIMULATED_OTP=true
ROUTER_PROFILE=mvp
SESSION_FACE_MODELS=true
SESSION_FACE_CHECKS=true
SESSION_VOICE_MODELS=true
IDENTITY_CARD_ENABLED=true
IDENTITY_FACE_FROM_VIDEO=true
IDENTITY_CONSISTENCY_REQUIRED=true
IDENTITY_VOICE_CONTINUITY=true
ACCOUNT_ENROLLMENT=true
PRIVATE_CREDENTIALS=false
RESULT_SIGNING_KEY_FILE=
VOICE_WORKER_STARTUP_TIMEOUT_SECONDS=180
```

Bổ sung đường dẫn model/runtime và khóa riêng qua cấu hình private của gói,
không chép bí mật vào repo. `VOICE_SPOOF_PYTHON` cần runtime tương thích
AntiDeepfake; `VOICE_RUNTIME_PYTHON` phục vụ Qwen/CTC/SyncNet. Startup timeout
riêng mặc định 180 giây (tối đa 600); `SESSION_MODEL_TIMEOUT_SECONDS` vẫn là
hạn inference hiện có, không dùng preload để báo sẵn sàng giả.

`USE_MOCK_MODELS=true` ở đây giữ nền OTP mô phỏng; các opt-in chọn model thật,
lỗi không fallback thành mock pass. OTP là mã ngẫu nhiên của lượt gửi được
hiển thị từ `simulated_sms`, **không mặc định `123456`**. Profile protected,
credential và signed result cho bên tích hợp không được mở bởi chế độ này.

## Giọng nói và chốt tài khoản

**APP-03 (03/11):** `MANUAL_DEMO_CONTENT_BACKEND=qwen06` là mặc định như cũ.
Chỉ khi `MANUAL_FULL_DEMO=true` mới được chọn `qwen17`; thiếu hoặc sai artifact
không fallback về 0.6. Bản 1.7B cố định revision
`bcd2b5b7f32b480ab5790554cfa8347f246a14f3`, wrapper
`cpu-fp32-content-v2-assistant-prefix`, thư mục riêng
`MODELS_DIR/qwen3-asr-17b-hf`; không ghi đè 0.6B hoặc đọc config override của nó.
Pin byte và kiểm thư mục không được thoát MODELS_DIR qua symlink/junction.

Hash policy vẫn biểu diễn đúng sáu ngưỡng bên trên. ASR được ràng buộc riêng:
worker preload/hello/request/reply và kết quả phải cùng phiên bản; phiên mới
lưu phiên bản ASR trong snapshot mã hóa do server tạo. Bản 1.7 từ chối pin
thiếu/sai/của 0.6, không tự backfill phiên cũ. Rollback sang 0.6 cũng không nhận
phiên đã pin 1.7; cần bắt đầu phiên mới. Chỉ 0.6 giữ tương thích phiên lịch sử
chưa có pin. Các endpoint công khai và ngưỡng không thêm quyền chọn mô hình
cho người dùng. SessionFlow và AccountStore kiểm pin/result khi cần giọng.

Tài khoản cũ giữ template/version mặt, consent, khóa, mode và policy hiện có;
không migration hoặc đổi nhãn. Khôi phục vẫn cần toàn bộ chốt mới đạt.
18 mẫu/18 người DNU calib_fit cho kết quả khả quan với 1.7, nhưng CPU chậm
hơn khoảng 2,5 lần, trọng số FP32 khoảng 8,15 GB. Trước khi bật cần preload
thật toàn stack và kiểm ngân sách RAM/timeout. Fit không thay nghiệm thu
điện thoại hay đánh giá spoof/lipsync. Xem bàn giao `2026-11-03-0128` và
[hướng dẫn đo ASR](../../ml/src/vericlue_ml/eval/DNU_ASR_FIT.md).

- Worker manual dùng raw **AntiDeepfake** (`voice01-v1-vad1-ln-win4-hop1-tail-meanlogits`)
  và raw **SyncNet** (`voice05-v3-u8resize`), giữ revision backend đầy đủ trước hậu tố
  policy. NES2Net ở đường tiêu chuẩn vẫn là diagnostic; không đổi
  `degraded/error` thành `ok/pass`, không dùng cửa sổ NES hoặc probability chung
  làm bằng chứng đạt cho manual full demo.
- Client/worker đóng băng policy khi tạo, handshake/request/reply gắn mode và
  hash. Worker manual chỉ báo ready sau khi preload đúng backend; metadata từ
  request người dân không chọn mode hoặc ngưỡng.
- Chỉ raw `status=ok`, đúng module/version, điểm hữu hạn và bằng chứng hợp lệ mới
  được chấm ngưỡng. AntiDeepfake cần đủ cửa sổ, logits/score và coverage hợp lệ.
  SyncNet cần `splice_flags=0` đúng kiểu, offset/confidence hợp lệ; giữ
  `hardware_clock_verified=false`. Thiếu bằng chứng, mock, diagnostic, lỗi,
  timeout hoặc version/policy sai không được đạt.
- Khớp môi bắt buộc cho recovery và onboarding có bước giọng khi ghi danh.
  SessionFlow và AccountStore kiểm riêng spoof/lipsync đúng policy trước pass
  hoặc receipt. Continuity dùng policy manual thay artifact cũ được cấu hình;
  đường chuẩn vẫn yêu cầu calibrator đúng protocol.
- Phiên và tài khoản lưu mode/hash; onboarding trùng CCCD bị từ chối, không tự
  hủy tài khoản hiện hữu. Consent xử lý phiên và consent lưu mẫu mã hóa 24 giờ
  là hai lựa chọn chủ động riêng. Không đủ receipt/consent thì không ghi danh.
  Android giữ receipt/khóa cũ khi lỗi hoặc mode/policy không khớp; metadata cũ
  chưa biết không được đoán thành standard/manual.

Android mở API thật mặc định trong APK giao, không rơi sang kết quả dựng sẵn
khi API lỗi. Nhãn **“Demo · Ngưỡng chưa hiệu chỉnh”** được giữ ở màn kết quả,
mở tài khoản và tài khoản khôi phục từ lưu trữ. Gallery offline là bản xem trước.
Không hiện điểm số cho người dân. Màn thành công chỉ xuất hiện khi đủ điều kiện;
không bảo đảm mọi người/lượt quay đều được chấp nhận.

## Lịch sử: `MANUAL_FACE_DEMO` ngày 31/10

Đây là chế độ chỉ trình diễn onboarding phần mặt, khác `MANUAL_FULL_DEMO` ở
trên. Cấu hình dùng `MANUAL_FACE_DEMO=true`, `MANUAL_FULL_DEMO=false`,
`IDENTITY_VOICE_CONTINUITY=false`, `ACCOUNT_ENROLLMENT=false`; vẫn yêu cầu
synthetic+mvp+ekyc, model mặt thật và OTP mô phỏng. Không mở đăng nhập lại,
khôi phục, receipt tài khoản, credential hoặc signed result.

Phiên mang `evaluation_mode=manual_demo`. Khi mọi cổng mặt đạt cùng policy và
CCCD đã xác nhận, API giữ `status=review` và thêm `demo_complete=true` để app
mở route trình diễn có nhãn. Tiêu đề “Xác minh thành công” ở route đó không
phải cấp tài khoản. Hash hiện tại được tính từ đối tượng policy v2 chung;
không tái sử dụng phiên/hash của bản cũ.

Launcher `D:/vericlue/tmp/full-demo-setup/VeriClue.cmd` và APK tại
`full-demo-setup/apk/` là cấu hình/lượt giao lịch sử, không phải gói thử ngày
02/11. Giữ nguyên dữ liệu/khóa cũ; không gọi helper apply/restore cũ để thay
cấu hình gói cô lập mới.

## Nghiệm thu còn lại

Smoke suy luận/API và dừng/mở lại server đã qua. Tiếp theo thử đăng ký → đăng
nhập lại → khôi phục trên điện thoại; ghi cả lượt bị từ chối, đổi policy, sai câu/không khớp
môi, mất mạng và restart. Chỉ ghi luồng thực sự đã chạy; các bước chưa chạy
đánh dấu `not_run`. Giữ tài khoản/khóa cũ khi thao tác lỗi.

Khi quay video, nói rõ “Model chạy thật, OTP mô phỏng, ngưỡng thử nghiệm chưa
hiệu chỉnh” và giữ nhãn demo trong khung hình. Chế độ chuẩn vẫn cần dữ liệu
có quyền sử dụng, chia theo người, artifact đúng protocol và đánh giá riêng;
xem [hiệu chỉnh phiên](session-face-calibration.md) và
[nghiệm thu tiếp theo](real-ekyc-next-steps.md).
