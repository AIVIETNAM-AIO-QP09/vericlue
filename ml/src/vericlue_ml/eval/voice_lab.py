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
        self,
        root: Any,
        *,
        models_dir: Path,
        device: int | None = None,
        preview: bool = False,
        nes2net_python: Path | None = None,
        worker_timeout: float = 180,
        with_reading_timing: bool = False,
    ) -> None:
        import tkinter as tk
        from tkinter import ttk

        self.root, self.preview = root, preview
        self.models_dir = models_dir.resolve()
        spoof = None
        timing = None
        if with_reading_timing and not preview:
            from vericlue_ml.voice.reading_timing import ReadingTimingDetector

            timing = ReadingTimingDetector(self.models_dir)
        if nes2net_python is not None and not preview:
            from vericlue_ml.eval.nes2net_client import Nes2NetClient

            spoof = Nes2NetClient(nes2net_python, self.models_dir, timeout=worker_timeout)
        self.trial = VoiceTrial(
            QwenVoiceChallengeDetector(QwenASR(self.models_dir)),
            device=device,
            spoof=spoof,
            timing=timing,
        )
        self.closed = False
        self.phase = "idle"
        self.record_started = 0.0
        self.payload = None
        self.prompt = generate_prompt()
        root.title("VeriClue · Thử giọng nói" + (" · xem thử" if preview else ""))
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
        self.header_label = ttk.Label(body, text="Thử giọng nói", font=("Segoe UI", 23, "bold"))
        self.header_label.pack(anchor="w")
        self.subtitle_label = ttk.Label(
            body,
            text=(
                "Nội bộ phát triển · Qwen3-ASR"
                + (" + NES2Net-X" if nes2net_python else "")
                + (" + CTC" if with_reading_timing else "")
                + " · xử lý trên máy"
            ),
        )
        self.subtitle_label.pack(anchor="w")
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
        self.finish_button = ttk.Button(controls, text="2. Dừng & kiểm", command=self.finish)
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
        self.tabs = ttk.Notebook(body)
        content_tab, spoof_tab, timing_tab = [ttk.Frame(self.tabs) for _ in range(3)]
        self.tabs.add(content_tab, text="Câu đọc")
        self.tabs.add(spoof_tab, text="Giọng AI · 4 giây đầu")
        self.tabs.add(timing_tab, text="Nhịp đọc")
        self.result_text = tk.Text(
            content_tab,
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
        self.spoof_text = tk.Text(
            spoof_tab,
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
        self.timing_text = tk.Text(
            timing_tab,
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
        for tab, widget in (
            (content_tab, self.result_text),
            (spoof_tab, self.spoof_text),
            (timing_tab, self.timing_text),
        ):
            scroll = ttk.Scrollbar(tab, orient="vertical", command=widget.yview)
            scroll.pack(side="right", fill="y")
            widget.configure(yscrollcommand=scroll.set)
            widget.pack(side="left", fill="both", expand=True)
        self._spoof_result(
            "Chưa có điểm giọng AI."
            if nes2net_python
            else "Chưa bật NES2Net trong lần chạy này. Xem hướng dẫn để bật kiểm giọng."
        )
        self._result("Chưa có kết quả. Micro chỉ mở khi bạn bấm Thu âm.")
        self._timing_result(
            "Chưa có mốc nhịp đọc. CTC dùng chung lượt thu, không cần đọc thêm."
            if with_reading_timing
            else "Chưa bật nhịp đọc. Chạy với --with-reading-timing để bật."
        )
        footer = ttk.Frame(body)
        footer.pack(side="bottom", fill="x", pady=(12, 0))
        self.save_button = ttk.Button(footer, text="Lưu JSON (có câu đọc)", command=self.save)
        self.save_button.pack(anchor="w")
        self.footer_note = ttk.Label(
            footer,
            text=(
                f"Tối đa {MAX_RECORD_SECONDS} giây/lượt · Âm thanh chỉ trong RAM, không ghi file.\n"
                "Khớp câu chưa chứng minh giọng thật, khớp môi hoặc xác minh thành công."
            ),
            wraplength=750,
        )
        self.footer_note.pack(anchor="w", pady=(10, 0))
        self.tabs.pack(fill="both", expand=True)
        root.bind("<Escape>", lambda _: self.cancel())
        root.protocol("WM_DELETE_WINDOW", self.close)
        self._buttons()
        root.after(100, self.tick)

    def _result(self, text: str) -> None:
        self.result_text.configure(state="normal")
        self.result_text.delete("1.0", "end")
        self.result_text.insert("1.0", text)
        self.result_text.configure(state="disabled")

    def _spoof_result(self, text: str) -> None:
        self.spoof_text.configure(state="normal")
        self.spoof_text.delete("1.0", "end")
        self.spoof_text.insert("1.0", text)
        self.spoof_text.configure(state="disabled")

    def _buttons(self) -> None:
        idle = not self.preview and not self.trial.active
        self.record_button.configure(state="normal" if idle else "disabled")
        self.new_button.configure(state="normal" if idle else "disabled")
        self.finish_button.configure(state="normal" if self.phase == "recording" else "disabled")
        self.cancel_button.configure(state="normal" if self.trial.active else "disabled")
        self.save_button.configure(state="normal" if self.payload and idle else "disabled")

    def _timing_result(self, text: str) -> None:
        self.timing_text.configure(state="normal")
        self.timing_text.delete("1.0", "end")
        self.timing_text.insert("1.0", text)
        self.timing_text.configure(state="disabled")

    def start(self) -> None:
        if self.preview or not self.trial.start(self.prompt):
            return
        self.payload = None
        self.phase = "opening"
        self.status_text.set("Đang mở micro… Chờ thông báo ĐANG THU rồi bắt đầu đọc.")
        self._result("Chưa có kết quả cho lượt này.")
        self._spoof_result("Chưa có điểm cho lượt này.")
        self._timing_result("Chưa có mốc nhịp đọc cho lượt này.")
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
        self._spoof_result("Lượt này đã hủy; điểm giọng sẽ bị bỏ qua.")
        self._timing_result("Lượt này đã hủy; mốc nhịp đọc sẽ bị bỏ qua.")
        self._buttons()

    def new_prompt(self) -> None:
        if self.trial.active or self.preview:
            return
        self.prompt = generate_prompt(self.prompt)
        self.prompt_text.set(self.prompt)
        self.payload = None
        self._result("Đã đổi câu. Bấm Thu âm để bắt đầu lượt mới.")
        self._spoof_result("Chưa có điểm cho lượt mới.")
        self._timing_result("Chưa có mốc nhịp đọc cho lượt mới.")
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
            elif kind == "spoof_processing":
                self.phase = "processing"
                self.status_text.set(
                    "MICRO ĐÃ TẮT · Đang đo điểm NES2Net; lần đầu cần nạp model riêng."
                )
            elif kind == "timing_processing":
                self.phase = "processing"
                self.status_text.set(
                    "MICRO ĐÃ TẮT · Đang căn mốc âm tiết bằng CTC; lần đầu cần nạp model."
                )
            elif kind == "lipsync_processing":
                self.phase = "processing"
                self.status_text.set("MICRO ĐÃ TẮT · Đang chấm SyncNet trên đoạn câu đã căn.")
            elif kind == "done":
                self.payload, error = value
                self.phase = "idle"
                self.progress.stop()
                self.status_text.set("MICRO ĐANG TẮT · Lượt đã kết thúc")
                if self.payload:
                    self.render_result()
                    self.render_spoof()
                    self.render_timing()
                    if self.payload.get("reading_timing"):
                        self.status_text.set(
                            "MICRO ĐANG TẮT · Đã xong · Xem riêng từng tab kết quả"
                        )
                    elif self.payload.get("voice_spoof"):
                        self.status_text.set(
                            "MICRO ĐANG TẮT · Xem riêng hai tab Câu đọc và Giọng AI"
                        )
                elif error:
                    self._result(error + "\nChưa có kết quả kiểm câu; không được coi là đạt.")
                    self._spoof_result("Chưa có kết quả giọng AI cho lượt này.")
                    self._timing_result("Chưa có mốc nhịp đọc cho lượt này.")
            self._buttons()
        if self.phase == "recording":
            elapsed = perf_counter() - self.record_started
            self.status_text.set(
                f"ĐANG THU · khoảng {elapsed:.1f} / {MAX_RECORD_SECONDS} giây · Đọc xong bấm Dừng & kiểm"
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

    def render_spoof(self) -> None:
        payload = self.payload.get("voice_spoof")
        if not payload:
            self._spoof_result(
                "NES2Net chưa bật trong lần chạy này. Kết quả câu đọc vẫn được giữ riêng."
            )
            return
        result = payload["result"]
        score = result.get("score")
        if score is None or result["status"] != "degraded":
            text = "CHƯA ĐO ĐƯỢC ĐIỂM GIỌNG AI · thử lại hoặc kiểm tra runtime"
        else:
            text = (
                "CHƯA KẾT LUẬN GIỌNG THẬT / GIẢ"
                f"\nĐiểm thô NES2Net (giả − thật): {score:.4f}"
                "\nĐiểm cao hơn nghiêng về giọng giả trong mô hình; chưa phải xác suất."
            )
        self._spoof_result(
            text + "\nChỉ chấm 4 giây đầu; âm thanh ngắn hơn sẽ được lặp."
            "\nChưa xác minh tương đương bản gốc hoặc hiệu chỉnh cho tiếng Việt."
            f"\nTrạng thái kỹ thuật: {result['status']} / {result['gate']}"
            f"\nMã lý do: {result.get('error_code') or 'không'}"
            f"\nThời gian worker/trao đổi: {payload.get('round_trip_ms', 0) / 1000:.2f} giây"
        )

    def render_timing(self) -> None:
        payload = self.payload.get("reading_timing")
        if not payload:
            self._timing_result("Chưa bật kiểm nhịp đọc trong lần chạy này.")
            return
        result = payload["result"]
        evidence = {item["name"]: item["value"] for item in result.get("evidence", [])}
        spans = evidence.get("timing_syllables", [])
        quality = result.get("quality", {})
        if result["status"] != "degraded" or not spans:
            self._timing_result(
                "CHƯA CĂN ĐƯỢC NHỊP ĐỌC · thử lại hoặc kiểm tra CTC/runtime"
                f"\nTrạng thái: {result['status']} / {result['gate']}"
                f"\nMã lý do: {result.get('error_code') or 'không'}"
                "\nKết quả câu đọc và giọng AI được giữ riêng."
            )
            return
        content = self.payload["result"]
        text = "MỐC ÉP CĂN THEO CÂU YÊU CẦU · CHỈ THAM KHẢO"
        if content.get("status") != "ok" or content.get("gate") != "pass":
            text += "\nCâu chưa khớp hoặc chưa nhận dạng được; mốc ép căn có thể sai."
        text += (
            "\nKhông chứng minh đọc đúng, giọng thật hoặc có cắt ghép."
            f"\nTốc độ trong đoạn căn (gồm khoảng ngắt): {quality['syllables_per_second_including_gaps']:.2f} âm tiết/giây"
            f"\nĐoạn căn: {quality['aligned_span_seconds']:.2f} giây · {len(spans)} âm tiết"
            f"\nKhoảng ngắt dài nhất giữa âm tiết: {quality['longest_gap_seconds']:.2f} giây"
            f"\nCờ thời lượng theo luật tạm: {int(quality['timing_flag_count'])}"
            "\n\nMốc trên bản thu gốc (giây):"
        )
        for row in spans:
            text += f"\n{row['text']}: {row['start_s']:.2f} → {row['end_s']:.2f} ({row['duration_s']:.2f} s)"
        labels = {
            "short_syllable": "Âm tiết ngắn",
            "long_syllable": "Âm tiết dài",
            "long_pause": "Khoảng ngắt dài",
            "long_star": "Vùng chưa gán âm tiết dài",
        }
        for row in evidence.get("timing_flags", []):
            text += f"\n{labels.get(row['kind'], 'Cờ thời lượng')}: {row['start_s']:.2f} → {row['end_s']:.2f} s"
        text += f"\n\nThời gian CTC: {result['latency_ms'] / 1000:.2f} giây · {result['status']} / {result['gate']}"
        self._timing_result(text)

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
    parser.add_argument(
        "--nes2net-python", type=Path, help="Opt in using the separate NES2Net Python executable"
    )
    parser.add_argument(
        "--worker-timeout", type=float, default=180, help="NES2Net timeout, 0–600 seconds"
    )
    parser.add_argument(
        "--with-reading-timing", action="store_true", help="Opt in to raw CTC syllable timing"
    )
    args = parser.parse_args(argv)
    import tkinter as tk

    root = tk.Tk()
    VoiceLab(
        root,
        models_dir=args.models_dir,
        device=args.device,
        preview=args.ui_preview,
        nes2net_python=args.nes2net_python,
        worker_timeout=args.worker_timeout,
        with_reading_timing=args.with_reading_timing,
    )
    root.mainloop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
