# Trình diễn AI khuôn mặt với ngưỡng thủ công

APP-01/FLOW-04, theo yêu cầu người dùng ngày31/10: một cấu hình thử nghiệm để
quay video nộp bài trong khi chưa có artifact hiệu chỉnh. Chỉ hỗ trợ onboarding
phần mặt, dùng các model thật; OTP vẫn mô phỏng. Không mở sinh trắc tài khoản,
đăng nhập lại/khôi phục, continuity giọng, chứng nhận hay kết quả ký cho bên tích hợp.

## Ngưỡng và ý nghĩa

| Cấu hình | Khởi đầu | So sánh |
|---|---:|---|
| MANUAL_DEMO_PAD_MAX | 0.50 | Điểm thô FS-VFM không vượt mức này |
| MANUAL_DEMO_GEND_MAX | 0.50 | Điểm thô GenD không vượt mức này |
| MANUAL_DEMO_MATCH_MIN | 0.30 | Cosine tham chiếu–chính diện tối thiểu |
| MANUAL_DEMO_CONSISTENCY_MIN | 0.30 | Cosine thấp nhất giữa ba góc tối thiểu |

Hai mức0.50 là điểm cắt thử nghiệm trên đầu ra phân loại nhị phân, không phải
xác suất đã hiệu chỉnh. Cosine dùng thang đo khác. Các giá trị do người dùng
chọn cách làm thủ công, chưa được đo/chọn trên dữ liệu có nhãn và không chứng
minh độ chính xác, FAR/FRR hay chống tấn công. Không sửa thresholds.yaml, không
tạo artifact có provenance/dataset/số mẫu giả. Không tự nới theo lượt người thử.

## Điều kiện cấu hình

MANUAL_FACE_DEMO mặc định false. Khi bật phải đồng thời có:

```dotenv
MANUAL_FACE_DEMO=true
SECURITY_PROFILE=synthetic
PRODUCT_MODE=ekyc
USE_MOCK_MODELS=true
ROUTER_PROFILE=mvp
SESSION_FACE_MODELS=true
SESSION_FACE_CHECKS=true
IDENTITY_CARD_ENABLED=true
IDENTITY_FACE_FROM_VIDEO=true
IDENTITY_CONSISTENCY_REQUIRED=true
IDENTITY_VOICE_CONTINUITY=false
ACCOUNT_ENROLLMENT=false
PRIVATE_CREDENTIALS=false
RESULT_SIGNING_KEY_FILE=
```

USE_MOCK_MODELS ở đây giữ nền OTP mô phỏng. Orchestrator vẫn chọn SCRFD,
CamProbe, gaze/head, FS-VFM, GenD và LVFace thật qua các opt-in nêu trên; lỗi
không fallback sang mock. Profile full có ChromaPulse chưa đủ điều kiện nên
không được bật cùng manual demo. Sản phẩm protected không cho dùng cấu hình này.

SessionAttackDetector/FaceMatchDetector nhận policy riêng: chỉ tính gate thủ
công sau khi suy luận hợp lệ; prob_attack vẫn null, calibrated=false và version
có hậu tố policy riêng. Mất mặt/nhiều mặt, decode/timeout/integrity/error/degraded
vẫn không đủ điều kiện. Giữ lịch server, kiểm mắt/quay đầu, ký media và chọn/
kiểm lại đúng pixel video. Chính sách manual không thay các kiểm tra đó.

## Phản hồi và màn hình

Phiên ghi evaluation_mode=manual_demo và SHA256 demo_policy_id của bốn ngưỡng.
Đổi cấu hình/bật tắt mode phải bắt đầu phiên mới; phiên cũ bị chặn. Response
chuẩn giữ nguyên dạng cũ khi không bật manual.

Chỉ khi tất cả model bắt buộc ok/pass, cùng policy và CCCD đã xác nhận, API mới
trả demo_complete=true. Status API vẫn review, không phải pass. Bộ marker bổ
sung là hợp đồng riêng cho trình diễn; client cũ vẫn xử lý là chưa xác minh.
Không cấp account receipt, khóa tài khoản, chứng nhận hay signed result.

Android kiểm mode/hash giữa tạo phiên và finalize, hiển thị thông báo trước
ghi hình. Theo yêu cầu người dùng, màn cuối có tiêu đề **“Xác minh thành công”**,
nhãn rõ **“Demo · Ngưỡng chưa hiệu chỉnh”** và giải thích không dùng kết quả để
mở tài khoản/xác minh thực tế. Đây là route riêng, không đi qua lưu tài khoản
thật. Camera được unbind trước khi mở màn. Không hiện điểm số cho người dân.

## Laptop hiện tại

Launcher: D:\vericlue\tmp\full-demo-setup\VeriClue.cmd.
Helper local configure_manual_face_demo.py nằm cùng thư mục launcher:
--check kiểm cấu hình mà chưa áp dụng; --apply ghi cấu hình; --restore phục hồi
các trường đã đổi. Helper chỉ sao lưu giá trị cấu hình không bí mật, giữ khóa/DB
và cập nhật .env nguyên tử, không in bí mật. Stop server trước khi apply/restore,
sau đó start và kiểm /healthz. Helper/data/mode backup không commit.

APK giao tại D:\vericlue\tmp\full-demo-setup\apk\VeriClue-demo-debug.apk;
cài đè -r, không gỡ/xóa dữ liệu. Điện thoại mới Samsung A04 đã pair; cổng kết nối
Wi-Fi có thể đổi sau này, không dùng lại mã pairing cũ. Sau reconnect dùng
adb reverse tcp:8421 tcp:8421 trên đúng serial của máy mới.

## Quay video và hoàn thiện tiếp

Nói rõ trong video: “Model chạy thật, OTP mô phỏng, ngưỡng thử nghiệm chưa hiệu
chỉnh”. Giữ nhãn demo trong khung hình. Màn thành công chỉ xuất hiện khi chấm
đủ điều kiện; không có bảo đảm mọi người/lượt quay sẽ được chấp nhận.

Hoàn thiện chế độ chuẩn cần dữ liệu có nhãn/chia theo người, artifact PAD/GenD
đúng protocol, ngưỡng match/consistency/continuity phù hợp, quyền lưu mẫu SEC-09,
tích hợp tài khoản và nghiệm thu cả mẫu đạt/lỗi/không hợp lệ. Xem
[hiệu chỉnh phiên](session-face-calibration.md). Không gọi số liệu test tổng
hợp hoặc một vài lượt dùng thử là accuracy thực tế.
