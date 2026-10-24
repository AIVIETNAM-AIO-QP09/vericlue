# Face matching — thử dataset trước, CCCD/selfie sau

Ảnh `selfie_2` và thử nghiệm gộp nhiều selfie: [FACE_CAPTURE.md](FACE_CAPTURE.md).
CLI mới giữ evidence/retry từng ảnh, không chọn frame theo điểm khớp CCCD.

Thực nghiệm training trên dataset công khai và kiểm tra 5 ảnh cá nhân:
[FACE_ADAPTER.md](FACE_ADAPTER.md). Đã train adapter nhẹ; chưa fine-tune backbone,
chưa thay model mặc định vì chưa chứng minh tăng khả năng phân biệt.

## Kiểm tra CCCD–selfie ngày 24/10/2026

Người dùng xác nhận 3 ảnh CCCD và 2 selfie hiện có đều cùng một người. Đây chỉ là
6 cặp genuine của **một người**, không đủ tính FMR/AUC hay chọn ngưỡng danh tính.
`audit_face_portrait.py` so baseline với phát hiện lại trong ROI mở rộng 0,5 lần
chiều rộng/cao mỗi bên. Bắt buộc ảnh gốc có đúng một mặt trước khi crop; không chọn
biến thể theo điểm từng cặp. Trích embedding một lần mỗi ảnh cho ma trận cặp,
không lưu embedding ra file. Debug ảnh mặt chứa dữ liệu cá nhân, chỉ lưu local.

Lượt thực tế: `outputs/face_portrait_audit_01/report.json`. Chênh lệch cosine
candidate-baseline từ -0,00644 tới +0,00582; tăng thời gian 198–226 ms/reference
(bao gồm ghi debug). Không đưa candidate vào mặc định vì chưa có lợi ích rõ ràng.
Giữ AdaFace IR18 single; không thay ngưỡng hoặc làm mất hiệu lực benchmark launcher.
Độ nét là chẩn đoán, chưa là gate chất lượng đã hiệu chỉnh.

```powershell
$env:IDENTITY_MODELS_DIR='F:\Python_code\AIO_2026\output\vericlue_identity_lab\models'
& ..\output\vericlue_identity_lab\.venv\Scripts\python.exe tools/identity_lab/audit_face_portrait.py --references data/images/test_ocr/anh_cccd.jfif data/images/test_ocr/anh_cccd_1.jfif data/images/test_ocr/anh_cccd_2.jfif --selfies data/images/test_ocr/selfie.jfif data/images/test_ocr/selfie_1.jfif --out outputs/face_portrait_audit_02
```

Bước cần dữ liệu tiếp theo: cặp CCCD–selfie có đồng ý sử dụng của nhiều người,
gồm cùng người và khác người; chia calibration/evaluation theo người. Không fine-tune
trên 5 ảnh rồi đánh giá lại trên chính chúng, không lấy score 0,4 làm ngưỡng mặc định.

## Pipeline

SCRFD-10G phát hiện khuôn mặt và 5 landmarks → căn chỉnh 112×112 → AdaFace-IR18
trích embedding → cosine similarity. Dùng ONNX CPU và model đã cache. Không yêu cầu
fine-tune ngay khi chưa có tập cặp CCCD/selfie có nhãn và người tách biệt.
AdaFace dùng đầu vào BGR theo implementation UniFace; không đảo sang RGB nhầm.

Mỗi ảnh bắt buộc đúng một khuôn mặt. Không có mặt, nhiều mặt, box cắt ra ngoài ảnh,
mặt quá nhỏ (cạnh <32px) hoặc landmarks không hợp lệ → retry, không có score.
Giới hạn kích thước/landmark là heuristic kỹ thuật chưa hiệu chỉnh trên CCCD.
Hai ảnh có pixel giống hệt dù khác encoding → retry/E_IDENTICAL_INPUTS.
Không suy ra người sống từ ảnh. Hai ảnh khác pixel của cùng tấm thẻ vẫn có thể giống nhau;
face matching không thay PAD, không chứng minh selfie được chụp trực tiếp.

Chất lượng được ghi dạng số thô: kích thước mặt, khoảng cách mắt, độ sáng, phương sai
Laplacian, góc đường mắt. Chưa dùng blur/brightness/pose làm ngưỡng quyết định tự động.
Một số ảnh khuôn mặt trên giấy có thể khó detect; chưa có whole-card rectification.

## Chạy hai file

Từ repo root, thay đường dẫn ảnh khi có selfie:

```powershell
$env:IDENTITY_MODELS_DIR = 'F:\Python_code\AIO_2026\output\vericlue_identity_lab\models'
& ..\output\vericlue_identity_lab\.venv\Scripts\python.exe tools/identity_lab/face_matching.py "duong_dan_cccd.jpg" "duong_dan_selfie.jpg" --out outputs/face_trial/result.json --debug-dir outputs/face_trial/debug
```

Debug chỉ khi opt-in: ảnh vẽ bbox/landmarks và đúng crop aligned đưa vào recognition.
Không ghi embedding ra JSON. File debug chứa dữ liệu khuôn mặt, không commit.

Kết quả `face-pair-lab/v2`:

- `status=ok`: đã tính score, **không phải cùng người**.
- `decision=review`, `threshold=null`, `identity_verified=false`: chưa hiệu chỉnh.
- `cosine_similarity` nằm [-1,1], không phải xác suất/"% cùng người".
- `status=retry`: input không đáp ứng điều kiện kỹ thuật, score=null, reason cụ thể.
- Không có đường tự trả pass. Model lỗi → API503; decode lỗi →422, quá dung lượng→413.

## API để SW nối sau

```powershell
& ..\output\vericlue_identity_lab\.venv\Scripts\python.exe -m uvicorn app:app --app-dir tools/identity_lab --host 127.0.0.1 --port 8010
```

Swagger: http://127.0.0.1:8010/docs. POST `/dev/v2/face-match`, multipart fields
`reference` (ảnh CCCD) và `selfie`. API không lưu ảnh/debug/embedding.
Giữ `/dev/v1/face-match` cũ để tương thích; dùng v2 cho thử nghiệm mới.
Đây là developer contract, chưa phải public session API. Khi tích hợp phải bổ sung
adapter/ModuleResult/mock đúng contracts, session và PAD; không hiển thị cosine cho người dân.

## Kiểm tra dataset LFW

```powershell
& ..\output\vericlue_identity_lab\.venv\Scripts\python.exe tools/identity_lab/prepare_lfw.py --out data/lfw_face_eval
& ..\output\vericlue_identity_lab\.venv\Scripts\python.exe tools/identity_lab/evaluate_faces.py --dataset data/lfw_face_eval --out outputs/face_lfw_new
```

Nguồn download và SHA-256 lấy từ metadata scikit-learn:
https://github.com/scikit-learn/scikit-learn/blob/main/sklearn/datasets/_lfw.py
Ảnh gốc LFW 250px, official pairsDevTest: 1000 cặp (500 cùng/500 khác), 1549 ảnh duy nhất.
Không dùng resized face 62×47 mặc định của sklearn. Chỉ giải nén ảnh thuộc tập cặp này.
Không chọn ngưỡng từ test. Báo ROC AUC trên cặp có score, phân bố score và tỷ lệ
không xử lý được, có reason từng cặp. Không tính accuracy khi chưa có ngưỡng khóa độc lập.
Cache embedding chỉ trong bộ nhớ để tránh inference lặp; output chỉ pair scores.

LFW là ảnh người nổi tiếng, **không phải cặp CCCD/selfie**, không đại diện dân số Việt Nam.
Đây là development-test evaluation, không phải protocol LFW 10-fold. Chưa audit trùng người
với dữ liệu pretraining của trọng số. Không dùng kết quả để tuyên bố hiệu quả ngân hàng.

Tập chuẩn tiếp theo cần cùng người/khác người, CCCD–selfie thực, có điều kiện chụp đa dạng;
tách người cho calibration và test, chọn ngưỡng trên calibration rồi khóa trước test.
Báo false match, false non-match, failure-to-acquire và latency, không chỉ accuracy tổng.

Tham khảo model:
https://github.com/mk-minchul/AdaFace
https://github.com/yakhyo/uniface

## Kiểm thử

### Nâng cấp và so sánh model (2026-10-24)

`compare_face_models.py` so sánh AdaFace IR18 và ArcFace R50 (`w600k_r50` qua UniFace),
mỗi model có `single` và `flip_mean`. Cùng ảnh, cùng detector SCRFD, cùng landmark và
aligned crop. UniFace thực hiện tiền xử lý riêng: AdaFace dùng BGR, ArcFace dùng RGB.
Không lấy max điểm giữa model cho từng cặp. `flip_mean` chuẩn hóa L2 từng embedding,
cộng embedding ảnh gốc và ảnh lật ngang, rồi chuẩn hóa lại trước tính cosine.

```powershell
# Chạy từ thư mục vericlue; dùng thư mục model cache hiện có.
$env:IDENTITY_MODELS_DIR='F:\Python_code\AIO_2026\output\vericlue_identity_lab\models'
& ..\output\vericlue_identity_lab\.venv\Scripts\python.exe tools/identity_lab/prepare_face_models.py --recognizer arcface_r50
& ..\output\vericlue_identity_lab\.venv\Scripts\python.exe tools/identity_lab/compare_face_models.py --dataset data/lfw_face_eval --out outputs/face_comparison_new
```

Theo yêu cầu ưu tiên tốc độ khi AUC gần nhau: launcher chọn cấu hình nhanh nhất có AUC
cách AUC cao nhất không quá 0,001 (tham số `--auc-tolerance`, mặc định 0.001).
Đây là mức đánh đổi kỹ thuật, không phải kiểm định tương đương thống kê.
Script benchmark vẫn lưu xếp hạng AUC gốc; launcher áp dụng lựa chọn tốc độ riêng.
Báo kèm coverage và latency nhận dạng (không gồm detection/nạp model). Chênh lệch nhỏ không chứng minh
ưu thế thống kê. Sau khi chọn model bằng LFW devtest, tập này là dữ liệu phát triển;
không được gọi là test độc lập. So sánh hai checkpoint này cũng không chứng minh mọi
ArcFace đều tốt hơn mọi AdaFace hoặc ngược lại.

CLI `face_matching.py` thêm `--recognizer adaface_ir18|arcface_r50`,
`--embedding-mode single|flip_mean`, `--reference-roi X1 Y1 X2 Y2`.
Developer API `/dev/v2/face-match` thêm multipart `embedding_mode` và `reference_roi`
(chuỗi JSON `[x1,y1,x2,y2]`). Model API chọn khi khởi động bằng `FACE_RECOGNIZER`;
khởi động lại server sau khi đổi biến môi trường. Mặc định vẫn AdaFace single cho
tương thích; cấu hình được khuyến nghị được ghi trong báo cáo so sánh.

Khởi động API bằng cấu hình nhanh nhất trong nhóm AUC gần mức tốt nhất (một cấu hình cố định):

```powershell
& ..\output\vericlue_identity_lab\.venv\Scripts\python.exe tools/identity_lab/serve_face_lab.py --comparison outputs/face_model_comparison_01/comparison.json --port 8010
```

Lệnh kiểm tra hash model, mã pipeline và runtime khớp báo cáo trước khi mở server.
Nếu đã thay code/model, chạy lại so sánh thay vì bỏ kiểm tra. Swagger ở
`http://127.0.0.1:8010/docs`; endpoint v2 mặc định dùng model và embedding mode đã chọn.
Vẫn có thể truyền mode khác để thử nghiệm riêng, nhưng đó không còn là cấu hình được chọn.
Endpoint v1 giữ AdaFace riêng cho tương thích. `identity_verified` luôn false ở lab.

### Kết quả so sánh và cấu hình đã chọn

**Chọn AdaFace IR18 `single` theo ưu tiên tốc độ của người dùng.** Model và API đã thử
với ảnh LFW thật, kiểm tra thêm ROI trên canvas tổng hợp, tọa độ ảnh gốc, duplicate
và sự nhất quán điểm giữa CLI/API. 70 tests đạt; lint sạch.

| Cấu hình | ROC AUC (chỉ cặp có score) | Median trích đặc trưng/mặt CPU |
|---|---:|---:|
| **AdaFace IR18 single — chọn** | **0,996228** | **52,8 ms** |
| AdaFace IR18 flip_mean | 0,996392 | 109,2 ms |
| ArcFace R50 single | 0,996315 | 267,6 ms |
| ArcFace R50 flip_mean | 0,996739 | 544,4 ms |

Tất cả dùng cùng 1.000 cặp, 645 cặp có score / 355 retry; chưa cải thiện coverage.
ArcFace flip có AUC cao nhất nhưng chỉ hơn AdaFace single khoảng 0,000511, trong khi
thời gian trích đặc trưng cao hơn khoảng 10,3 lần. Thời gian trên không phải latency
toàn API hoặc một cặp hai ảnh. Vòng so sánh chung mất 1.356 giây, không gồm nạp model.

Kiểm tra mô tả đường ROC trên chính tập phát triển này: ở mức không nhận nhầm bất kỳ
cặp khác người nào trong 341 cặp có score, cả bốn đều bỏ lỡ 5/304 cặp cùng người;
ở mức 3/341 cặp nhận nhầm, cả bốn đều bỏ lỡ 4/304. Đây là điểm trên ROC được tìm từ
cùng dữ liệu, **không phải đánh giá ngưỡng đã khóa độc lập**. Không đưa ngưỡng này vào API.
Không có bằng chứng ở đây để đánh đổi tốc độ lấy ưu thế eKYC rõ rệt của ArcFace.

Chi tiết: `outputs/face_model_comparison_01/comparison.json`; lựa chọn cuối sau yêu cầu
tốc độ: `selection.json`; kiểm tra API đã chọn: `api_smoke_fast.json`.
`provisional_candidate` trong comparison gốc là thắng theo AUC; selection/launcher mới
là lựa chọn tốc độ cuối. Dữ liệu/mã benchmark được giữ lại, không sửa điểm để đổi người thắng.

ROI là vùng **ảnh chân dung chính trên thẻ**, gồm đủ mặt và khoảng trống cho alignment;
không phải bounding box cắt sát mặt. Tọa độ tính trên ảnh đã sửa EXIF. Với ROI,
`reference.bbox` và `reference.landmarks` vẫn trả tọa độ ảnh gốc đã sửa EXIF;
debug overlay của reference là ảnh crop ROI. ROI sai/tràn ảnh trả 422. Trong ROI vẫn
phải có đúng một mặt; selfie luôn kiểm tra toàn khung và từ chối nhiều mặt.
ROI hiện do bên gọi cung cấp, chưa tự động nối detector CCCD; không chứng minh thẻ thật
hay rằng vùng đã chọn thuộc chân dung thật của chủ thẻ. Chỉ dùng trong lab, chưa phải
tham số để trình duyệt production tự quyết định vùng nhận dạng.

Landmark trùng điểm/thẳng hàng bị retry trước alignment. Báo thêm tỷ lệ padding và
độ nét sau alignment; đây là số đo để phân tích, chưa phải ngưỡng chất lượng đã hiệu chỉnh.
Không tự làm nét/tạo lại khuôn mặt để tăng điểm.

### Hiệu chỉnh ngưỡng khi có dataset CCCD–selfie

Tạo hai thư mục dataset, mỗi thư mục có `pairs.json` và các ảnh tương ứng:

```json
[
  {"pair_id": "g1", "reference": "images/card_a.jpg", "selfie": "images/selfie_a.jpg",
   "reference_identity": "person_a", "selfie_identity": "person_a", "same_person": true},
  {"pair_id": "i1", "reference": "images/card_a.jpg", "selfie": "images/selfie_b.jpg",
   "reference_identity": "person_a", "selfie_identity": "person_b", "same_person": false}
]
```

ID là mã ẩn danh **nhất quán giữa mọi thư mục**, không dùng số CCCD; calibration và test
phải khác người. Ảnh reference cho công cụ dataset hiện là crop chân dung đã chuẩn bị;
không tự suy ra ROI trong manifest. Chạy `evaluate_faces.py --dataset ... --out ...`
với cùng `--recognizer` và `--embedding-mode` cho cả hai tập, rồi:

```powershell
& ..\output\vericlue_identity_lab\.venv\Scripts\python.exe tools/identity_lab/calibrate_faces.py fit --run outputs/face_calibration --target-fmr 0.01 --out outputs/face_threshold.json
& ..\output\vericlue_identity_lab\.venv\Scripts\python.exe tools/identity_lab/calibrate_faces.py evaluate --run outputs/face_test --calibration outputs/face_threshold.json --out outputs/face_threshold_test.json
```

`0.01` chỉ là ví dụ mục tiêu FMR thực nghiệm, không là yêu cầu an toàn eKYC. Công cụ
chỉ chọn ngưỡng trên calibration và khóa để test, chặn trùng người/pixel, cặp lặp,
nhãn mâu thuẫn, score lỗi và khác model/pipeline/runtime. FMR/FNMR chỉ trên cặp có score;
báo thêm retry và tỷ lệ cùng người không được match khi tính cả retry. Không có lỗi
trên ít mẫu không chứng minh FMR thấp ngoài thực tế; các cặp dùng lại người không độc lập.
Artifact này chưa được nạp vào API để tự pass danh tính. Các run LFW cũ thiếu identity/hash
không dùng trực tiếp để hiệu chỉnh ngưỡng; không bịa nhãn để vượt kiểm tra.

Nguồn kỹ thuật: https://github.com/mk-minchul/AdaFace,
https://github.com/yakhyo/uniface/blob/main/docs/modules/recognition.md,
https://pages.nist.gov/frvt/html/frvt11.html.

### Kết quả LFW hoàn tất — 2026-10-24

Kết quả máy: `outputs/face_lfw_v2/summary.json`; từng cặp: `pairs.json` cùng thư mục.

| Chỉ số | Kết quả |
|---|---:|
| Tổng cặp | 1.000 (500 cùng người, 500 khác người) |
| Có điểm so khớp | 645 / 1.000 (64,5%) |
| Có điểm: cùng người / khác người | 304 / 341 |
| Yêu cầu thử lại | 355 (35,5%) |
| Cặp bị từ chối vì nhiều mặt | 351 |
| Cặp bị từ chối vì không thấy mặt | 4 |
| ROC AUC chỉ trên cặp có điểm | 0,996228 |
| Thời gian vòng đánh giá CPU (không gồm nạp model) | 472,84 giây |

Không có accuracy/FAR/FRR tại ngưỡng vì chưa khóa ngưỡng trên tập calibration độc lập.
AUC này không phải accuracy 99,62%; các cặp retry không được coi là xác thực thành công.
Coverage thấp phản ánh cả chính sách chỉ nhận ảnh có đúng một mặt và đặc tính ảnh LFW.

Kiểm tra trực quan 6 ảnh nhiều mặt duy nhất đầu tiên theo thứ tự manifest: cả 6 đều
có người khác trong nền hoặc ở mép ảnh. Overlay và tọa độ được lưu cục bộ trong
`outputs/face_lfw_v2/diagnostics/`. Đây chỉ là mẫu chẩn đoán, không chứng minh nguyên
nhân cho toàn bộ 351 cặp. Không thay ngưỡng detection hay chọn mặt lớn nhất theo test.

Kết luận: pipeline và API thử nghiệm đã chạy được với model thật. Chưa đủ bằng chứng
để tự động xác nhận danh tính trong VeriClue. Bước tiếp theo là dữ liệu CCCD–selfie
có quyền sử dụng, chia người độc lập giữa calibration/test, rồi đo false match,
false non-match và retry ở ngưỡng đã khóa; kết hợp kết quả PAD riêng.

Unit tests: duplicate pixels, geometry, parser LFW, AUC và missing coverage, API lỗi không pass.
Real-model smoke: cặp cùng/khác người từ LFW, blank, duplicate và API multipart v2;
ảnh nhiều mặt bị retry thay vì chọn mặt lớn nhất. Debug tại outputs/face_pair_smoke_v2.
Thread pools CPU giới hạn 2 intra-op/1 inter-op; đối chiếu 100 cặp với cấu hình mặc định
cho cùng trạng thái và cosine (max absolute difference 0 trong lượt chạy này).
