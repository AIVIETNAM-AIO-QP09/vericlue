"""VietOCR recognition fine-tuning with resumable epoch checkpoints and held-out validation."""

import json
import random
from importlib.metadata import version
from pathlib import Path

import numpy as np
import torch
import yaml
from PIL import Image
from torch.utils.data import DataLoader, Dataset
from vintext_recognition import digest


def distance(a, b):
    prev = list(range(len(b) + 1))
    for i, x in enumerate(a, 1):
        cur = [i]
        for j, y in enumerate(b, 1):
            cur.append(min(cur[-1] + 1, prev[j] + 1, prev[j - 1] + (x != y)))
        prev = cur
    return prev[-1]


class Crops(Dataset):
    def __init__(self, root, rows, vocab):
        self.root, self.rows, self.vocab = Path(root), rows, vocab

    def __len__(self):
        return len(self.rows)

    def __getitem__(self, index):
        from vietocr.tool.translate import process_image

        row = self.rows[index]
        path = (self.root / row["crop"]).resolve()
        if not path.is_relative_to(self.root.resolve()):
            raise ValueError("Crop outside dataset")
        with Image.open(path) as source:
            image = process_image(source, 32, 32, 512)
        return torch.tensor(image, dtype=torch.float32), self.vocab.encode(row["text"])


def collate(items):
    width = max(im.shape[2] for im, _ in items)
    length = max(len(tokens) - 1 for _, tokens in items)
    images = torch.ones(len(items), 3, 32, width)
    inputs = torch.zeros(length, len(items), dtype=torch.long)
    targets = torch.zeros(len(items), length, dtype=torch.long)
    for i, (im, tokens) in enumerate(items):
        images[i, :, :, : im.shape[2]] = im
        inputs[: len(tokens) - 1, i] = torch.tensor(tokens[:-1])
        targets[i, : len(tokens) - 1] = torch.tensor(tokens[1:])
    return images, inputs, targets


def evaluate(model, vocab, dataset, device):
    from vietocr.tool.translate import translate

    errors = chars = exact = 0
    model.eval()
    with torch.inference_mode():
        for i, row in enumerate(dataset.rows):
            image, _ = dataset[i]
            ids, _ = translate(image.unsqueeze(0).to(device), model, max_seq_length=128)
            prediction = vocab.decode(ids[0].tolist())
            expected = row["text"]
            errors += distance(prediction, expected)
            chars += len(expected)
            exact += prediction == expected
    if not len(dataset) or not chars:
        raise ValueError("Empty evaluation")
    return {"samples": len(dataset), "cer": errors / chars, "exact_match": exact / len(dataset)}


def save(path, value):
    temporary = path.with_suffix(".tmp")
    torch.save(value, temporary)
    temporary.replace(path)


def train(dataset, model_dir, out, smoke=True, epochs=10, batch_size=16, lr=1e-5):
    from vietocr.tool.translate import build_model

    if not torch.cuda.is_available():
        raise RuntimeError("Enable Colab T4 GPU before training")
    if epochs < 1 or batch_size < 1 or not 0 < lr < 1:
        raise ValueError("Invalid training settings")
    dataset, model_dir, out = map(Path, (dataset, model_dir, out))
    rows = json.loads((dataset / "manifest.json").read_text(encoding="utf-8"))
    selected = {s: [r for r in rows if r["split"] == s] for s in ("train", "valid")}
    if smoke:
        selected = {s: rs[: 32 if s == "train" else 16] for s, rs in selected.items()}
        epochs = 1
    if any(not rs for rs in selected.values()):
        raise ValueError("Empty train/valid split")
    if {r["source_pixel_sha256"] for r in selected["train"]} & {
        r["source_pixel_sha256"] for r in selected["valid"]
    }:
        raise ValueError("Train/valid source leakage")
    for rs in selected.values():
        for row in rs:
            path = (dataset / row["crop"]).resolve()
            if not path.is_relative_to(dataset.resolve()) or digest(path) != row["crop_sha256"]:
                raise ValueError("Crop changed or unsafe path")
    config = yaml.safe_load((model_dir / "local.yml").read_text(encoding="utf-8"))
    config["device"] = "cuda:0"
    config["cnn"]["pretrained"] = False
    config["predictor"]["beamsearch"] = False
    initial = model_dir / "vgg_seq2seq.pth"
    signature = {
        "manifest": digest(dataset / "manifest.json"),
        "initial_weights": digest(initial),
        "config": digest(model_dir / "local.yml"),
        "smoke": smoke,
        "epochs": epochs,
        "batch_size": batch_size,
        "lr": lr,
        "script": digest(__file__),
        "versions": {n: version(n) for n in ("torch", "torchvision", "vietocr", "numpy", "Pillow")},
    }
    out.mkdir(parents=True, exist_ok=True)
    last = out / "last.pt"
    if not last.exists() and any(out.iterdir()):
        raise ValueError("Run folder contains files but no checkpoint; choose new run")
    checkpoint = torch.load(last, map_location="cpu", weights_only=False) if last.exists() else None
    if checkpoint and checkpoint["signature"] != signature:
        raise ValueError(
            "Checkpoint incompatible: choose new RUN_NAME; never overwrite smoke with full training"
        )
    torch.manual_seed(2026)
    random.seed(2026)
    np.random.seed(2026)
    model, vocab = build_model(config)
    model.load_state_dict(torch.load(initial, map_location="cpu", weights_only=True), strict=True)
    optimizer = torch.optim.AdamW(model.parameters(), lr=lr, weight_decay=1e-4)
    data = {s: Crops(dataset, rs, vocab) for s, rs in selected.items()}
    history = []
    best = float("inf")
    start = 0
    if checkpoint:
        model.load_state_dict(checkpoint["model"])
        optimizer.load_state_dict(checkpoint["optimizer"])
        start = checkpoint["epoch"] + 1
        best = checkpoint["best"]
        history = checkpoint["history"]
        torch.set_rng_state(checkpoint["rng"])
        torch.cuda.set_rng_state_all(checkpoint["cuda_rng"])
    else:
        baseline = evaluate(model, vocab, data["valid"], "cuda:0")
        history.append({"epoch": -1, "validation": baseline})
        best = baseline["cer"]
        save(out / "best.pt", model.state_dict())
        config["weights"] = "best.pt"
        config["device"] = "cpu"
        (out / "local.yml").write_text(yaml.safe_dump(config, allow_unicode=True), encoding="utf-8")
        print("Pretrained validation:", baseline, flush=True)
    for epoch in range(start, epochs):
        generator = torch.Generator().manual_seed(2026 + epoch)
        loader = DataLoader(
            data["train"],
            batch_size=batch_size,
            shuffle=True,
            collate_fn=collate,
            num_workers=0,
            generator=generator,
        )
        losses = []
        for images, inputs, targets in loader:
            model.train()
            optimizer.zero_grad(set_to_none=True)
            images, inputs, targets = [x.to("cuda:0") for x in (images, inputs, targets)]
            outputs = model(images, inputs, tgt_key_padding_mask=targets.eq(0))
            loss = torch.nn.functional.cross_entropy(
                outputs.reshape(-1, outputs.shape[-1]), targets.reshape(-1), ignore_index=0
            )
            if not torch.isfinite(loss):
                raise RuntimeError("Nonfinite loss; stopped before saving checkpoint")
            loss.backward()
            torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
            optimizer.step()
            losses.append(loss.item())
        metrics = evaluate(model, vocab, data["valid"], "cuda:0")
        if metrics["cer"] < best:
            best = metrics["cer"]
            save(out / "best.pt", model.state_dict())
        history.append({"epoch": epoch, "loss": sum(losses) / len(losses), "validation": metrics})
        save(
            last,
            {
                "signature": signature,
                "epoch": epoch,
                "model": model.state_dict(),
                "optimizer": optimizer.state_dict(),
                "best": best,
                "history": history,
                "rng": torch.get_rng_state(),
                "cuda_rng": torch.cuda.get_rng_state_all(),
            },
        )
        (out / "history.json").write_text(json.dumps(history, indent=2), encoding="utf-8")
        print(history[-1], flush=True)
    return history
