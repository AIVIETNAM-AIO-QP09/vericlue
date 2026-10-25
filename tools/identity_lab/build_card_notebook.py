"""Generate a standalone Colab notebook embedding the reviewed local modules."""

import json
from pathlib import Path

HERE = Path(__file__).parent


def build():
    cells = []

    def add(kind, text):
        cell = {"cell_type": kind, "metadata": {}, "source": text.strip().splitlines(keepends=True)}
        if kind == "code":
            cell.update(execution_count=None, outputs=[])
        cells.append(cell)

    add(
        "markdown",
        """
# VeriClue — fine-tune detector vùng CCCD trên Google Colab

**Notebook này train vùng thông tin, chưa train VietOCR đọc chữ.**
Faster R-CNN + MobileNetV3 pretrained COCO, input 640 px, 10 lớp trường CCCD.
YOLO chỉ là định dạng nhãn nguồn; không cài Ultralytics/YOLOv5.

Runtime → Change runtime type → **T4 GPU**, rồi Run all với `SMOKE=True`.
Smoke chỉ kiểm tra training chạy, không là benchmark. AUTO_GROUP=True tự đọc số CCCD
để gom nhóm tạm, loại ảnh không chắc. Kết quả chỉ là thử nghiệm trên tập con dễ đọc,
chưa chứng minh chia tập theo người. AUTO_GROUP=False dùng groups.csv đã duyệt thủ công.
Test giữ riêng, không dùng chọn checkpoint/ngưỡng. Không có accuracy OCR nếu chưa có transcript.
Ảnh, crop và checkpoint nằm trong Drive riêng của bạn; không chia sẻ công khai notebook có output chứa CCCD.

Dataset nguồn: https://www.kaggle.com/datasets/tranphucthaitruong/vietnamese-card-dataset (v1).
Metadata Kaggle ghi Unknown, README ghi CC BY 4.0: quyền nguồn còn cần xác minh trước phát hành.
""",
    )
    add(
        "code",
        """
%pip -q install pyyaml==6.0.3 easyocr==1.7.2
from google.colab import drive
from pathlib import Path
import torch, torchvision
drive.mount('/content/drive')
print('torch', torch.__version__, 'torchvision', torchvision.__version__)
assert torch.cuda.is_available(), 'Bật T4 GPU trong Runtime > Change runtime type'
print(torch.cuda.get_device_name(0))
""",
    )
    add(
        "code",
        """
# AUTO_GROUP tự gom theo OCR số CCCD; chưa phải nhóm danh tính đã xác minh.
SMOKE = True
AUTO_GROUP = True
EPOCHS = 15
BATCH_SIZE = 2  # Nếu hết VRAM: dùng 1 và RUN_NAME mới.
RESUME = True  # Tiếp tục từ epoch hoàn thành gần nhất.
RUN_NAME = 'smoke_v1' if SMOKE else ('detector_auto_v1' if AUTO_GROUP else 'detector_v1')
BASE = Path('/content/drive/MyDrive/vericlue_ocr')
BASE.mkdir(parents=True, exist_ok=True)
ROOT = Path('/content/vietnamese_card_v1')
AUDIT = BASE / 'audit_v1'
RUN = BASE / 'runs' / RUN_NAME
GROUPS = AUDIT / 'groups.csv'
""",
    )
    add("markdown", "## Nạp code độc lập — không cần clone repo hoặc token GitHub")
    for name in ("card_dataset.py", "train_card_detector.py", "auto_card_groups.py"):
        source = (HERE / name).read_text(encoding="utf-8")
        add("code", f"Path('/content/{name}').write_text({source!r}, encoding='utf-8')")
    add(
        "code",
        """
import sys, importlib
sys.path.insert(0, '/content')
import card_dataset, train_card_detector
importlib.reload(card_dataset)
importlib.reload(train_card_detector)
""",
    )
    add("markdown", "## Tải bản v1, kiểm SHA-256 và giải nén an toàn")
    add(
        "code",
        """
import urllib.request, zipfile
from card_dataset import sha256
ARCHIVE = BASE / 'vietnamese_card_v1.zip'
EXPECTED = '72d1b4883dd07a87f134a77123987d9b4107745ed2197c8cfb2d72643510d7db'
URL = 'https://www.kaggle.com/api/v1/datasets/download/tranphucthaitruong/vietnamese-card-dataset?datasetVersionNumber=1'
if not ARCHIVE.exists():
    partial = ARCHIVE.with_suffix('.part')
    with urllib.request.urlopen(URL, timeout=120) as response, partial.open('wb') as target:
        import shutil
        shutil.copyfileobj(response, target)
    assert sha256(partial) == EXPECTED, 'Archive khác bản đã kiểm tra; dừng để xác minh nguồn.'
    partial.replace(ARCHIVE)
assert sha256(ARCHIVE) == EXPECTED, 'Sai checksum dataset; không tiếp tục train.'
ROOT.mkdir(parents=True, exist_ok=True)
with zipfile.ZipFile(ARCHIVE) as archive:
    assert sum(item.file_size for item in archive.infolist()) < 500_000_000
    for item in archive.infolist():
        assert (ROOT / item.filename).resolve().is_relative_to(ROOT.resolve()), 'Unsafe zip path'
    archive.extractall(ROOT)
print('Dataset SHA-256:', EXPECTED)
""",
    )
    add(
        "code",
        """
import json
from card_dataset import audit, export_crops, grouped_split
report, rows = audit(ROOT, AUDIT)
print(json.dumps({k: report[k] for k in ['images', 'splits', 'cccd_candidates', 'sizes']}, indent=2))
print('Lỗi nhãn/ảnh:', len(report['errors']))
print('Nhóm pixel trùng xuyên tập:', len(report['cross_split_identical_pixels']))
print('Nhóm tên nguồn cần xem:', len(report['cross_split_source_name_candidates']))
assert not report['errors'], 'Xem audit.json và sửa lỗi dữ liệu trước khi train.'
selected = [row for row in rows if row['cccd_candidate']]
if not SMOKE:
    if AUTO_GROUP:
        import easyocr
        import auto_card_groups
        importlib.reload(auto_card_groups)
        reader = easyocr.Reader(['en'], gpu=torch.cuda.is_available(), detector=False,
                                model_storage_directory=str(BASE / 'easyocr_models'))
        selected, auto_csv = auto_card_groups.auto_group(ROOT, selected, AUDIT, reader)
        selected = grouped_split(selected, auto_csv)
        del reader
        torch.cuda.empty_cache()
        print('AUTO: nhóm tạm bằng OCR, chưa xác minh theo người; không dùng làm benchmark chính thức.')
    else:
        selected = grouped_split(selected, GROUPS)
export_crops(ROOT, selected, RUN / 'recognition_queue', limit=80)
print('Nhóm thủ công giữ nguyên:', GROUPS)
""",
    )
    add(
        "markdown",
        """
## Kiểm tra ảnh/box trước khi train
Các ảnh dưới đây chỉ từ train. Xem cả `cccd` có thực sự chọn đúng loại thẻ,
box có cắt mất dấu/ký tự, và các dòng địa chỉ có đủ không.
Để chạy tự động: SMOKE=False, AUTO_GROUP=True. Đọc 2 biến thể crop số CCCD,
chỉ nhận khi cùng 12 chữ số với confidence >=0.85; ảnh mâu thuẫn/không chắc bị loại.
Không sửa ký tự hay ép chỉ nhận số. Ngưỡng này là heuristic, chưa hiệu chỉnh.
Lưu groups_auto.csv, auto_group_report.json và auto_group_excluded.json trong audit_v1.
Chạy lại tận dụng cache, không ghi đè nhóm thủ công. Cần ít nhất 10 nhóm tự nhận được.
AUTO_GROUP=False vẫn dùng groups.csv đã điền. Tách nhóm 70/15/15 xấp xỉ.
Hash/pixel trùng chỉ tìm được một phần rò rỉ; cần người kiểm tra ảnh khác của cùng một thẻ.
""",
    )
    add(
        "code",
        """
from PIL import Image, ImageDraw
from IPython.display import display
from card_dataset import FIELDS
for row in [r for r in selected if r['split'] == 'train'][:3]:
    with Image.open(ROOT / row['image']) as source:
        preview = source.convert('RGB')
    draw = ImageDraw.Draw(preview)
    for box in row['boxes']:
        if box['field'] in FIELDS:
            draw.rectangle(box['xyxy'], outline='red', width=2)
            draw.text(tuple(box['xyxy'][:2]), box['field'], fill='red')
    display(preview)
""",
    )
    add(
        "markdown",
        """
## Fine-tune và tiếp tục khi mất phiên
`last.pt` lưu model, optimizer, RNG, epoch; `best.pt` chọn bằng **validation field-box F1**
với IoU≥0.5 và score≥0.5 cố định. Đây không phải mAP, cũng không phải độ chính xác OCR.
Mất phiên: chạy lại các cell, giữ RUN_NAME, SMOKE và cấu hình, RESUME=True.
Đổi môi trường/data/batch size: tạo RUN_NAME mới. Không nạp checkpoint không rõ nguồn.
""",
    )
    add(
        "code",
        """
from train_card_detector import train
history = train(ROOT, selected, RUN, smoke=SMOKE, epochs=EPOCHS,
                batch_size=BATCH_SIZE, resume=RESUME)
print('Checkpoint và metrics:', RUN)
print(json.dumps(history[-1], indent=2))
""",
    )
    add(
        "markdown",
        """
## Dùng kết quả
Giữ `best.pt`, `manifest.json`, `metrics.json`, `checkpoint_sha256.txt` trên Drive.
Chạy smoke thành công chỉ chứng minh pipeline chạy; không đưa số smoke vào báo cáo.
Chưa tự thay detector đang chạy trong identity_lab: cần đánh giá crop và OCR end-to-end trước.

Muốn fine-tune **VietOCR**: điền `text` chính xác và `reviewed=true` trong
`runs/<RUN_NAME>/recognition_queue/transcriptions.csv`, mở ảnh crop để kiểm từng dấu. Đây chỉ là hàng đợi 80 crop
đầu tiên, chưa phải tập train đủ và chưa có validation transcript.
Không coi dự đoán OCR là ground truth. Giữ split theo người khi mở rộng bộ recognition.

Tham khảo API model: https://docs.pytorch.org/vision/stable/models/generated/torchvision.models.detection.fasterrcnn_mobilenet_v3_large_320_fpn.html
""",
    )
    notebook = {
        "cells": cells,
        "metadata": {
            "accelerator": "GPU",
            "colab": {"name": "finetune_cccd_detector_colab.ipynb"},
            "kernelspec": {"display_name": "Python 3", "language": "python", "name": "python3"},
        },
        "nbformat": 4,
        "nbformat_minor": 5,
    }
    for i, cell in enumerate(cells):
        cell["id"] = f"card-{i:02d}"
    destination = HERE / "finetune_cccd_detector_colab.ipynb"
    destination.write_text(json.dumps(notebook, ensure_ascii=False, indent=1), encoding="utf-8")
    return destination


if __name__ == "__main__":
    print(build())
