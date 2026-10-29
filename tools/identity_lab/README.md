# OCR CCCD và face matching — công cụ thử nghiệm trong repo

## Luồng app hiện tại: một server, QR-only (APP-08)

Bộ đọc nằm trong `services/api/.../services/card_scanner.py`, được ApplicationState
giữ và dùng lại qua `IdentityRuntime`. QR dùng ZXing-C++/OpenCV; SCRFD dùng chung
session với các module mặt theo model/device. Không có bridge HTTP/cổng QR riêng.
`qr_scanner.py` và `card_scanner.py` trong tools chỉ là import tương thích lịch sử.
Không dùng OCR cho luồng app; xem [demo một bản](../../docs/runbooks/vericlue-demo.md).

Các phần OCR bên dưới là công cụ nghiên cứu lịch sử, không nằm trong luồng app.

**Bắt đầu tại [HANDOFF.md](HANDOFF.md):** bản được giữ lại, checkpoint cần chia sẻ,
kết quả thử VinText và ranh giới tích hợp UI/UX. Các thí nghiệm bên dưới là lịch sử
phát triển, không phải tất cả đều được chọn làm mặc định.

## Face matching

API xác minh hiện dùng SCRFD + LVFace-B trực tiếp trong orchestrator, không gọi
các endpoint face của lab này. Lab tiếp tục cung cấp QR/OCR; các thử nghiệm AdaFace
bên dưới được giữ để tái lập, không phải backend so CCCD–selfie đang tích hợp.
Xem [hướng dẫn tích hợp](../../docs/runbooks/identity-integration.md).

So sánh model bằng dữ liệu ngoài, giữ ảnh cá nhân chỉ để test:
[FACE_ROBUSTNESS.md](FACE_ROBUSTNESS.md). Có CLI khóa cấu hình trước khi đọc ảnh test.

Xem [FACE_MATCHING.md](FACE_MATCHING.md): pipeline SCRFD-10G + AdaFace-IR18,
CLI `face_matching.py`, developer API `/dev/v2/face-match`, kiểm tra LFW 1000 cặp.
Chưa có ngưỡng CCCD/selfie, không trả pass hay phần trăm danh tính; có retry cho ảnh
không phù hợp và debug căn chỉnh mặt opt-in. Pipeline OCR giữ nguyên.

## Cải thiện tổng quát trên bộ dữ liệu

Xem [quy trình recognition](RECOGNITION_WORKFLOW.md): đã tạo 5.996 crop / 668 ảnh CCCD,
chạy hai recognizer trên 100 crop train và có giao diện duyệt transcript localhost.
Gợi ý OCR tách khỏi nhãn chuẩn; đánh giá CER/exact match theo trường và xuất dữ liệu
VietOCR chỉ khi có nhãn người duyệt. Chưa có accuracy tổng quát hoặc model recognition
fine-tuned. Các split gốc chưa xác minh theo người; không dùng báo cáo chính thức.
Thử nghiệm hai recognizer giữ nguyên pipeline API hiện tại.

## Thử checkpoint detector đã train trên ảnh tại máy

### Đọc lại crop (bản cải thiện)

`try_card_detector.py` nay dùng `field_recognition.py`: giữ crop gốc, thêm biên nhỏ
theo chiều cao dòng (ngang 25%, dọc 8%, chặn ở mép ảnh), thử grayscale/autocontrast
và padding lặp pixel biên. Lưu 7 ảnh biến thể, nội dung, confidence và tọa độ nguồn
trong `readings`. Không tự chỉnh nghiêng khi chưa có bằng chứng góc; thử xoay +/-2 độ
đã làm giảm chất lượng trong lượt probe nên không đưa vào pipeline cuối.

Ngày phải khớp định dạng và có thật trong lịch; số CCCD phải đủ 12 chữ số.
Nếu bản gốc sai định dạng, chỉ đề xuất `text` khác khi >=2 biến thể confidence>=0.6
cùng giá trị và dẫn đầu duy nhất. Nếu không đủ, `text=null`, giữ `original_text`.
Ngưỡng là heuristic chưa hiệu chỉnh, không là xác suất chính xác. Trường chữ tự do
giữ bản gốc; phương án nhiều phiếu ở `suggested_text` chỉ để người kiểm tra.
Ngay cả đa số cũng có thể làm mất dấu đang đúng. Tất cả vẫn `status=review`,
`document_status=review`, `identity_verified=false`; không tự xác minh CCCD.

Kết quả `outputs/cccd_detector_trial_03`: ngày hết hạn đọc lại đúng trên cả hai ảnh;
giữ nguyên dấu đúng của địa chỉ dòng hai. Ảnh đầu có gợi ý sửa dấu quê quán đúng,
nhưng gợi ý ở ảnh khác có thể sai. i/1 ở dòng địa chỉ đầu vẫn chưa sửa được.
Thời gian đo lượt này 8.72/14.30 giây CPU (không tính nạp model), chậm hơn bản một crop.
Đây chỉ là hồi quy hai ảnh phát triển; không phải tập test độc lập. Cần crop/transcript
chuẩn và fine-tune recognition để tiếp tục, không tuyên bố hết lỗi.

Đặt checkpoint tự train ở `models/cccd_detector/best.pt`. Chạy từ repo root:

```powershell
& ..\output\vericlue_identity_lab\.venv\Scripts\python.exe tools/identity_lab/try_card_detector.py data/images/test_ocr/anh_cccd.jfif data/images/test_ocr/anh_cccd_1.jfif --checkpoint models/cccd_detector/best.pt --out outputs/cccd_detector_trial_04 --vietocr-models ../output/vericlue_identity_lab/models/vietocr
```

Mỗi ảnh có thư mục riêng với `overlay.jpg`, crop PNG, `result.json` (box, điểm detector,
chữ và điểm VietOCR). Thư mục output phải mới/trống để tránh trộn kết quả cũ.
Bỏ `--vietocr-models` nếu chỉ muốn kiểm detector. Chạy CPU, không cần GPU.
Model nạp strict với weights_only; không tự tải trọng số detector khác.
Chưa thay pipeline API hiện tại; đây là phép thử riêng, không xác minh danh tính.

Lượt chạy 23/10/2026: checkpoint epoch 15, hai ảnh phát triển đều cho 9 box ở score>=0.5.
VietOCR pretrained đọc đúng các trường chính khi đối chiếu trực quan nhưng còn sai
ngày hết hạn (`02/0712031`), i/1 trong địa chỉ, dấu địa danh ở một ảnh. Một số box sát/cắt
mép ký tự. `origin_place1` vắng trong cả hai ảnh có quê quán một dòng; không mặc định là lỗi.
Thời gian CPU detector+recognition khoảng 2.30 và 1.89 giây (không tính nạp model).
Đây không phải benchmark và không chứng minh chính xác 99.25% OCR.

## Fine-tune trên Google Colab

Mở [finetune_cccd_detector_colab.ipynb](finetune_cccd_detector_colab.ipynb) bằng
Google Colab → File → Upload notebook. Bật Runtime → Change runtime type → T4 GPU.
Chạy `SMOKE=True` trước. Notebook độc lập, không cần clone repo/token GitHub;
tự tải dataset Kaggle bản v1, kiểm SHA-256, lưu checkpoint vào
`MyDrive/vericlue_ocr/runs/`. Cho phép mount Drive khi Colab yêu cầu.

Đây là **fine-tune detector vùng thông tin** (Faster R-CNN + MobileNetV3, 10 lớp),
chưa fine-tune VietOCR. Chọn backbone Torchvision để dùng trực tiếp trong Python,
không thêm code YOLO có giấy phép xung đột với quy tắc repo. Định dạng nhãn YOLO
không bắt buộc phải train bằng YOLO. Dùng input 640 thay vì 320 để giữ thêm chi tiết chữ.

Kiểm tra thực tế dataset v1 ngày 23/10/2026:

- 1.722 ảnh; train/valid/test gốc: 1.325/221/176; tất cả 640×640.
- 668 ảnh có nhãn `cccd`: 493/115/60. Đây là ứng viên theo nhãn, cần kiểm tra loại thẻ thực tế.
- Nhãn trộn box và polygon: đã chuyển 2.040 polygon thành box bao ngoài,
  giữ polygon gốc trong manifest. Không còn lỗi định dạng sau chuyển đổi.
- 8 nhóm pixel trùng xuyên tập; 88 nhóm tên nguồn trùng xuyên tập cần rà soát
  (tên trùng không chứng minh cùng người). Chưa xác nhận chia tập theo người.

**Chạy tự động (mới):** đặt `SMOKE=False`, `AUTO_GROUP=True`, chạy lại notebook mới.
EasyOCR 1.7.2 đọc vùng `id` đã có nhãn (không cần detector mới); 2 biến thể phải
cùng 12 chữ số và confidence >=0.85. Không ép alphabet số hay sửa O/0.
Đây là heuristic, hai lần đọc cùng model không xác minh độc lập.
Gom cùng số, lan truyền qua ảnh trùng pixel; loại ảnh không chắc hoặc xung đột.
Tự ghi `groups_auto.csv`, `auto_group_report.json`, `auto_group_excluded.json` và cache
vào `audit_v1`; giữ nguyên groups.csv thủ công. Mã nhóm dùng HMAC, khóa nằm trên Drive,
không lưu số CCCD raw trong cache/log. Không chia sẻ khóa/crop/checkpoint công khai.
Run tự động mặc định `detector_auto_v1`. Chạy lại dùng cache và checkpoint.
Nếu ít hơn 10 nhóm thì dừng vì dữ liệu chưa đủ cho quy trình chia tập này.
**Nhóm tự động chưa được xác minh theo người**; chỉ đo trên tập con đọc được, có thể
còn rò rỉ danh tính do OCR sai. Không dùng metrics này như benchmark chính thức.
Crop queue mới nằm ở `runs/<RUN_NAME>/recognition_queue/`.
Logic tự động có unit tests; chưa chạy nhận dạng EasyOCR thật trên toàn dataset/Colab.

**Chế độ thủ công (`AUTO_GROUP=False`):** điền `group_id` trong `MyDrive/vericlue_ocr/audit_v1/groups.csv`:
cùng người, kể cả nhiều ảnh/thẻ, dùng cùng mã ẩn danh. Kiểm cả ảnh khác tên và khác pixel.
Sau đó đặt `SMOKE=False`, dùng tên run mới và chạy lại. Notebook chia theo nhóm,
giữ test riêng; không dùng test để chọn model. Không tự tạo danh tính từ filename.
Nếu chưa có nhóm được điền, chế độ thủ công dừng trước full training.

Mất phiên Colab: chạy lại notebook, giữ cấu hình và RUN_NAME, `RESUME=True`.
Tiếp tục từ `last.pt` của epoch hoàn thành gần nhất; `best.pt` chọn theo validation
field-box F1 ở IoU/score 0,5 cố định, **không phải mAP hay độ chính xác OCR**.
Đổi batch size/dữ liệu/phiên bản Torch thì dùng run mới. Không nạp checkpoint lạ.
Chưa tự thay detector đang chạy trong API; cần đánh giá OCR end-to-end trước.

Hàng đợi 80 crop train đầu tiên nằm ở `audit_v1/recognition_*/transcriptions.csv`;
điền chữ chính xác và `reviewed=true` để chuẩn bị VietOCR. Đây chưa phải bộ recognition
đủ train/val/test. Không sử dụng kết quả OCR chưa kiểm tra làm ground truth.

Kiểm tra tại máy: unit tests và một lượt forward/backward trên ảnh thật với trọng số
khởi tạo ngẫu nhiên, validation, lưu/nạp checkpoint đều chạy được trên CPU.
Chưa chạy GPU trong phiên Colab của người dùng và chưa có kết quả fine-tune thực.
Notebook dùng Torch/Torchvision có sẵn trong Colab, ghi phiên bản vào checkpoint;
môi trường Colab chưa được khóa đầy đủ. Metadata Kaggle/README lệch license
(`Unknown`/`CC BY 4.0`), cần xác minh quyền nguồn trước phát hành.

Code nguồn: `card_dataset.py`, `train_card_detector.py`.
Sau khi sửa, chạy `build_card_notebook.py` để nhúng lại code vào notebook,
rồi chạy Ruff fix/format cho notebook. Dữ liệu và audit chi tiết nằm ở `data/`,
`outputs/` bị Git bỏ qua; không đẩy ảnh/crop/checkpoint lên repo.

Code chính của bản thử nay nằm ở `vericlue/tools/identity_lab`.
Không nối vào TrustRouter và không sửa hợp đồng API công khai của VeriClue.
Môi trường Python 3.10 và trọng số đã tải được tái sử dụng ngoài repo;
đây chưa phải package Python 3.12 của dịch vụ chính.

## Chạy trên máy hiện tại

Mở PowerShell, không cần activate venv:

```powershell
cd F:\Python_code\AIO_2026\vericlue
$env:IDENTITY_MODELS_DIR = 'F:\Python_code\AIO_2026\output\vericlue_identity_lab\models'
& ..\output\vericlue_identity_lab\.venv\Scripts\python.exe tools/identity_lab/identity_lab.py --out outputs/ocr/result.json ocr data/images/test_ocr/anh_cccd_1.jfif --debug-dir outputs/ocr/debug
```

`result.json`: kết quả đọc gốc, kết quả từng trường, lý do cần xem lại.
`debug/overlay.png`: ảnh vẽ box, số trên box khớp `source_line_ids` và thứ tự `lines`.
`debug/line_*.png`: chính crop được đưa vào VietOCR. Chỉ lưu khi chỉ định `--debug-dir`.
Các file này chứa dữ liệu cá nhân, nằm trong `outputs/` bị Git bỏ qua. Không có tự xóa 24 giờ.

API thử nội bộ:

```powershell
& ..\output\vericlue_identity_lab\.venv\Scripts\python.exe -m uvicorn app:app --app-dir tools/identity_lab --host 127.0.0.1 --port 8010
```

Mở http://127.0.0.1:8010/docs. Endpoint `POST /dev/v1/ocr`, multipart `image`.
Face matching: `POST /dev/v1/face-match`, multipart `reference`, `selfie`.
API không lưu ảnh debug và không trả đường dẫn nội bộ khi model lỗi. Chưa có auth/session;
chỉ chạy localhost cho developer, không dùng trực tiếp làm API ngân hàng.
`openapi.json` sinh từ `schemas.py` là hợp đồng developer, không phải hợp đồng production.

## Ý nghĩa kết quả v2

### Đọc lại vùng giá trị (23/10)

Áp dụng ý tưởng tách detection/recognition của bài thực hành DBNet/CRAFT/VietOCR:
PaddleOCR xuất thêm vị trí từ; tìm điểm kết thúc nhãn và cắt riêng giá trị quốc tịch,
thường trú, ngày hết hạn đang có bất nhất. VietOCR đọc 3 crop với biên 0/10/20%.
Không có tọa độ từ phù hợp thì bỏ qua, không đoán một vị trí cố định trên thẻ.

`rereads` lưu text, confidence, polygon, biên và dòng gốc. `original_value` giữ ứng viên
trước đọc lại. Chỉ đề xuất thay `value` khi ít nhất hai biến thể cho cùng một giá trị
hợp lệ với confidence >=0.7 (heuristic chưa hiệu chỉnh); vẫn giữ `review` và mọi ứng viên cũ.
Không coi chạy lặp cùng model là xác minh độc lập. `field_*.png` trong debug cho thấy đúng
ảnh giá trị đưa vào model. Dòng raw trong `lines` không bị ghi đè.

Đã thử tăng max width 512→1024 và thêm biên trên nguyên dòng: không sửa được lỗi ngày
hết hạn ở ảnh thứ hai. Kết quả probe ở outputs/ocr_debug/probe.json; không dùng làm benchmark.
Chưa thay detector bằng CRAFT hoặc huấn luyện DBNet mới. Giấy tờ nhiều kiểu bố cục cần
đánh giá riêng; vị trí từ do recognizer ước lượng vẫn có thể sai.

Quan sát trên hai ảnh phát triển: crop quốc tịch đọc đúng dấu qua cả 3 biến thể;
crop địa chỉ đọc được chữ đầu D thay cho p, nhưng vẫn nhầm i/1 và dấu ở một số biến thể.
Ở ảnh thứ hai, crop ngày hết hạn không thêm biên đọc `02/07/2031`, còn hai biến thể
thêm biên vẫn đọc `02/0712031`. Do đó chưa nâng trạng thái hoặc tuyên bố hết lỗi.
Không dùng kết quả này làm độ chính xác tổng quát hay chọn ngưỡng production.

- `status=ok`: inference chạy xong; không bảo đảm chữ đúng.
- `document_status=review`: chưa đủ điều kiện tự xác minh. Không có đường OCR tự trả pass.
- `fields`: số định danh, họ tên, ngày sinh, giới tính, quốc tịch, quê quán, thường trú, hết hạn.
- `consistent`: hai bộ đọc có cùng một giá trị hợp lệ. Không phải xác suất đúng hoặc xác minh giấy tờ.
- `review`: có bất nhất, một nguồn hợp lệ, confidence thấp hoặc địa chỉ chưa chứng minh đầy đủ.
- `missing`: chưa gán được trường; không đoán theo thứ tự ngày xuất hiện.
- `value`: ứng viên đề xuất, phải đi cùng `status`. Không được bỏ status khi tích hợp.
- `candidates`: giữ các phương án; `source_line_ids` dẫn về chữ gốc và polygon.
- Ngày được chuẩn hóa thành ISO chỉ khi ngày có thật trong lịch; không tự thay `1` bằng `/`.
- Nhãn, QR, quốc huy có thể bị detector xem là chữ; raw lines vẫn giữ để debug nhưng không
  dùng mọi chuỗi số đó tạo cảnh báo toàn hồ sơ.
- Địa chỉ ghép dòng tiếp theo gần nhau; vẫn đánh dấu review, không sửa địa danh bằng từ điển/LLM.
- Tọa độ trên ảnh đã áp dụng EXIF, không phải ảnh thẻ tự căn chỉnh.

Pipeline: PP-OCRv5 mobile tìm vùng + Latin đọc đối chiếu; VietOCR vgg_seq2seq đọc crop
đã chỉnh phối cảnh từng dòng. Không tự chỉnh phối cảnh toàn thẻ, không hỗ trợ mọi mẫu thẻ,
không kiểm tính xác thực QR/thẻ, không có PAD trong công cụ này.
Face matching mặc định là SCRFD + AdaFace; điểm cosine chưa hiệu chỉnh, không quyết định danh tính.

Face matching v2 hiện hỗ trợ thêm ArcFace R50, so sánh model trên cùng aligned crops,
vùng chân dung CCCD, và công cụ hiệu chỉnh ngưỡng offline có kiểm tra trùng người/ảnh.
Xem [FACE_MATCHING.md](FACE_MATCHING.md) để chạy so sánh và khởi động API với cấu hình
được chọn từ kết quả thực nghiệm. Đây vẫn là công cụ nghiên cứu, chưa tự duyệt eKYC.

## Kiểm tra

```powershell
& ..\output\vericlue_identity_lab\.venv\Scripts\python.exe -m pytest -c tools/identity_lab/pytest.ini tools/identity_lab -q
& ..\output\vericlue_identity_lab\.venv\Scripts\python.exe tools/identity_lab/check_local.py
```

`check_local.py` chạy lại ảnh JFIF ở data/images/test_ocr, lưu outputs/ocr_debug và kiểm tra API
bằng mô hình thật. Đây là hồi quy trên ảnh phát triển, không phải tập test độc lập hoặc benchmark.
Không dùng hai ảnh này để tuyên bố độ chính xác hoặc hiệu chỉnh ngưỡng.

Để cài trên máy khác: tạo venv Python 3.10, cài `requirements-lock.txt` bằng `uv pip install --no-deps -r ...`;
lock bao gồm toàn bộ dependency inference đã chạy. `--no-deps` tránh pin dependency training cũ
của VietOCR. Chạy `prepare_vietocr.py` tải config/weights từ vocr.vn. Model PaddleOCR/UniFace
tải ở lần đầu; đặt IDENTITY_MODELS_DIR trước khi chạy. Không commit ảnh/weights.
Không có dependency hoặc code nguồn GPL được chép vào repo; các thư viện được gọi qua API.

## Giới hạn và bước tiếp theo

Fine-tune bộ đọc VietOCR trên VinText bằng Colab: xem
[VINTEXT_FINETUNE.md](VINTEXT_FINETUNE.md) và notebook
`finetune_vietocr_vintext_colab.ipynb`. Đây là huấn luyện đọc chữ; không thay detector CCCD.

Parser là heuristic theo nhãn song ngữ và vị trí, chưa bao phủ mọi mẫu CCCD/căn cước,
thẻ xoay 90 độ, bố cục khác, ảnh thiếu góc, lóa mạnh. Các confidence chỉ là tín hiệu thô.
Cần tập ảnh đa dạng có nhãn thật, tách người, đánh giá exact-match từng trường, lỗi bỏ sót và
nhận sai. Tích hợp chính thức cần adapter ModuleResult, session, public contract, retention
và kiểm tra cùng phiên PAD. Chưa đánh dấu task production hoàn tất.

Face matching: xem [FACE_CONTEXT.md](FACE_CONTEXT.md) để chạy bản IR18 có bước khắc phục detector bỏ sót mặt sát khung hình và đọc kết quả FG-NET.
