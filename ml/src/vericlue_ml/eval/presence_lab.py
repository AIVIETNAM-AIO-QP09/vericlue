"""One-click color → eyes → head trial; developer lab only, no API/authentication."""

from __future__ import annotations

import argparse
import queue
import threading
from pathlib import Path
from time import perf_counter
from typing import Any

from vericlue_ml.eval.presence_trial import PresenceTrial
from vericlue_ml.eval.webcam_lab import WebcamLab


def wipe_frames(frames: dict) -> None:
    """Release pixel buffers owned by a completed or discarded local job."""
    for frame in frames.values():
        frame.fill(0)
    frames.clear()


class PresenceLab(WebcamLab):
    """Reuse the camera/model pipeline with an isolated, cancellable combined trial."""

    def __init__(
        self, root: Any, *, models_dir: Path, camera: int = 0, preview: bool = False
    ) -> None:
        self.presence_trial = None
        self.presence_busy = False
        self.presence_events = queue.SimpleQueue()
        self.presence_seen = None
        super().__init__(root, models_dir=models_dir, camera=camera, preview=preview)
        import tkinter as tk
        from tkinter import ttk

        root.title("VeriClue · Thử mặt liên tục" + (" · xem thử" if preview else ""))
        self.preview_size = (280, 160)
        self.video.configure(height=6)
        self.result_text.pack_forget()
        result_frame = ttk.Frame(self.result_text.master)
        result_frame.pack(fill="both", expand=True)
        scroll = ttk.Scrollbar(result_frame, orient="vertical", command=self.result_text.yview)
        scroll.pack(side="right", fill="y")
        self.result_text.configure(height=4, yscrollcommand=scroll.set)
        self.result_text.pack(in_=result_frame, side="left", fill="both", expand=True)
        self.result_text.lift()
        self.trial_button.pack_forget()
        self.color_button.pack_forget()
        controls = self.trial_button.master
        self.presence_button = ttk.Button(
            controls,
            text="Thử mặt · ánh sáng → mắt → quay đầu",
            command=self.start_presence_trial,
            state="disabled",
        )
        self.presence_button.pack(side="left")
        self.single_button = ttk.Menubutton(controls, text="Thử riêng", state="disabled")
        menu = tk.Menu(self.single_button, tearoff=False)
        menu.add_command(label="Mắt + quay đầu · 18 giây", command=self.start_trial)
        menu.add_command(label="Ánh sáng · 6–8 giây", command=self.start_color_trial)
        self.single_button.configure(menu=menu)
        self.single_button.pack(side="left", padx=(8, 0))
        self.render_results()

    @property
    def presence_active(self) -> bool:
        return self.presence_trial is not None or self.presence_busy

    def start_presence_trial(self) -> None:
        current = self.current()
        if (
            self.preview
            or self.closed
            or current is None
            or self.presence_active
            or self.trial is not None
            or self.color_trial is not None
            or self.color_busy
        ):
            return
        if self.busy:
            self.auto_ai = False
            self.ai_button.configure(text="3. Bật AI liên tục")
            self.status.set("Đang chấm ảnh. Chờ xong rồi bắt đầu lượt thử mặt.")
            return
        if current[3].face_count != 1:
            self.status.set("Cần đúng một khuôn mặt trong khung trước khi bắt đầu.")
            return
        try:
            trial = PresenceTrial.create(perf_counter())
        except Exception:
            self.status.set("Không đọc được cấu hình màu hợp lệ; chưa bắt đầu lượt thử.")
            return
        self.auto_ai = False
        self.generation += 1
        self.presence_trial = trial
        self.presence_seen = None
        self.results, self.motion, self.score_source = {}, {}, {}
        self.motion_plan = None
        self.clear_color_result()
        self.color_collect.set()
        self.root.resizable(False, False)
        self.ai_button.configure(text="3. Bật AI liên tục")
        self.update_presence_controls()
        self.status.set("Bước 1/3 · Giữ đầu yên và nhìn camera. Esc để dừng.")
        self.render_results()

    def update_presence_controls(self) -> None:
        ready = self.current() is not None and not self.preview and not self.closed
        idle = (
            ready
            and not self.presence_active
            and self.trial is None
            and self.color_trial is None
            and not self.color_busy
        )
        for button in (self.presence_button, self.single_button):
            button.configure(state="normal" if idle else "disabled")
        if self.presence_active:
            for button in (self.ref_button, self.ai_button, self.trial_button, self.color_button):
                button.configure(state="disabled")

    def cancel_presence_trial(self, reason: str) -> None:
        if not self.presence_active:
            return
        self.generation += 1
        trial, self.presence_trial = self.presence_trial, None
        if trial is not None:
            trial.wipe()
        self.color_collect.clear()
        self.results, self.motion, self.score_source = {}, {}, {}
        self.motion_plan = None
        self.clear_color_result()
        self.restore_color_controls()
        self.update_presence_controls()
        self.render_results()
        self.status.set(reason)

    def finish_presence_trial(self) -> None:
        trial, self.presence_trial = self.presence_trial, None
        if trial is None:
            return
        self.color_collect.clear()
        self.target.configure(bg="#111827")
        self.presence_busy = True
        self.update_presence_controls()
        self.status.set("Đã thu xong 3 bước · Đang đối chiếu số đo…")
        threading.Thread(
            target=self.score_presence, args=(self.generation, trial), daemon=True
        ).start()

    def score_presence(self, token: int, trial: PresenceTrial) -> None:
        frames = {}
        try:
            report, frames = trial.evaluate()
        except Exception:
            report = None
            wipe_frames(frames)
        finally:
            trial.wipe()
        if self.closed or token != self.generation:
            wipe_frames(frames)
            report = None
        self.presence_events.put((token, report, frames))

    def receive_presence_result(self, token: int, report: dict | None, frames: dict) -> None:
        self.presence_busy = False
        if self.closed or token != self.generation:
            wipe_frames(frames)
            if not self.closed:
                self.restore_color_controls()
                self.update_presence_controls()
            return
        self.restore_color_controls()
        self.update_presence_controls()
        if report is None:
            wipe_frames(frames)
            self.status.set("Chưa đối chiếu được lượt thử; kiểm tra runtime và thử lại.")
            return
        self.motion, self.motion_plan = report["motion"], report["motion_plan"]
        self.color_result, self.color_plan = report["color"], report["color_plan"]
        self.render_results()
        self.status.set("Đã xong 3 phần đo riêng · Chưa có kết luận xác minh.")
        if frames and self.reference is not None:
            self.submit(frames)
        else:
            wipe_frames(frames)
            if self.reference is None:
                self.status.set("Đã đo 3 phần; chưa so mặt vì chưa chụp tham chiếu.")
            else:
                self.status.set("Đã đo 3 phần; chưa chấm ảnh vì chưa đủ chuyển động/ba góc hợp lệ.")

    def tick(self) -> None:
        if self.closed:
            return
        super().tick()
        while not self.presence_events.empty():
            self.receive_presence_result(*self.presence_events.get_nowait())
        self.update_presence_controls()
        trial = self.presence_trial
        if trial is None:
            if self.trial is None and self.color_trial is None:
                self.target.delete("all")
                self.target.create_text(
                    self.target.winfo_width() / 2,
                    70,
                    text=(
                        "Đã thu xong 3 bước\nĐang đối chiếu số đo…"
                        if self.presence_busy
                        else "Bật camera → Thử mặt liên tục\nChụp tham chiếu nếu muốn thử so mặt."
                    ),
                    fill="#F8FAFC",
                    font=("Segoe UI", 15),
                    width=max(120, self.target.winfo_width() - 50),
                    justify="center",
                )
            return
        current = self.current()
        if current is not None and current[1] != self.presence_seen:
            self.presence_seen = current[1]
            trial.add(current[1], current[2], current[3], current[4])
        elapsed = (perf_counter() - trial.started) * 1000
        if elapsed >= trial.duration_ms + 200:
            self.finish_presence_trial()
            return
        step, text, dot, rgb = trial.cue(elapsed)
        if step > 1:
            self.color_collect.clear()
        background = "#{:02x}{:02x}{:02x}".format(*rgb) if rgb else "#111827"
        foreground = "#0F172A" if rgb else "#F8FAFC"
        self.target.configure(bg=background)
        if rgb is not None:
            trial.color.record_draw((perf_counter() - trial.started) * 1000, rgb)
        self.target.delete("all")
        width, height = self.target.winfo_width(), self.target.winfo_height()
        remaining = max(0, (trial.duration_ms - elapsed) / 1000)
        self.target.create_text(
            width / 2,
            45,
            text=f"Bước {step}/3 · {text}\n{remaining:.1f} giây còn lại · Esc để dừng",
            fill=foreground,
            font=("Segoe UI", 15),
            width=max(120, width - 50),
            justify="center",
        )
        if dot:
            x, y = dot[0] * width, 100 + dot[1] * max(30, height - 140)
            self.target.create_oval(
                x - 11, y - 11, x + 11, y + 11, fill="#22D3EE", outline="white", width=2
            )
        self.status.set(f"Bước {step}/3 · Ánh sáng → Mắt → Quay đầu · {remaining:.1f} giây còn lại")

    def capture_reference(self) -> None:
        if not self.presence_active:
            super().capture_reference()

    def toggle_ai(self) -> None:
        if not self.presence_active:
            super().toggle_ai()

    def start_trial(self) -> None:
        if not self.presence_active:
            super().start_trial()

    def start_color_trial(self) -> None:
        if not self.presence_active:
            super().start_color_trial()

    def submit_snapshot(self) -> None:
        if not self.presence_active:
            super().submit_snapshot()

    def check_color_visibility(self) -> None:
        if self.presence_active and not self.closed and self.root.focus_displayof() is None:
            self.cancel_presence_trial("Đã hủy lượt thử mặt vì cửa sổ mất tiêu điểm.")
        super().check_color_visibility()

    def cancel_color_trial(self, reason: str) -> None:
        # Base Unmap handler delegates here, including while only combined mode is active.
        if self.presence_active:
            self.cancel_presence_trial(reason)
        super().cancel_color_trial(reason)

    def score(self, token: int, reference: Any, frames: dict) -> None:
        try:
            super().score(token, reference, frames)
        finally:
            reference.fill(0)
            wipe_frames(frames)

    def stop_camera(self) -> None:
        self.cancel_presence_trial("Đã hủy lượt thử mặt.")
        super().stop_camera()
        self.video.configure(height=6)
        self.update_presence_controls()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--models-dir", type=Path, required=True)
    parser.add_argument("--camera", type=int, default=0)
    parser.add_argument("--ui-preview", action="store_true")
    args = parser.parse_args(argv)
    import tkinter as tk

    root = tk.Tk()
    PresenceLab(root, models_dir=args.models_dir, camera=args.camera, preview=args.ui_preview)
    root.mainloop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
