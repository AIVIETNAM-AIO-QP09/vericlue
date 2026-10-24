# FLOW-05 — bàn giao identity lab, chờ tích hợp UI/UX

Theo yêu cầu người dùng, push code OCR/face matching và dọn thử nghiệm.
Nhánh `feat/FLOW-05-identity-lab`, base main a98098e. Nhánh FLOW-04-FLOW-05-head-and-match
đã là ancestor của main; không ghi đè phần LVFace hiện có của nhóm.

Tài liệu chính: `tools/identity_lab/HANDOFF.md` và README.
Gồm OCR/field detector, notebook Colab, face CLI/lab API, benchmark/calibration và tests.
Không thay contracts, production models, threshold, STATUS hoặc trạng thái FLOW-05:
chưa xong tích hợp/UI, chưa đáp ứng nghiệm thu production.

Giữ detector CCCD tự train, VietOCR pretrained, SCRFD10G/AdaFaceIR18. Không phát hành
trọng số adapter/IR101/ArcFace hoặc VinText candidate. VinText đã thử trên ba ảnh CCCD,
có regression; chi tiết không chứa dữ liệu nhận dạng trong HANDOFF.md.
Gói detector để người dùng upload kho model riêng, có SHA-256 và hướng dẫn đặt file.
Không commit model/dataset/ảnh/output cá nhân; notebook đã bỏ output.

Kiểm tra: 103 tests identity lab pass; Ruff check/format pass. Main production suite
không thuộc phạm vi thay đổi. FLOW-05 tiếp tục doing, chờ nhóm quyết định giao diện tích hợp.

Câu hỏi cho nhóm: giữ LVFace làm module production hay đánh giá AdaFace cùng giao thức
CCCD–selfie trước khi thay? Không thay model production chỉ theo kết quả lab.
