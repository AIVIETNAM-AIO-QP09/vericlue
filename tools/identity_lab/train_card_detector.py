"""Colab detector baseline. Metrics are field-box metrics, not OCR accuracy."""

import hashlib
import json
import random
from pathlib import Path

import torch
import torchvision
from card_dataset import FIELDS, sha256
from PIL import Image
from torch.utils.data import DataLoader, Dataset
from torchvision.models.detection import fasterrcnn_mobilenet_v3_large_320_fpn
from torchvision.models.detection.faster_rcnn import FastRCNNPredictor
from torchvision.ops import box_iou
from torchvision.transforms.functional import to_tensor


class Cards(Dataset):
    def __init__(self, root, rows):
        self.root, self.rows = Path(root), rows

    def __len__(self):
        return len(self.rows)

    def __getitem__(self, index):
        row = self.rows[index]
        with Image.open(self.root / row["image"]) as image:
            tensor = to_tensor(image.convert("RGB"))
        annotations = [b for b in row["boxes"] if b["field"] in FIELDS]
        target = {
            "boxes": torch.tensor([b["xyxy"] for b in annotations], dtype=torch.float32).reshape(
                -1, 4
            ),
            "labels": torch.tensor(
                [FIELDS.index(b["field"]) + 1 for b in annotations], dtype=torch.int64
            ),
        }
        return tensor, target


def build_model(pretrained=True, image_size=640):
    model = fasterrcnn_mobilenet_v3_large_320_fpn(
        weights="DEFAULT" if pretrained else None,
        weights_backbone=None,
        min_size=image_size,
        max_size=image_size,
    )
    features = model.roi_heads.box_predictor.cls_score.in_features
    model.roi_heads.box_predictor = FastRCNNPredictor(features, len(FIELDS) + 1)
    return model


def collate(batch):
    return tuple(zip(*batch, strict=True))


@torch.inference_mode()
def evaluate(model, loader, device):
    """One-to-one matching, IoU>=.5 and score>=.5; no threshold tuning."""
    model.eval()
    stats = {name: {"tp": 0, "fp": 0, "fn": 0} for name in FIELDS}
    for images, targets in loader:
        predictions = model([image.to(device) for image in images])
        for pred, target in zip(predictions, targets, strict=True):
            pred = {k: v.cpu() for k, v in pred.items()}
            for category, name in enumerate(FIELDS, 1):
                keep = (pred["labels"] == category) & (pred["scores"] >= 0.5)
                predicted = pred["boxes"][keep]
                predicted = predicted[pred["scores"][keep].argsort(descending=True)]
                truth = target["boxes"][target["labels"] == category]
                overlaps = box_iou(predicted, truth)
                used = set()
                for scores in overlaps:
                    available = [(float(s), j) for j, s in enumerate(scores) if j not in used]
                    score, j = max(available, default=(0.0, -1))
                    if score >= 0.5:
                        used.add(j)
                        stats[name]["tp"] += 1
                    else:
                        stats[name]["fp"] += 1
                stats[name]["fn"] += len(truth) - len(used)
    tp, fp, fn = (sum(s[key] for s in stats.values()) for key in ("tp", "fp", "fn"))
    return {
        "precision": tp / max(1, tp + fp),
        "recall": tp / max(1, tp + fn),
        "f1": 2 * tp / max(1, 2 * tp + fp + fn),
        "per_class_counts": stats,
        "iou": 0.5,
        "score": 0.5,
        "metric": "micro field-box F1 (not mAP or OCR accuracy)",
    }


def save_checkpoint(path, payload):
    path = Path(path)
    temporary = path.with_suffix(".tmp")
    torch.save(payload, temporary)
    temporary.replace(path)


def checkpoint_config_diff(old_config, config):
    """Accept absent legacy grouping metadata only for the identical manifest."""
    old_config = dict(old_config)
    if (
        "grouping" not in old_config
        and config.get("manifest_sha256")
        and old_config.get("manifest_sha256") == config["manifest_sha256"]
    ):
        old_config["grouping"] = config.get("grouping")
    return {
        key: {"checkpoint": old_config.get(key), "current": config.get(key)}
        for key in sorted(old_config.keys() | config.keys())
        if old_config.get(key) != config.get(key)
    }


def train(
    root,
    rows,
    out,
    smoke=True,
    epochs=15,
    batch_size=2,
    resume=True,
    allow_cpu=False,
    pretrained=True,
):
    if not torch.cuda.is_available() and not allow_cpu:
        raise RuntimeError("Colab: Runtime > Change runtime type > T4 GPU")
    if not smoke and any(not r.get("group_id") for r in rows):
        raise ValueError(
            "Full training requires group IDs; use manual or provisional auto grouping"
        )
    random.seed(42)
    torch.manual_seed(42)
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    train_rows = [r for r in rows if r["split"] == "train"]
    valid_rows = [r for r in rows if r["split"] == "valid"]
    if smoke:
        train_rows, valid_rows, epochs = train_rows[:8], valid_rows[:4], 1
    if not train_rows or not valid_rows:
        raise ValueError("Empty train/validation split")
    loaders = [
        DataLoader(
            Cards(root, subset),
            batch_size=batch_size,
            shuffle=is_train,
            num_workers=0,
            collate_fn=collate,
        )
        for subset, is_train in ((train_rows, True), (valid_rows, False))
    ]
    fingerprint = hashlib.sha256(json.dumps(rows, sort_keys=True).encode()).hexdigest()
    config = {
        "smoke": smoke,
        "manifest_sha256": fingerprint,
        "fields": FIELDS,
        "image_size": 640,
        "lr": 0.0001,
        "batch_size": batch_size,
        "torch": str(torch.__version__),
        "torchvision": str(torchvision.__version__),
        "pretrained": pretrained,
        "seed": 42,
        "grouping": "provisional_ocr"
        if any(r.get("group_source") for r in rows)
        else "provided_groups",
    }
    last = out / "last.pt"
    checkpoint = (
        torch.load(last, map_location="cpu", weights_only=True)
        if resume and last.exists()
        else None
    )
    differences = checkpoint_config_diff(checkpoint["config"], config) if checkpoint else {}
    if differences:
        raise ValueError(
            f"Checkpoint incompatible: {last}\n"
            + json.dumps(differences, ensure_ascii=False, indent=2)
            + "\nĐể tiếp tục run cũ, khôi phục đúng cấu hình/dữ liệu/môi trường. "
            "Để train mới, đổi RUN_NAME và tính lại RUN = BASE / 'runs' / RUN_NAME. "
            "Giữ checkpoint cũ; RESUME=False không ghi đè run đã tồn tại."
        )
    if not resume and last.exists():
        raise ValueError("Run already exists; choose a new RUN_NAME")
    model = build_model(pretrained=pretrained and checkpoint is None).to(device)
    optimizer = torch.optim.AdamW([p for p in model.parameters() if p.requires_grad], lr=0.0001)
    start, best, history = 0, -1.0, []
    if checkpoint:
        model.load_state_dict(checkpoint["model"])
        optimizer.load_state_dict(checkpoint["optimizer"])
        torch.set_rng_state(checkpoint["rng"])
        if device.type == "cuda" and checkpoint.get("cuda_rng"):
            torch.cuda.set_rng_state_all(checkpoint["cuda_rng"])
        start, best, history = checkpoint["epoch"] + 1, checkpoint["best"], checkpoint["history"]
    (out / "manifest.json").write_text(
        json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    for epoch in range(start, epochs):
        model.train()
        loss_sum = 0.0
        for images, targets in loaders[0]:
            images = [image.to(device) for image in images]
            targets = [{k: v.to(device) for k, v in target.items()} for target in targets]
            optimizer.zero_grad(set_to_none=True)
            loss = sum(model(images, targets).values())
            if not torch.isfinite(loss):
                raise RuntimeError("Nonfinite loss: stop and inspect data")
            loss.backward()
            torch.nn.utils.clip_grad_norm_(model.parameters(), 10.0)
            optimizer.step()
            loss_sum += float(loss.detach())
        metrics = evaluate(model, loaders[1], device)
        history.append(
            {"epoch": epoch + 1, "train_loss": loss_sum / len(loaders[0]), "validation": metrics}
        )
        improved = metrics["f1"] > best
        best = max(best, metrics["f1"])
        payload = {
            "model": model.state_dict(),
            "optimizer": optimizer.state_dict(),
            "epoch": epoch,
            "best": best,
            "history": history,
            "config": config,
            "rng": torch.get_rng_state(),
            "cuda_rng": torch.cuda.get_rng_state_all() if device.type == "cuda" else [],
        }
        if improved:
            save_checkpoint(out / "best.pt", payload)
        save_checkpoint(last, payload)
        (out / "metrics.json").write_text(json.dumps(history, indent=2), encoding="utf-8")
        print(
            f"Epoch {epoch + 1}/{epochs}: loss={history[-1]['train_loss']:.4f}, val field-box F1={metrics['f1']:.4f}",
            flush=True,
        )
    (out / "checkpoint_sha256.txt").write_text(sha256(out / "best.pt"), encoding="utf-8")
    return history
