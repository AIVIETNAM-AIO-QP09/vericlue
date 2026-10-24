"""Build a self-contained Colab notebook; embed the reviewed local helper sources."""

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
cells = []


def cell(kind, source):
    value = {"cell_type": kind, "metadata": {}, "source": source.splitlines(keepends=True)}
    if kind == "code":
        value.update(execution_count=None, outputs=[])
    cells.append(value)


cell(
    "markdown",
    """# Fine-tune VietOCR seq2seq trên VinText — Google Colab
Huấn luyện **đọc chữ**, không huấn luyện detector trường CCCD hoặc face matching.
Bật Runtime → Change runtime type → T4 GPU. Chạy SMOKE trước, sau đó đổi False và chạy lại từ cấu hình.
VinText là ảnh cảnh thực; cần đánh giá CCCD riêng, chưa bảo đảm cải thiện. Dataset gốc chỉ dùng nghiên cứu/giáo dục,
không phân phối lại dữ liệu/crop. Nguồn: https://github.com/VinAIResearch/dict-guided.
Notebook chưa được chạy trên GPU Colab trong phiên tạo; nếu cấu trúc Kaggle khác TXT gốc, dừng để kiểm tra.
""",
)
cell(
    "code",
    """# Chạy trên runtime Colab GPU SẠCH. Nếu từng chạy cell numpy<2:
# Runtime -> Disconnect and delete runtime, kết nối GPU lại rồi chạy notebook này.
import sys, subprocess, json
from pathlib import Path
assert 'google.colab' in sys.modules or Path('/content').is_dir(), 'Notebook dành cho Google Colab'
probe = '''import sys,json,numpy,torch,torchvision,cv2
from importlib.metadata import version
assert sys.version_info < (3,13) or int(numpy.__version__.split('.')[0]) >= 2, 'Python 3.13 cần NumPy tương thích; tạo runtime sạch'
assert torch.cuda.is_available(), 'Bật GPU T4 trong Runtime > Change runtime type'
x=numpy.zeros((8,8,3),dtype=numpy.uint8)
assert cv2.cvtColor(x,cv2.COLOR_RGB2GRAY).shape==(8,8)
t=torch.from_numpy(numpy.ones((2,2),dtype=numpy.float32)).cuda()
assert t.sum().item()==4
torchvision.ops.nms(torch.tensor([[0.,0.,2.,2.]],device='cuda'),torch.tensor([1.],device='cuda'),0.5)
print(json.dumps({'python':sys.version,'numpy':numpy.__version__,'torch':torch.__version__,'torchvision':torchvision.__version__,'opencv':cv2.__version__,'gpu':torch.cuda.get_device_name(0)}))
'''
check = subprocess.run([sys.executable,'-c',probe],capture_output=True,text=True)
print(check.stdout)
if check.returncode:
    print(check.stderr)
    raise RuntimeError('Môi trường GPU nền chưa hợp lệ. Nếu đã hạ numpy: Disconnect and delete runtime; không chạy pip sửa chồng tiếp.')
# Khóa các gói nhị phân ở phiên bản Colab đang có; pip không được tự thay chúng.
from importlib.metadata import version, PackageNotFoundError
from contextlib import suppress
protected = ['numpy','torch','torchvision','Pillow','opencv-python','opencv-contrib-python','opencv-python-headless']
pins=[]
for name in protected:
    with suppress(PackageNotFoundError):
        pins.append(name+'=='+version(name))
Path('/content/colab_native_constraints.txt').write_text('\\n'.join(pins)+'\\n')
COLAB_ENV = json.loads(check.stdout.strip().splitlines()[-1])
""",
)
cell(
    "code",
    """# Không cài/hạ numpy, OpenCV, torch hoặc torchvision; không kéo dependency training cũ của VietOCR.
import subprocess, sys
subprocess.run([sys.executable,'-m','pip','install','-q','--only-binary=:all:',
               '-c','/content/colab_native_constraints.txt','einops','gdown','PyYAML','requests','kagglehub'],check=True)
subprocess.run([sys.executable,'-m','pip','install','-q','--no-deps','--only-binary=:all:','vietocr==0.3.13'],check=True)
# Smoke test đúng các module notebook dùng, không import Trainer/imgaug/LMDB cũ.
import torch, torchvision, numpy, cv2
from vietocr.tool.translate import build_model, process_image
from vietocr.model.vocab import Vocab
from PIL import Image
assert process_image(Image.new('RGB',(100,32)),32,32,512).shape == (3,32,100)
assert Vocab('aAêÊ ').decode(Vocab('aAêÊ ').encode('Ê a')) == 'Ê a'
assert torch.cuda.is_available(), 'Runtime phải có GPU'
print('Colab native stack + VietOCR imports OK:',numpy.__version__,torch.__version__)
""",
)
cell(
    "code",
    """from google.colab import drive
drive.mount('/content/drive')
from pathlib import Path
SMOKE = True
RUN_NAME = 'vintext_seq2seq_v1'  # đổi khi thay cấu hình; giữ để resume cùng cấu hình
BASE = Path('/content/drive/MyDrive/vericlue_vintext')
RUN = BASE / 'runs' / (RUN_NAME + ('_smoke' if SMOKE else '_full'))
EPOCHS = 10
BATCH_SIZE = 16
LEARNING_RATE = 1e-5
BASE.mkdir(parents=True, exist_ok=True)
print('Run:', RUN)
""",
)
cell(
    "code",
    """import kagglehub
RAW = Path(kagglehub.dataset_download('hungkhoi/vietnamese-scene-text-spotting-dataset-vintext'))
print('Dataset:', RAW)
print('\n'.join(str(p.relative_to(RAW)) for p in list(RAW.rglob('*'))[:50]))
# Nếu yêu cầu đăng nhập: dùng kagglehub.login(), không ghi token vào notebook chia sẻ.
# Nếu chỉ có archive, giải nén vào /content/vintext_raw rồi đặt RAW tới thư mục đó.
""".replace("print('\n'.join", "print('\\n'.join"),
)
for name in ("vintext_recognition.py", "train_vintext.py"):
    cell(
        "code",
        f"from pathlib import Path\nPath('/content/{name}').write_text({(ROOT / name).read_text(encoding='utf-8')!r}, encoding='utf-8')\n",
    )
cell(
    "code",
    """import requests, yaml, hashlib
MODELS = BASE / 'pretrained'
MODELS.mkdir(exist_ok=True)
cfg = {}
for name in ['base.yml','vgg-seq2seq.yml']:
    response = requests.get('https://vocr.vn/data/vietocr/config/'+name, timeout=60)
    response.raise_for_status()
    cfg.update(yaml.safe_load(response.text))
weight = MODELS / 'vgg_seq2seq.pth'
if not weight.exists():
    temporary = weight.with_suffix('.part')
    with requests.get(cfg['weights'], stream=True, timeout=120) as response:
        response.raise_for_status()
        with temporary.open('wb') as f:
            for block in response.iter_content(1024*1024): f.write(block)
    temporary.replace(weight)
assert hashlib.sha256(weight.read_bytes()).hexdigest() == 'REPLACE_WEIGHT_HASH', 'Pretrained weight mismatch'
cfg['cnn']['pretrained'] = False
cfg['weights'] = str(weight)
cfg['device'] = 'cpu'
(MODELS/'local.yml').write_text(yaml.safe_dump(cfg,allow_unicode=True),encoding='utf-8')
""",
)
cell(
    "code",
    """import importlib, vintext_recognition
importlib.reload(vintext_recognition)
PREP = BASE / 'prepared_v1'
if not PREP.exists():
    print(vintext_recognition.prepare(RAW, PREP, cfg['vocab']))
import json
assert (PREP/'audit.json').exists(), 'Chuẩn bị chưa hoàn tất: dùng thư mục PREP mới để chạy lại'
audit = json.loads((PREP/'audit.json').read_text())
print('Crops:', audit['counts'], 'Rejected:', len(audit['rejected']))
print('Kiểm tra audit.json và crop trước khi train thật; test/dataset_val/unseen_test không dùng để chọn model.')
from IPython.display import display
from PIL import Image
rows = json.loads((PREP/'manifest.json').read_text())
for row in [r for r in rows if r['split']=='train'][:8]:
    print(row['text']); display(Image.open(PREP/row['crop']))
""",
)
cell(
    "code",
    """import train_vintext
importlib.reload(train_vintext)
history = train_vintext.train(PREP, MODELS, RUN, smoke=SMOKE, epochs=EPOCHS, batch_size=BATCH_SIZE, lr=LEARNING_RATE)
print('Best checkpoint:', RUN/'best.pt')
print('Nếu validation không tốt hơn pretrained, best.pt vẫn là pretrained. Không tự ghi đè model dự án.')
""",
)
cell(
    "code",
    """# Chỉ chạy sau khi đã chốt cấu hình từ validation; không dùng test để chỉnh hyperparameter.
EVALUATE_FINAL_TEST = False
if EVALUATE_FINAL_TEST:
    assert not SMOKE, 'Không báo test cho smoke run'
    from vietocr.tool.translate import build_model
    config = yaml.safe_load((RUN/'local.yml').read_text())
    config['device']='cuda:0'
    model,vocab=build_model(config)
    results={}
    for label, weights in [('pretrained',MODELS/'vgg_seq2seq.pth'),('selected',RUN/'best.pt')]:
        model.load_state_dict(torch.load(weights,map_location='cpu',weights_only=True),strict=True)
        results[label]={}
        for split in sorted({r['split'] for r in rows} - {'train','valid'}):
            data=train_vintext.Crops(PREP,[r for r in rows if r['split']==split],vocab)
            results[label][split]=train_vintext.evaluate(model,vocab,data,'cuda:0')
    target=RUN/'final_test.json'
    with target.open('x',encoding='utf-8') as f: json.dump(results,f,indent=2)
    print(results)
""",
)
cell(
    "code",
    """# ZIP chỉ gồm model/config/kết quả; không đóng gói dữ liệu VinText.
import zipfile
archive = RUN / 'vietocr_vintext_export.zip'
with zipfile.ZipFile(archive,'w',zipfile.ZIP_DEFLATED) as z:
    z.write(RUN/'best.pt','vgg_seq2seq.pth')
    export_cfg=yaml.safe_load((RUN/'local.yml').read_text())
    export_cfg['weights']='vgg_seq2seq.pth'
    z.writestr('local.yml',yaml.safe_dump(export_cfg,allow_unicode=True))
    for name in ['history.json','final_test.json']:
        if (RUN/name).exists(): z.write(RUN/name,name)
    z.writestr('scope.txt', f'SMOKE={SMOKE}; VinText scene text recognition; CCCD performance not established. No dataset included.')
from google.colab import files
files.download(str(archive))
""",
)

if __name__ == "__main__":
    import hashlib

    weight = ROOT.parents[2] / "output/vericlue_identity_lab/models/vietocr/vgg_seq2seq.pth"
    checksum = hashlib.sha256(weight.read_bytes()).hexdigest()
    for c in cells:
        c["source"] = [line.replace("REPLACE_WEIGHT_HASH", checksum) for line in c["source"]]
    notebook = {
        "cells": cells,
        "metadata": {
            "accelerator": "GPU",
            "kernelspec": {"display_name": "Python 3", "language": "python", "name": "python3"},
        },
        "nbformat": 4,
        "nbformat_minor": 5,
    }
    destination = ROOT / "finetune_vietocr_vintext_colab.ipynb"
    for i, c in enumerate(cells):
        c["id"] = f"vintext-{i:02d}"
    destination.write_text(json.dumps(notebook, ensure_ascii=False, indent=1), encoding="utf-8")
    import subprocess
    import sys

    subprocess.run([sys.executable, "-m", "ruff", "check", "--fix", str(destination)], check=False)
    subprocess.run([sys.executable, "-m", "ruff", "format", str(destination)], check=True)
    subprocess.run([sys.executable, "-m", "ruff", "check", str(destination)], check=True)
