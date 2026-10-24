"""Opt-in Windows camera/microphone lab with one DirectShow A/V input and RAM SyncNet."""

from __future__ import annotations

import argparse
import json
import queue
import threading
from contextlib import suppress
from pathlib import Path

from vericlue_ml.eval.av_capture import AVRecorder, ffmpeg_path, list_devices
from vericlue_ml.eval.voice_lab import VoiceLab


class AVLab(VoiceLab):
    def __init__(
        self,
        root,
        *,
        models_dir: Path,
        lipsync_models_dir: Path,
        ffmpeg: Path | None = None,
        video_device: str = "",
        audio_device: str = "",
        nes2net_python: Path | None = None,
        worker_timeout: float = 180,
        preview: bool = False,
    ) -> None:
        import tkinter as tk
        from tkinter import ttk

        super().__init__(
            root,
            models_dir=models_dir,
            nes2net_python=nes2net_python,
            worker_timeout=worker_timeout,
            with_reading_timing=True,
            preview=preview,
        )
        self.binary = ffmpeg_path(ffmpeg) if not preview else Path("disabled-preview")
        self.recorder = None
        if not preview:
            from vericlue_ml.voice.av_lipsync import RamLipSyncDetector

            self.recorder = AVRecorder(self.binary)
            self.trial.recorder = self.recorder
            self.trial.failure_message = "Không thể thu hoặc xử lý hình–tiếng. Kiểm tra camera, micro, quyền truy cập và runtime."
            self.trial.lipsync = RamLipSyncDetector(
                lipsync_models_dir, aligner=self.trial.timing.aligner
            )
        self.video_device, self.audio_device = video_device, audio_device
        self.device_results = queue.SimpleQueue()
        self.device_dialog = None
        self.device_epoch = 0
        self.last_payload = None
        self.preview_image = None
        self.camera_tab = ttk.Frame(self.tabs)
        self.tabs.add(self.camera_tab, text="Camera & micro")
        self.device_button = ttk.Button(
            self.camera_tab, text="Chọn camera & micro…", command=self.choose_devices
        )
        self.device_button.pack(anchor="w", padx=10, pady=4)
        self.device_summary = tk.StringVar(
            value="Chưa chọn thiết bị. Chỉ mở camera/micro khi bấm Thu hình & tiếng."
        )
        ttk.Label(self.camera_tab, textvariable=self.device_summary, wraplength=700).pack(
            anchor="w", padx=10
        )
        self.canvas = tk.Canvas(self.camera_tab, height=160, bg="#0F172A", highlightthickness=0)
        self.canvas.pack(fill="both", expand=True, padx=10, pady=4)
        self.lipsync_tab = ttk.Frame(self.tabs)
        self.tabs.add(self.lipsync_tab, text="Khớp môi")
        self.lipsync_text = tk.Text(
            self.lipsync_tab,
            height=9,
            wrap="word",
            font=("Segoe UI", 12),
            bg="white",
            fg="#0F172A",
            relief="flat",
            padx=14,
            pady=12,
        )
        scroll = ttk.Scrollbar(self.lipsync_tab, orient="vertical", command=self.lipsync_text.yview)
        scroll.pack(side="right", fill="y")
        self.lipsync_text.configure(yscrollcommand=scroll.set)
        self.lipsync_text.pack(side="left", fill="both", expand=True)
        self._lipsync_result("Chưa có kết quả. Cần cùng một lượt thu camera và micro.")
        self.tabs.select(self.camera_tab)
        self.header_label.configure(text="Thử hình & tiếng")
        self.subtitle_label.configure(
            text="Nội bộ · Qwen3-ASR · CTC · SyncNet"
            + (" · NES2Net" if nes2net_python else "")
            + " · xử lý trên máy"
        )
        self.record_button.configure(text="1. Thu hình & tiếng")
        self.footer_note.configure(
            text="Tối đa 20 giây · Hình/tiếng chỉ trong RAM, không ghi media.\nĐộ lệch/cosine chỉ tham khảo; chưa kết luận giọng thật hoặc giả."
        )
        self.status_text.set("CAMERA & MICRO ĐANG TẮT · Chọn thiết bị rồi bấm Thu hình & tiếng")
        root.title("VeriClue · Khớp môi (A/V)" + (" · xem thử" if preview else ""))
        root.geometry("900x750")
        self.device_button.configure(state="disabled" if preview else "normal")

    def choose_devices(self):
        if self.preview or self.trial.active:
            return
        import tkinter as tk
        from tkinter import ttk

        if self.device_dialog is not None and self.device_dialog.winfo_exists():
            self.device_dialog.lift()
            return
        self.device_epoch += 1
        epoch = self.device_epoch
        dialog = self.device_dialog = tk.Toplevel(self.root)
        dialog.title("Chọn nguồn hình và tiếng")
        dialog.geometry("620x250")
        dialog.transient(self.root)
        dialog.grab_set()
        body = ttk.Frame(dialog, padding=16)
        body.pack(fill="both", expand=True)
        self.video_choice, self.audio_choice = tk.StringVar(), tk.StringVar()
        ttk.Label(body, text="Camera").pack(anchor="w")
        self.video_combo = ttk.Combobox(body, textvariable=self.video_choice, state="readonly")
        self.video_combo.pack(fill="x", pady=(0, 8))
        ttk.Label(body, text="Microphone").pack(anchor="w")
        self.audio_combo = ttk.Combobox(body, textvariable=self.audio_choice, state="readonly")
        self.audio_combo.pack(fill="x", pady=(0, 8))
        self.device_status = tk.StringVar(value="Đang liệt kê thiết bị · Chưa thu hình hoặc tiếng")
        ttk.Label(body, textvariable=self.device_status, wraplength=580).pack(anchor="w")
        self.apply_device_button = ttk.Button(
            body, text="Dùng hai thiết bị này", state="disabled", command=self.apply_devices
        )
        self.apply_device_button.pack(anchor="e", pady=8)

        def enumerate_devices():
            try:
                value = list_devices(self.binary)
            except Exception:
                value = None
            self.device_results.put((epoch, value))

        threading.Thread(target=enumerate_devices, daemon=False).start()

    def apply_devices(self):
        self.video_device, self.audio_device = self.video_choice.get(), self.audio_choice.get()
        self.device_summary.set(f"{self.video_device} · {self.audio_device}")
        self.device_dialog.destroy()
        self.device_dialog = None

    def clear_preview(self):
        self.canvas.delete("all")
        self.preview_image = None
        if self.recorder is not None:
            with suppress(queue.Empty):
                while True:
                    self.recorder.preview.get_nowait()

    def start(self):
        if self.preview or self.trial.active:
            return
        if not self.video_device or not self.audio_device:
            self.choose_devices()
            return
        self.clear_preview()
        self.recorder.video, self.recorder.audio = self.video_device, self.audio_device
        self._lipsync_result("Chưa có kết quả khớp môi cho lượt này.")
        self.last_payload = None
        super().start()
        self.tabs.select(self.camera_tab)
        self.status_text.set("Đang mở camera và micro… Chờ ĐANG THU rồi đọc câu.")

    def cancel(self):
        super().cancel()
        if hasattr(self, "canvas"):
            self.clear_preview()
            self._lipsync_result("Lượt đã hủy; bỏ kết quả khớp môi.")

    def finish(self):
        super().finish()
        if self.phase == "stopping":
            self.status_text.set("Đang tắt camera và micro, chuyển sang kiểm câu…")

    def new_prompt(self):
        if self.trial.active or self.preview:
            return
        super().new_prompt()
        self.clear_preview()
        self._lipsync_result("Chưa có kết quả khớp môi cho câu mới.")

    def _lipsync_result(self, text):
        self.lipsync_text.configure(state="normal")
        self.lipsync_text.delete("1.0", "end")
        self.lipsync_text.insert("1.0", text)
        self.lipsync_text.configure(state="disabled")

    def render_lipsync(self):
        payload = self.payload.get("lipsync")
        if not payload:
            self._lipsync_result("Chưa có kết quả khớp môi cho lượt này.")
            return
        result = payload["result"]
        values = {e["name"]: e["value"] for e in result.get("evidence", [])}
        if "av_offset_ms" not in values:
            text = "CHƯA ĐO ĐƯỢC KHỚP MÔI · cần đủ đoạn nói và một khuôn mặt rõ"
        else:
            text = (
                "KẾT QUẢ THAM KHẢO · CHƯA KẾT LUẬN THẬT / GIẢ"
                f"\nĐộ lệch hình–tiếng: {values['av_offset_ms']:.0f} ms (dương: tiếng trễ)"
                f"\nCosine tại mốc gốc: {values['sync_confidence']:.4f}"
                f"\nCosine tốt nhất trong khoảng dò: {values['best_offset_confidence']:.4f}"
                "\nCosine không phải xác suất. Dò trong khoảng ±600 ms."
                "\nĐộ trễ phần cứng/driver chưa được kiểm chứng; không tự coi lệch là giả mạo."
            )
        self._lipsync_result(
            text + f"\nTrạng thái: {result['status']} / {result.get('gate', 'unclear')}"
            f"\nMã lý do: {result.get('error_code') or 'không'}"
            f"\nThời gian SyncNet/CTC: {result['latency_ms'] / 1000:.2f} giây"
        )

    def tick(self):
        if self.closed:
            return
        super().tick()
        if not hasattr(self, "recorder"):
            return
        self.device_button.configure(
            state="disabled" if self.preview or self.trial.active else "normal"
        )
        while not self.device_results.empty():
            epoch, value = self.device_results.get_nowait()
            if (
                epoch != self.device_epoch
                or self.device_dialog is None
                or not self.device_dialog.winfo_exists()
            ):
                continue
            if value is None:
                self.device_status.set(
                    "Chưa tìm được camera/micro. Kiểm tra FFmpeg, quyền thiết bị rồi mở lại hộp chọn."
                )
            else:
                self.video_combo.configure(values=value["video"])
                self.audio_combo.configure(values=value["audio"])
                self.video_choice.set(value["video"][0])
                self.audio_choice.set(value["audio"][0])
                self.device_status.set(
                    "Thiết bị chưa thu · Chọn nguồn rồi bấm Dùng hai thiết bị này"
                )
                self.apply_device_button.configure(state="normal")
        image = None
        if self.recorder is not None:
            with suppress(queue.Empty):
                image = self.recorder.preview.get_nowait()
        if image is not None:
            from PIL import Image, ImageTk

            if self.phase in {"recording", "opening", "stopping"}:
                picture = Image.fromarray(image[:, :, ::-1])
                picture.thumbnail(
                    (max(1, self.canvas.winfo_width()), max(1, self.canvas.winfo_height()))
                )
                self.preview_image = ImageTk.PhotoImage(picture)
                self.canvas.delete("all")
                self.canvas.create_image(
                    self.canvas.winfo_width() // 2,
                    self.canvas.winfo_height() // 2,
                    image=self.preview_image,
                )
        if self.payload is not None and self.payload is not self.last_payload:
            self.last_payload = self.payload
            self.render_lipsync()
            if self.tabs.select() == str(self.camera_tab):
                self.tabs.select(self.lipsync_tab)
        text = self.status_text.get()
        if text.startswith("MICRO"):
            self.status_text.set(text.replace("MICRO", "CAMERA & MICRO", 1))

    def close(self):
        self.clear_preview()
        if self.device_dialog is not None and self.device_dialog.winfo_exists():
            self.device_dialog.destroy()
        super().close()


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--models-dir", type=Path, required=True)
    parser.add_argument("--lipsync-models-dir", type=Path)
    parser.add_argument("--ffmpeg", type=Path)
    parser.add_argument("--nes2net-python", type=Path)
    parser.add_argument("--worker-timeout", type=float, default=180)
    parser.add_argument("--video-device", default="")
    parser.add_argument("--audio-device", default="")
    parser.add_argument("--ui-preview", action="store_true")
    parser.add_argument("--list-devices", action="store_true")
    args = parser.parse_args(argv)
    if args.list_devices:
        print(json.dumps(list_devices(ffmpeg_path(args.ffmpeg)), ensure_ascii=False))
        return 0
    import tkinter as tk

    root = tk.Tk()
    AVLab(
        root,
        models_dir=args.models_dir,
        lipsync_models_dir=args.lipsync_models_dir or args.models_dir,
        ffmpeg=args.ffmpeg,
        nes2net_python=args.nes2net_python,
        worker_timeout=args.worker_timeout,
        video_device=args.video_device,
        audio_device=args.audio_device,
        preview=args.ui_preview,
    )
    root.mainloop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
