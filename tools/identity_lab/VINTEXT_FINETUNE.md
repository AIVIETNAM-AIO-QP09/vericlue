# Fine-tune đọc chữ tiếng Việt với VinText

Upload `finetune_vietocr_vintext_colab.ipynb` lên Google Colab, bật T4 GPU, chạy từ trên
xuống. Notebook chứa helper code, không cần upload repo. Dataset lấy bằng kagglehub
từ `hungkhoi/vietnamese-scene-text-spotting-dataset-vintext`; nếu Kaggle yêu cầu đăng nhập,
dùng `kagglehub.login()` trong Colab, không gửi token trong chat hoặc lưu trong notebook.

## Môi trường Google Colab

Notebook giữ NumPy, PyTorch, torchvision, OpenCV và Pillow có sẵn của runtime,
khóa phiên bản các gói đó khi cài thư viện bổ sung. Không dùng cell cũ cài `numpy<2`
hoặc `opencv-python-headless<4.12`. VietOCR được cài `--no-deps`; trainer riêng
không dùng Trainer/imgaug/LMDB cũ của VietOCR.

Nếu đã gặp `numpy.dtype size changed` sau khi chạy cell cũ:

1. Lưu file cần giữ trong `/content` vào Drive hoặc tải về máy.
2. Chọn **Runtime → Disconnect and delete runtime** để lấy môi trường sạch.
   Restart session đơn thuần không hoàn tác các gói đã cài.
3. Upload lại notebook đã sửa, bật **T4 GPU**, chạy từ cell đầu với `SMOKE=True`.
4. Cell đầu kiểm tra NumPy ↔ OpenCV, NumPy ↔ Torch/CUDA và torchvision NMS trên GPU.
   Cell tiếp theo kiểm tra import VietOCR, xử lý ảnh và mã hóa tiếng Việt.

Không cài lại Torch/CUDA hay hạ NumPy để bỏ qua kiểm tra. Bản sửa đã kiểm tra cú pháp
và VietOCR preprocessing trên NumPy 2 ở máy local; chưa xác minh trực tiếp trên
runtime Colab Python 3.13/GPU. Smoke trên Colab vẫn là bước bắt buộc.

## Phạm vi và điều kiện

Fine-tune VietOCR vgg_seq2seq **nhận dạng chữ trong crop**, không phải detector 10 trường
CCCD, face matching hoặc model phát hiện deepfake. VinText có chữ cảnh thực, khác chữ
trên CCCD; không bảo đảm transfer tốt hơn. Tác giả yêu cầu chỉ nghiên cứu/giáo dục,
không phân phối lại dữ liệu và trích dẫn bài Dictionary-guided Scene Text Recognition:
https://github.com/VinAIResearch/dict-guided.

Kaggle page không cung cấp danh sách file qua công cụ đọc web trong phiên này; chưa tải
dataset thật để kiểm chứng layout. Converter hỗ trợ bản gốc TXT:
`x1,y1,x2,y2,x3,y3,x4,y4,TRANSCRIPT`, ảnh trong `train_images`, `test_image`,
`unseen_test_images`; hỗ trợ ảnh `im0001.jpg` ghép nhãn `gt_1.txt` theo ID số,
cũng như nhãn cùng stem ảnh (có thể thêm tiền tố gt_). Nếu Kaggle chứa COCO,
archive hoặc tên khác, cell kiểm tra sẽ dừng; xem danh sách thư mục trước khi sửa mapping.
Không suy đoán nội dung nhãn hoặc tự gộp test vào train để chạy được.

## Chạy

Bản Kaggle người dùng xác nhận có `vintext/vintext/train_images` (1200 ảnh),
`test_image` (500), `val_image` (300). Converter giữ `val_image` thành `dataset_val`,
không tự nhận là original unseen_test. `valid` chọn checkpoint vẫn tách theo ảnh nguồn
từ train. `test` và `dataset_val` chỉ đánh giá cuối; notebook tự nhận các tập giữ lại.
Nhánh `text_recognition_data` chứa crop imXXXX_N được bỏ qua khi chuẩn bị ảnh gốc.

1. `SMOKE=True`: tối đa 32 crop train, 16 validation, một epoch. Kiểm tra GPU, crop,
   nhãn, loss, export trước. Smoke không là kết quả chất lượng.
2. Xem `audit.json`: số crop, nhãn bị loại (không đọc được, ngoài vocab, polygon lỗi),
   kiểm tra trực quan crop. Các nhãn bị loại không được âm thầm bỏ khỏi báo cáo.
3. `SMOKE=False`: mặc định 10 epochs, batch16, LR1e-5; chạy lại từ cấu hình. Run smoke
   và full tách thư mục tự động. Full vẫn khởi tạo pretrained, không dùng smoke checkpoint.
4. Checkpoint `last.pt` lưu cuối mỗi epoch trên Drive; chạy lại cùng config sẽ resume.
   Mất kết nối giữa epoch thì chạy lại epoch đó. Thay config/data/code/runtime phải đổi
   RUN_NAME. Không cam kết tái lập bit-for-bit trên GPU.
5. `best.pt` chọn theo CER validation. So với pretrained ngay trước train; nếu không
   tốt hơn, best vẫn là pretrained. Xem `history.json` để tránh hiểu nhầm đã cải thiện.
6. Chỉ bật `EVALUATE_FINAL_TEST=True` sau khi chốt cấu hình. Báo cả pretrained/selected
   trên test và unseen_test. Không chỉnh hyperparameter theo kết quả test.

Validation lấy từ khoảng 10% nhóm pixel ảnh nguồn thuộc official train, không chia
crop của cùng ảnh qua train/valid. Test và unseen_test được giữ riêng. Chặn trùng pixel
xuyên official split; chưa audit ảnh gần trùng/cùng cảnh. CER và exact match giữ dấu,
hoa/thường và dấu câu. Mức lỗi đo trên **crop có nhãn được giữ lại**, không phải end-to-end.

## Đầu ra và thử trên CCCD

Drive: `MyDrive/vericlue_vintext/runs/vintext_seq2seq_v1_full/`.
Cell cuối tải ZIP gồm `vgg_seq2seq.pth`, `local.yml`, history và test nếu có. Không gồm
dataset/crop. Giải nén vào thư mục model **mới**, ví dụ:

`F:\Python_code\AIO_2026\output\vericlue_identity_lab\models\vietocr_vintext`

Từ repo root:

```powershell
& ..\output\vericlue_identity_lab\.venv\Scripts\python.exe tools/identity_lab/try_card_detector.py data/images/test_ocr/anh_cccd_2.jfif --checkpoint models/cccd_detector/best.pt --vietocr-models ../output/vericlue_identity_lab/models/vietocr_vintext --out outputs/cccd_vintext_trial_01
```

Không ghi đè VietOCR cũ. Đánh giá cả hai recognizer trên cùng crop CCCD có nhãn trước khi
thay mặc định. Lỗi crop dính dòng/bỏ sót vùng CCCD vẫn cần xử lý ở detector riêng.

## Kiểm tra đã thực hiện

Parser nhãn giữ dấu/phẩy, warp polygon, teacher-forcing/padding batch và edit distance:
unit tests đạt. Chạy forward/backward CPU với trọng số VietOCR thật thành công, shape
logits khớp target. Các code cell notebook kiểm tra cú pháp được. Lint sạch.
**Chưa chạy end-to-end trên dataset Kaggle thật hoặc GPU Colab; chưa có trọng số fine-tune
hay số liệu cải thiện VinText/CCCD.**
