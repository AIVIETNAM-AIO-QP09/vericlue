# Bàn giao · VOICE-09 · Ngoc Quang+Codex · 2026-11-01 21:42

**Nhánh:** codex/VOICE-09-offline-integrity-coverage, dựa PR124/c154abf
**Trạng thái task sau phiên này:** review — chốt diagnostic/coverage; chưa có hiệu chỉnh hai lớp thật hoặc nghiệm thu điện thoại

## Đã xong
- Audit độc lập tái hiện9 lần report diagnostic ghi được vào3 kho env qua readiness/voice collect/face collect. Thêm shared diagnostic_output guard cho producer, chặn kho repo và MODELS_DIR/DATA_DIR/CALIBRATORS_DIR trước xử lý, trước model load/fit và kiểm lại trước ghi.
- Không đổi chủ ý session.fit_report xuất fitted calibrator vào output_dir được yêu cầu; regression xác nhận kho CALIBRATORS_DIR vẫn nhận fitted artifact đúng định dạng từ dữ liệu fixture tổng hợp.
- Dev thêm SoundFile/JiWER/RapidFuzz cùng bounds voice extra; lock không đổi phiên bản package hiện có. Bật18 fixture WAV +1 oracle thư viện từng skip, không cài Torch/model.
- Sau cài SoundFile,7 test cũ lỗi vì fake backend gọi runtime_identity thật cần Torch. Fixture đã cô lập runtime synthetic, production runtime giữ nguyên; nhóm audio/matching144 đạt.
- Sửa ghi chú research LTT lỗi thời và ghi rõ đầu vào cần nhóm cung cấp; dữ liệu TTS/VC chưa có, không bị xóa.

## Đang dở
<!-- file:dòng, việc gì còn dang dở -->
- Full suite/review/CI nhánh riêng đang thực hiện. Không dùng CI parent thay thế.
- Thiếu dữ liệu đủ quyền/crosswalk/protocol và fitted artifacts thật; metadata mặt còn thiếu strata/runtime/gate. Chưa có điện thoại, OTP mô phỏng; không đóng toàn luồng AI.

## Bước tiếp theo
<!-- Viết đủ rõ để người khác hoặc AI khác làm ngay, không cần hỏi lại -->
1. Nhóm gửi link/bundle dữ liệu có điều kiện sử dụng, nhãn và mã người/nguồn; mở quyền tài khoản nếu cần. Nếu có artifact PAD/GenD/giọng, gửi đường dẫn/config/commit/split/report.
2. AI kiểm và chuẩn hóa manifest/chia tập, chuẩn bị protocol rồi fit–LTT–test khi đủ điều kiện; nhóm không cần tự viết script/fit/buildAPK.
3. Nhóm chốt phạm vi demo và dữ kiện nguồn; có người thao tác Android thật để nghiệm thu ba luồng/consent. Maintainer review/gộp chuỗi Draft PR khi đồng ý; agent không merge main.

## Quyết định, lưu ý, bẫy
- Không thay thresholds/contracts/ADR/proposal/STATUS, mã số học/parity NES2Net, API/Android hoặc liveDB/media. Không reset/xóa WIP, model/media/tài khoản hay khởi động API cleanup.
- Report research không được ghi vào kho runtime; fitted calibrator output có chủ ý là loại khác, không áp guard diagnostic vào đó. Không đổi failclosed status error/degraded.

## Câu hỏi cho nhóm
<!-- Việc cần cả nhóm hoặc trưởng nhóm quyết. Trưởng nhóm gom vào STATUS.md -->
- Chưa thêm câu hỏi thiết kế mới. Cần nhóm hỗ trợ nguồn/quyền/data/phạm vi và thao tác vật lý; AI tiếp tục phần kỹ thuật sau khi có đầu vào. Xem ghi chú research để chuyển yêu cầu cho người giữ dữ liệu/model.

## Test đã chạy
<!-- lệnh + kết quả thật -->
- RED17 ca guard thực tế (sau sửa lỗi tên class trong fixture), rồi56 test producer/guard đạt; thêm6 ca normalize repo storage.
- Nhóm WAV/align/matching:144 đạt, không skip. Nhóm guard/utterance/NES/align/matching/session/readiness/candidates/LTT: **354 passed**,38.26s, không skip.
- Ruff sạch871file; uv lock --check sạch; diff --check sạch. Full suite/review/smoke/CI sẽ ghi bổ sung sau xác nhận.
