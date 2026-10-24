"""Local Qwen microphone lab; explicit record action, no audio files or API decision."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from time import perf_counter
from typing import Any

from vericlue_ml.eval.microphone import MAX_RECORD_SECONDS
from vericlue_ml.eval.voice_trial import VoiceTrial
from vericlue_ml.voice.phrases import generate_prompt
from vericlue_ml.voice.qwen_asr import QwenASR, QwenVoiceChallengeDetector


def write_report(path: Path, payload: dict, *, models_dir: Path) -> None:
    """Explicit JSON export; never overwrite an existing file or write into weights."""
    path = path.resolve()
    if path.is_relative_to(models_dir.resolve()):
        raise ValueError("Không lưu báo cáo vào thư mục trọng số.")
    with path.open("x", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, ensure_ascii=False, indent=2) + "\n")


class VoiceLab:
    """Internal diagnostic window; model and microphone are lazy, UI stays responsive."""

    def __init__(
        self, root: Any, *, models_dir: Path, device: int | None = None, preview: bool = False
    ) -> None:
        import tkinter as tk
        from tkinter import ttk

        self.root, self.preview = root, preview
        self.models_dir = models_dir.resolve()
        self.trial = VoiceTrial(QwenVoiceChallengeDetector(QwenASR(models_dir)), device=device)
        self.closed = False
        self.phase = "idle"
        self.record_started = 0.0
        self.payload = None
        self.prompt = generate_prompt()
        root.title("VeriClue · Thử câu đọc" + (" · xem thử" if preview else ""))
        root.geometry("850x690")
        root.minsize(760, 640)
        root.configure(bg="#F8FAFC")
        style = ttk.Style(root)
        style.theme_use("clam")
        style.configure("TFrame", background="#F8FAFC")
        style.configure("TLabel", background="#F8FAFC", foreground="#0F172A", font=("Segoe UI", 11))
        style.configure("TButton", font=("Segoe UI", 11), padding=(12, 10))
        style.configure("Record.TButton", background="#1D4ED8", foreground="white")
        style.map(
            "Record.TButton",
            background=[("disabled", "#64748B"), ("active", "#1E40AF")],
            foreground=[("disabled", "white")],
        )
        body = ttk.Frame(root, padding=24)
        body.pack(fill="both", expand=True)
        ttk.Label(body, text="Thử câu đọc", font=("Segoe UI", 23, "bold")).pack(anchor="w")
        ttk.Label(body, text="Nội bộ phát triển · Qwen3-ASR-0.6B · xử lý trên máy").pack(anchor="w")
        ttk.Label(
            body, text="Đọc nguyên câu dưới đây sau khi trạng thái chuyển sang ĐANG THU."
        ).pack(anchor="w", pady=(24, 8))
        self.prompt_text = tk.StringVar(value=self.prompt)
        ttk.Label(
            body, textvariable=self.prompt_text, font=("Segoe UI", 19, "bold"), wraplength=750
        ).pack(anchor="w", fill="x", pady=(0, 20))
        controls = ttk.Frame(body)
        controls.pack(fill="x")
        self.record_button = ttk.Button(
            controls, text="1. Thu âm", style="Record.TButton", command=self.start
        )
        self.record_button.pack(side="left", padx=(0, 8))
        self.finish_button = ttk.Button(controls, text="2. Dừng & kiểm câu", command=self.finish)
        self.finish_button.pack(side="left", padx=(0, 8))
        self.cancel_button = ttk.Button(controls, text="Hủy (Esc)", command=self.cancel)
        self.cancel_button.pack(side="left")
        self.new_button = ttk.Button(controls, text="Đổi câu", command=self.new_prompt)
        self.new_button.pack(side="right")
        self.status_text = tk.StringVar(value="MICRO ĐANG TẮT · Sẵn sàng")
        ttk.Label(body, textvariable=self.status_text, wraplength=750).pack(
            anchor="w", fill="x", pady=(18, 8)
        )
        self.progress = ttk.Progressbar(body, mode="indeterminate")
        self.progress.pack(fill="x", pady=(0, 12))
        self.result_text = tk.Text(
            body,
            height=9,
            wrap="word",
            font=("Segoe UI", 12),
            bg="white",
            fg="#0F172A",
            relief="flat",
            padx=14,
            pady=12,
            takefocus=True,
        )
        self._result("Chưa có kết quả. Micro chỉ mở khi bạn bấm Thu âm.")
        footer = ttk.Frame(body)
        footer.pack(side="bottom", fill="x", pady=(12, 0))
        self.save_button = ttk.Button(footer, text="Lưu JSON (có câu đọc)", command=self.save)
        self.save_button.pack(anchor="w")
        ttk.Label(
            footer,
            text=(
                f"Tối đa {MAX_RECORD_SECONDS} giây/lượt · Âm thanh chỉ trong RAM, không ghi file.\n"
                "Khớp câu chưa chứng minh giọng thật, khớp môi hoặc xác minh thành công."
            ),
            wraplength=750,
        ).pack(anchor="w", pady=(10, 0))
        self.result_text.pack(fill="both", expand=True)
        root.bind("<Escape>", lambda _: self.cancel())
        root.protocol("WM_DELETE_WINDOW", self.close)
        self._buttons()
        root.after(100, self.tick)

    def _result(self, text: str) -> None:
        self.result_text.configure(state="normal")
        self.result_text.delete("1.0", "end")
        self.result_text.insert("1.0", text)
        self.result_text.configure(state="disabled")

    def _buttons(self) -> None:
        idle = not self.preview and not self.trial.active
        self.record_button.configure(state="normal" if idle else "disabled")
        self.new_button.configure(state="normal" if idle else "disabled")
        self.finish_button.configure(state="normal" if self.phase == "recording" else "disabled")
        self.cancel_button.configure(state="normal" if self.trial.active else "disabled")
        self.save_button.configure(state="normal" if self.payload and idle else "disabled")

    def start(self) -> None:
        if self.preview or not self.trial.start(self.prompt):
            return
        self.payload = None
        self.phase = "opening"
        self.status_text.set("Đang mở micro… Chờ thông báo ĐANG THU rồi bắt đầu đọc.")
        self._result("Chưa có kết quả cho lượt này.")
        self.progress.start(12)
        self._buttons()

    def finish(self) -> None:
        if self.phase != "recording":
            return
        self.phase = "stopping"
        self.status_text.set("Đang tắt micro và chuyển sang kiểm câu…")
        self.trial.finish()
        self._buttons()

    def cancel(self) -> None:
        if not self.trial.active:
            return
        self.trial.cancel()
        self.payload = None
        self.phase = "cancelling"
        self.status_text.set("Đã yêu cầu hủy · Chờ tác vụ hiện tại kết thúc để thử lại.")
        self._result("Lượt này đã hủy; kết quả sẽ bị bỏ qua.")
        self._buttons()

    def new_prompt(self) -> None:
        if self.trial.active or self.preview:
            return
        self.prompt = generate_prompt(self.prompt)
        self.prompt_text.set(self.prompt)
        self.payload = None
        self._result("Đã đổi câu. Bấm Thu âm để bắt đầu lượt mới.")
        self._buttons()

    def tick(self) -> None:
        if self.closed:
            return
        for kind, value in self.trial.poll():
            if kind == "recording":
                self.phase = "recording"
                self.record_started = perf_counter()
            elif kind == "processing":
                self.phase = "processing"
                self.status_text.set("MICRO ĐÃ TẮT · Đang kiểm câu. Lần đầu cần nạp model CPU.")
            elif kind == "done":
                self.payload, error = value
                self.phase = "idle"
                self.progress.stop()
                self.status_text.set("MICRO ĐANG TẮT · Lượt đã kết thúc")
                if self.payload:
                    self.render_result()
                elif error:
                    self._result(error + "\nChưa có kết quả kiểm câu; không được coi là đạt.")
            self._buttons()
        if self.phase == "recording":
            elapsed = perf_counter() - self.record_started
            self.status_text.set(
                f"ĐANG THU · khoảng {elapsed:.1f} / {MAX_RECORD_SECONDS} giây · Đọc xong bấm Dừng & kiểm câu"
            )
        self.root.after(100, self.tick)

    def render_result(self) -> None:
        result = self.payload["result"]
        if result["status"] == "ok":
            summary = "KHỚP CÂU" if result["gate"] == "pass" else "CHƯA KHỚP CÂU"
        else:
            summary = "CHƯA THỂ KIỂM CÂU · thử lại hoặc kiểm tra runtime"
        evidence = {item["name"]: item["value"] for item in result.get("evidence", [])}
        quality = result.get("quality", {})
        details = ""
        if "syllable_error_rate" in quality:
            details = (
                f"\nSai lệch âm tiết (WER): {quality['syllable_error_rate']:.3f} — thấp hơn là tốt hơn"
                f"\nĐộ giống khi bỏ dấu: {quality['unaccented_similarity']:.3f} — cao hơn là tốt hơn"
            )
        self._result(
            f"{summary}\nMáy nghe: {evidence.get('recognized_text', 'Chưa có bản nhận dạng')}"
            f"{details}\nThời gian xử lý: {result['latency_ms'] / 1000:.2f} giây"
            f"\nTrạng thái kỹ thuật: {result['status']} / {result['gate']}"
            f"\nMã lý do: {result.get('error_code') or 'không'}"
        )

    def save(self) -> None:
        from tkinter import filedialog, messagebox

        if not self.payload or self.trial.active or self.preview:
            return
        selected = filedialog.asksaveasfilename(
            parent=self.root,
            title="Lưu kết quả có transcript, không chứa âm thanh",
            defaultextension=".json",
            filetypes=[("JSON", "*.json")],
        )
        if not selected:
            return
        path = Path(selected).resolve()
        try:
            write_report(path, self.payload, models_dir=self.models_dir)
        except (OSError, ValueError) as exc:
            messagebox.showerror("Chưa lưu được", str(exc), parent=self.root)

    def close(self) -> None:
        self.closed = True
        self.trial.close()
        self.root.destroy()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--models-dir", type=Path, default=Path(os.getenv("MODELS_DIR", "models")))
    parser.add_argument(
        "--device", type=int, help="PortAudio input device index; default: OS input"
    )
    parser.add_argument(
        "--ui-preview", action="store_true", help="Disable microphone and model work"
    )
    args = parser.parse_args(argv)
    import tkinter as tk

    root = tk.Tk()
    VoiceLab(root, models_dir=args.models_dir, device=args.device, preview=args.ui_preview)
    root.mainloop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
