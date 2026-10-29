"""Interactive local developer webcam lab; camera opens only on an explicit button click.

Preview/eye/pose measurements run live. Heavy classifiers run on one latest
snapshot at a time in a separate worker, never on the GUI thread. All face pixels
stay in RAM. No API, authentication decision, microphone or video recording.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import queue
import threading
from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path
from time import perf_counter
from typing import Any

import numpy as np

from vericlue_ml.common.detector import DetectorInput
from vericlue_ml.common.result import ErrorCode, Gate, Module, ModuleResult, Status
from vericlue_ml.eval.face_runtime import runtime_versions
from vericlue_ml.eval.report import git_revision
from vericlue_ml.eval.webcam_color import WebcamColorTrial, local_color_plan, observe_live
from vericlue_ml.eval.webcam_trial import WebcamTrial
from vericlue_ml.face.fsvfm import FsvfmPadDetector
from vericlue_ml.face.gend import FaceDeepfakeDetector
from vericlue_ml.face.match import FaceMatchDetector
from vericlue_ml.face.pad import PadError
from vericlue_ml.presence.color_regions import ColorObservation
from vericlue_ml.presence.landmarks import FaceObservation, FaceObservationReader

ROOT = Path(__file__).resolve().parents[4]


class WebcamLab:
    """A desktop-only diagnostic, independent of the product UI and HTTP router."""

    def __init__(
        self, root: Any, *, models_dir: Path, camera: int = 0, preview: bool = False
    ) -> None:
        import tkinter as tk
        from tkinter import ttk

        self.root, self.tk = root, tk
        self.models_dir, self.camera, self.preview = models_dir, camera, preview
        self.preview_size = (320, 210)
        self.events = queue.SimpleQueue()
        self.lock = threading.Lock()
        self.latest = None
        self.stop_event = threading.Event()
        self.camera_thread = None
        self.closed = False
        self.busy = False
        self.auto_ai = False
        self.generation = 0
        self.epoch = 0
        self.last_seen = None
        self.reference = None
        self.trial = None
        self.color_trial = None
        self.color_busy = False
        self.color_collect = threading.Event()
        self.color_result = None
        self.color_plan = None
        self.results = {}
        self.motion = {}
        self.motion_plan = None
        self.score_source = {}
        self.landmarker_sha = None
        self.models = (FaceMatchDetector(), FaceDeepfakeDetector(), FsvfmPadDetector())
        root.title("VeriClue · Webcam Lab nội bộ" + (" · xem thử" if preview else ""))
        root.geometry(
            f"{min(1120, root.winfo_screenwidth() - 80)}x{min(740, root.winfo_screenheight() - 100)}"
        )
        root.minsize(900, 620)
        root.configure(bg="#F8FAFC")
        style = ttk.Style(root)
        style.theme_use("clam")
        style.configure("TButton", font=("Segoe UI", 11), padding=(12, 10))
        style.configure("Stop.TButton", background="#B91C1C", foreground="white")
        style.map("Stop.TButton", background=[("active", "#991B1B")])
        style.configure("TFrame", background="#F8FAFC")
        style.configure("TLabel", background="#F8FAFC", foreground="#0F172A", font=("Segoe UI", 11))
        header = ttk.Frame(root, padding=(22, 14))
        header.pack(fill="x")
        ttk.Label(header, text="Webcam Lab", font=("Segoe UI", 22, "bold")).pack(anchor="w")
        ttk.Label(
            header, text="Nội bộ phát triển · Số đo thử nghiệm, chưa phải kết quả xác minh"
        ).pack(anchor="w")
        toolbar = ttk.Frame(root, padding=(22, 0, 22, 10))
        toolbar.pack(fill="x")
        self.open_button = ttk.Button(toolbar, text="1. Bật camera", command=self.start_camera)
        self.open_button.pack(side="left", padx=(0, 8))
        self.ref_button = ttk.Button(
            toolbar, text="2. Chụp tham chiếu", command=self.capture_reference, state="disabled"
        )
        self.ref_button.pack(side="left", padx=(0, 8))
        self.ai_button = ttk.Button(
            toolbar, text="3. Bật AI liên tục", command=self.toggle_ai, state="disabled"
        )
        self.ai_button.pack(side="left", padx=(0, 8))
        ttk.Button(toolbar, text="Dừng (Esc)", style="Stop.TButton", command=self.stop_camera).pack(
            side="right"
        )
        body = ttk.Frame(root, padding=(22, 0))
        body.pack(fill="both", expand=True)
        self.target = tk.Canvas(body, bg="#111827", highlightthickness=0, takefocus=True)
        self.target.pack(side="left", fill="both", expand=True, padx=(0, 18))
        side = ttk.Frame(body, width=330)
        side.pack(side="right", fill="y")
        self.video = tk.Label(
            side,
            text="Camera đang tắt",
            bg="#E2E8F0",
            fg="#334155",
            font=("Segoe UI", 13),
            width=35,
            height=10,
        )
        self.video.pack(fill="x")
        self.measure = ttk.Label(
            side, text="Chưa có số đo mắt / góc đầu", justify="left", wraplength=320
        )
        self.measure.pack(fill="x", pady=10)
        self.result_text = tk.Text(
            side,
            width=39,
            height=9,
            font=("Consolas", 10),
            bg="white",
            fg="#0F172A",
            wrap="word",
            relief="solid",
            bd=1,
        )
        self.result_text.pack(fill="both", expand=True)
        self.result_text.configure(state="disabled")
        controls = ttk.Frame(root, padding=(22, 12))
        controls.pack(fill="x")
        self.trial_button = ttk.Button(
            controls,
            text="Thử mắt + quay đầu · 18 giây",
            command=self.start_trial,
            state="disabled",
        )
        self.trial_button.pack(side="left")
        self.color_button = ttk.Button(
            controls,
            text="Thử ánh sáng · 6–8 giây",
            command=self.start_color_trial,
            state="disabled",
        )
        self.color_button.pack(side="left", padx=(8, 0))
        ttk.Button(controls, text="Lưu báo cáo JSON", command=self.save_report).pack(side="right")
        self.status = tk.StringVar(value="Bấm Bật camera để bắt đầu. Không lưu ảnh hoặc video.")
        ttk.Label(root, textvariable=self.status, wraplength=1000, padding=(22, 0, 22, 8)).pack(
            fill="x"
        )
        ttk.Label(
            root,
            text="AI cập nhật khi chấm xong; CPU không chấm mọi khung hình. Ảnh chỉ giữ trong RAM.",
            padding=(22, 0, 22, 12),
        ).pack(fill="x")
        root.bind("<Escape>", lambda event: self.stop_camera())
        root.bind("<FocusOut>", lambda event: root.after_idle(self.check_color_visibility))
        root.bind(
            "<Unmap>",
            lambda event: (
                self.cancel_color_trial("Đã hủy lượt ánh sáng.") if event.widget is root else None
            ),
        )
        root.protocol("WM_DELETE_WINDOW", self.close)
        if preview:
            self.open_button.configure(state="disabled")
            self.status.set("Xem giao diện tổng hợp · không mở webcam, không chạy mô hình.")
        root.after(30, self.tick)

    def start_camera(self) -> None:
        if self.preview or (self.camera_thread is not None and self.camera_thread.is_alive()):
            return
        self.stop_event = threading.Event()
        self.epoch += 1
        self.open_button.configure(state="disabled")
        self.status.set("Đang nạp MediaPipe và mở camera…")
        self.camera_thread = threading.Thread(
            target=self.camera_loop, args=(self.epoch, self.stop_event), daemon=True
        )
        self.camera_thread.start()

    def camera_loop(self, epoch: int, stop: threading.Event) -> None:
        import cv2

        reader = FaceObservationReader()
        capture = None
        try:
            reader.preload(models_dir=self.models_dir)
            if stop.is_set():
                return
            capture = cv2.VideoCapture(self.camera)
            capture.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
            capture.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
            capture.set(cv2.CAP_PROP_BUFFERSIZE, 1)
            if not capture.isOpened():
                raise RuntimeError("camera_unavailable")
            self.events.put(("camera_ready", epoch, reader.expected_sha256))
            measured = 0.0
            while not stop.is_set():
                ok, frame = capture.read()
                acquired = perf_counter()
                if not ok:
                    raise RuntimeError("camera_read_failed")
                if acquired - measured < 0.1:
                    continue
                measured = acquired
                row, color = observe_live(reader, frame, with_color=self.color_collect.is_set())
                with self.lock:
                    self.latest = (epoch, acquired, frame, row, color)
        except Exception as exc:
            self.events.put(("camera_error", epoch, type(exc).__name__))
        finally:
            if capture is not None:
                capture.release()
            reader.close()
            with self.lock:
                if self.latest is not None and self.latest[0] == epoch:
                    self.latest = None
            self.events.put(("camera_stopped", epoch, None))

    def current(
        self,
    ) -> tuple[int, float, np.ndarray, FaceObservation, ColorObservation | None] | None:
        with self.lock:
            return self.latest if self.latest is not None and self.latest[0] == self.epoch else None

    def capture_reference(self) -> None:
        if self.trial is not None or self.color_trial is not None or self.color_busy:
            return
        current = self.current()
        if current is None or current[3].face_count != 1:
            self.status.set("Cần đúng một khuôn mặt, đủ sáng trước camera.")
            return
        self.reference = current[2].copy()
        self.generation += 1
        self.results = {}
        self.motion = {}
        self.motion_plan = None
        self.score_source = {}
        self.clear_color_result()
        self.render_results()
        self.ai_button.configure(state="normal")
        self.status.set("Đã chụp tham chiếu trong RAM. Nhìn thẳng rồi bấm Bật AI liên tục.")

    def toggle_ai(self) -> None:
        if (
            self.reference is None
            or self.trial is not None
            or self.color_trial is not None
            or self.color_busy
        ):
            return
        self.auto_ai = not self.auto_ai
        self.ai_button.configure(text="Tạm dừng AI" if self.auto_ai else "3. Bật AI liên tục")
        if self.auto_ai:
            self.motion = {}
            self.motion_plan = None
            self.clear_color_result()
            self.submit_snapshot()

    def submit_snapshot(self) -> None:
        current = self.current()
        if (
            self.closed
            or self.busy
            or not self.auto_ai
            or self.trial is not None
            or self.color_trial is not None
            or self.color_busy
            or self.reference is None
            or current is None
        ):
            return
        self.submit({"front": current[2].copy()})

    def submit(self, frames: dict[str, np.ndarray]) -> None:
        if self.busy or self.reference is None:
            return
        self.busy = True
        reference = self.reference.copy()
        token = self.generation
        threading.Thread(target=self.score, args=(token, reference, frames), daemon=True).start()

    def score(self, token: int, reference: np.ndarray, frames: dict[str, np.ndarray]) -> None:
        inp = DetectorInput()
        results = {}
        for detector in self.models:
            self.events.put(("scoring", token, detector.name))
            started = perf_counter()
            try:
                detector.preload(models_dir=self.models_dir, device="cpu")
                if detector.name == "face_match":
                    result = detector.predict_frames(inp, frames, reference_frame=reference)
                elif len(frames) == 1:
                    result = detector.predict_frame(inp, frames["front"])
                else:
                    result = detector.predict_frames(inp, frames)
                results[detector.name] = result.to_contract()
            except Exception as exc:
                results[detector.name] = ModuleResult(
                    module=Module(detector.name),
                    model_version=detector.version,
                    status=Status.ERROR,
                    error_code=exc.code if isinstance(exc, PadError) else ErrorCode.E_INTERNAL,
                    latency_ms=(perf_counter() - started) * 1000,
                ).to_contract()
        source = {
            "reference_sha256": hashlib.sha256(reference.tobytes()).hexdigest(),
            "frame_sha256": {
                role: hashlib.sha256(frame.tobytes()).hexdigest() for role, frame in frames.items()
            },
            "mode": "single_frame" if len(frames) == 1 else "three_views",
        }
        self.events.put(("scores", token, (results, source)))

    def start_trial(self) -> None:
        if (
            self.current() is None
            or self.trial is not None
            or self.color_trial is not None
            or self.color_busy
        ):
            return
        if self.busy:
            self.auto_ai = False
            self.ai_button.configure(text="3. Bật AI liên tục")
            self.status.set("Đang chấm ảnh. Chờ xong rồi bấm thử chuyển động.")
            return
        self.auto_ai = False
        self.ai_button.configure(text="3. Bật AI liên tục")
        self.trial = WebcamTrial(perf_counter())
        self.root.resizable(False, False)
        self.ai_button.configure(state="disabled")
        self.ref_button.configure(state="disabled")
        self.motion = {}
        self.motion_plan = None
        self.results = {}
        self.score_source = {}
        self.clear_color_result()
        self.render_results()
        self.trial_button.configure(state="disabled")
        self.color_button.configure(state="disabled")

    def finish_trial(self) -> None:
        trial = self.trial
        self.trial = None
        self.root.resizable(True, True)
        gaze, head = trial.evaluate()
        self.motion = {"gaze_tracking": asdict(gaze), "head_turn": asdict(head)}
        self.motion_plan = {
            "trial_id": trial.trial_id,
            "gaze_plan": asdict(trial.gaze_plan),
            "head_plan": asdict(trial.head_plan),
        }
        self.trial_button.configure(state="normal")
        self.color_button.configure(state="normal")
        self.ref_button.configure(state="normal")
        if self.reference is not None:
            self.ai_button.configure(state="normal")
        self.status.set(
            f"Mắt: {gaze.gate.value}; quay đầu: {head.gate.value}. Luật thử nghiệm, chưa xác minh danh tính."
        )
        if (
            gaze.status == head.status == Status.OK
            and gaze.gate == head.gate == Gate.PASS
            and self.reference is not None
        ):
            try:
                self.submit(trial.selected_frames(head.view_times_ms))
            except ValueError:
                self.status.set("Chưa lấy đủ ba khung đúng tư thế; hãy thử lại.")
        self.render_results()

    def clear_color_result(self) -> None:
        self.color_result = None
        self.color_plan = None

    def start_color_trial(self) -> None:
        if (
            self.preview
            or self.current() is None
            or self.trial is not None
            or self.color_trial is not None
            or self.color_busy
        ):
            return
        self.auto_ai = False
        self.ai_button.configure(text="3. Bật AI liên tục")
        if self.busy:
            self.status.set("Đang chấm ảnh. Chờ xong rồi bấm thử ánh sáng.")
            return
        try:
            plan, tail = local_color_plan()
        except Exception:
            self.status.set("Không đọc được cấu hình màu hợp lệ; chưa bắt đầu lượt thử.")
            return
        self.generation += 1
        self.results, self.motion, self.score_source = {}, {}, {}
        self.motion_plan = None
        self.clear_color_result()
        self.color_trial = WebcamColorTrial(perf_counter(), plan, tail)
        self.color_collect.set()
        self.root.resizable(False, False)
        for button in (self.ref_button, self.ai_button, self.trial_button, self.color_button):
            button.configure(state="disabled")
        self.status.set("Giữ đầu yên. Màn hình đổi màu nhẹ trong 6–8 giây; Esc để dừng.")
        self.render_results()

    def check_color_visibility(self) -> None:
        if not self.closed and self.color_trial is not None and self.root.focus_displayof() is None:
            self.cancel_color_trial("Đã hủy lượt ánh sáng vì cửa sổ mất tiêu điểm.")

    def restore_color_controls(self) -> None:
        self.target.configure(bg="#111827")
        self.root.resizable(True, True)
        ready = self.current() is not None and not self.preview
        self.ref_button.configure(state="normal" if ready else "disabled")
        self.ai_button.configure(
            state="normal" if ready and self.reference is not None else "disabled"
        )
        for button in (self.trial_button, self.color_button):
            button.configure(state="normal" if ready else "disabled")

    def cancel_color_trial(self, reason: str) -> None:
        if self.color_trial is None:
            return
        self.color_collect.clear()
        self.color_trial = None
        self.restore_color_controls()
        self.status.set(reason)

    def finish_color_trial(self) -> None:
        trial = self.color_trial
        self.color_trial = None
        self.color_collect.clear()
        self.target.configure(bg="#111827")
        self.color_busy = True
        self.status.set("Đang đối chiếu số đo ánh sáng…")
        token = self.generation
        threading.Thread(target=self.score_color, args=(token, trial), daemon=True).start()

    def score_color(self, token: int, trial: WebcamColorTrial) -> None:
        try:
            result = trial.evaluate().to_contract()
            plan = {
                "trial_id": trial.trial_id,
                "color_plan": asdict(trial.plan),
                "tail_ms": trial.tail_ms,
                "draw_requests": trial.draws,
                "timestamp_source": "host_acquisition_and_tk_draw_request_not_attested",
            }
            self.events.put(("color_result", token, (result, plan)))
        except Exception:
            self.events.put(("color_result", token, (None, None)))

    def receive_color_result(self, token: int, value: tuple) -> None:
        self.color_busy = False
        if token != self.generation:
            return
        self.color_result, self.color_plan = value
        self.restore_color_controls()
        self.render_results()
        self.status.set(
            "Đã đo ánh sáng. R² và độ trễ chỉ là số đo thử nghiệm, chưa xác minh."
            if self.color_result is not None
            else "Chưa đối chiếu được số đo ánh sáng; hãy thử lại."
        )

    def tick(self) -> None:
        if self.closed:
            return
        from PIL import Image, ImageTk

        while not self.events.empty():
            kind, token, value = self.events.get()
            if kind == "color_result":
                self.receive_color_result(token, value)
            elif kind == "scores":
                self.busy = False
                if token == self.generation:
                    self.results, self.score_source = value
                    self.render_results()
                    self.status.set(
                        "Đã cập nhật điểm AI thô. Không có kết luận xác minh từ các điểm này."
                    )
                if self.auto_ai and self.trial is None:
                    self.root.after(500, self.submit_snapshot)
            elif kind == "scoring" and token == self.generation:
                self.status.set(f"Đang nạp/chấm {value} trên CPU… bạn vẫn có thể dừng camera.")
            elif token == self.epoch:
                if kind == "camera_ready":
                    self.landmarker_sha = value
                    self.ref_button.configure(state="normal")
                    self.trial_button.configure(state="normal")
                    self.color_button.configure(state="normal")
                    self.status.set(
                        "Camera đã mở. Chụp tham chiếu để so mặt, hoặc chọn lượt thử bên dưới."
                    )
                elif kind == "camera_error":
                    self.stop_camera()
                    self.status.set(
                        f"Không đọc được camera ({value}). Đóng Camera/Teams nếu đang sử dụng webcam."
                    )
                elif kind == "camera_stopped":
                    self.open_button.configure(state="normal" if not self.preview else "disabled")
                    self.ref_button.configure(state="disabled")
                    self.trial_button.configure(state="disabled")
                    self.color_button.configure(state="disabled")
        current = self.current()
        if (
            self.stop_event.is_set()
            and self.camera_thread is not None
            and not self.camera_thread.is_alive()
            and not self.preview
        ):
            self.open_button.configure(state="normal")
        if current is not None and current[1] != self.last_seen:
            _, acquired, frame, row, color = current
            self.last_seen = acquired
            rgb = Image.fromarray(frame[:, :, ::-1])
            rgb.thumbnail(self.preview_size)
            self.photo = ImageTk.PhotoImage(rgb)
            self.video.configure(
                image=self.photo, text="", width=self.preview_size[0], height=self.preview_size[1]
            )

            def fmt(v):
                return "—" if v is None else f"{v:.2f}"

            self.measure.configure(
                text=f"Số mặt: {row.face_count} · đo tối đa 10 Hz\nYaw {fmt(row.yaw_deg)}° · pitch {fmt(row.pitch_deg)}°\nMắt x {fmt(row.gaze_x)} · y {fmt(row.gaze_y)}"
            )
            if self.trial is not None:
                self.trial.add(acquired, frame, row)
            if self.color_trial is not None:
                self.color_trial.add(acquired, color)
        self.target.delete("all")
        w, h = self.target.winfo_width(), self.target.winfo_height()
        text = "Bật camera → chụp tham chiếu → bật AI\nHoặc thử chuyển động / phản hồi ánh sáng."
        dot = None
        text_color = "#F8FAFC"
        if self.trial is not None:
            elapsed = (perf_counter() - self.trial.started) * 1000
            text, dot = self.trial.cue(elapsed)
            text += f"\n{max(0, 18 - elapsed / 1000):.1f} giây còn lại"
            if elapsed >= 18200:
                self.finish_trial()
        elif self.color_trial is not None:
            trial = self.color_trial
            elapsed = (perf_counter() - trial.started) * 1000
            if elapsed >= trial.duration_ms + 200:
                self.finish_color_trial()
                text = "Đang đối chiếu phản hồi màu…"
            else:
                rgb = trial.color_at(elapsed)
                self.target.configure(bg="#{:02x}{:02x}{:02x}".format(*rgb))
                trial.record_draw((perf_counter() - trial.started) * 1000, rgb)
                text_color = "#0F172A"
                text = f"Giữ đầu yên, nhìn camera\n{max(0, (trial.duration_ms - elapsed) / 1000):.1f} giây · Esc để dừng"
        self.target.create_text(
            w / 2,
            45,
            text=text,
            fill=text_color,
            font=("Segoe UI", 15),
            width=max(120, w - 50),
            justify="center",
        )
        if dot:
            x, y = dot[0] * w, 100 + dot[1] * max(30, h - 140)
            self.target.create_oval(
                x - 11, y - 11, x + 11, y + 11, fill="#22D3EE", outline="white", width=2
            )
        elif self.preview:
            self.target.create_oval(
                w * 0.6 - 11,
                h * 0.6 - 11,
                w * 0.6 + 11,
                h * 0.6 + 11,
                fill="#22D3EE",
                outline="white",
                width=2,
            )
        self.root.after(33, self.tick)

    def render_results(self) -> None:
        lines = []
        for name, value in self.results.items():
            score = value.get("score")
            lines.append(
                f"{name}: {value['status']}\n  Điểm thô: {'—' if score is None else f'{score:.4f}'}"
            )
        for name, value in self.motion.items():
            lines.append(f"{name}: {value['gate']}\n  {value['reason']}")
        if self.color_result is not None:
            quality = self.color_result["quality"]
            r2, lag = quality.get("fit_r2_in_sample"), quality.get("apparent_lag_ms")
            lines.append(
                "Ánh sáng: đo thử nghiệm / chưa rõ\n  "
                + (
                    f"R² fit: {r2:.3f} · lag biểu kiến: {lag:.0f} ms"
                    if r2 is not None and lag is not None
                    else "Chưa đủ số đo; giữ đầu yên và thử lại."
                )
            )
        self.result_text.configure(state="normal")
        self.result_text.delete("1.0", "end")
        self.result_text.insert(
            "end",
            "\n".join(lines)
            or "Chưa chấm AI.\nẢnh tham chiếu dùng để so cùng người.\nPAD / GenD chưa có ngưỡng hiệu chỉnh.",
        )
        self.result_text.configure(state="disabled")

    def save_report(self) -> None:
        if not self.results and not self.motion and self.color_result is None:
            self.status.set("Chưa có kết quả để lưu.")
            return
        folder = ROOT / "tmp" / "webcam-lab"
        folder.mkdir(parents=True, exist_ok=True)
        path = folder / f"report-{datetime.now(UTC).strftime('%Y%m%d-%H%M%S-%f')}.json"
        path.write_text(
            json.dumps(
                {
                    "commit": git_revision(),
                    "created_at": datetime.now(UTC).isoformat(),
                    "sample_count": 1,
                    "dataset": "local_webcam_developer_diagnostic_not_accuracy_evaluation",
                    "runtime": runtime_versions(),
                    "challenge_source": "local_lab_not_server_authenticated",
                    "timestamp_source": "host_acquisition_clock_not_sensor_attestation",
                    "landmarker_sha256": self.landmarker_sha,
                    "source": self.score_source,
                    "results": self.results,
                    "motion": self.motion,
                    "plan": self.motion_plan,
                    "color": self.color_result,
                    "color_plan": self.color_plan,
                },
                ensure_ascii=False,
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
        self.status.set(f"Đã lưu {path.relative_to(ROOT)}; không lưu ảnh/video.")

    def stop_camera(self) -> None:
        self.stop_event.set()
        self.epoch += 1
        self.auto_ai = False
        self.generation += 1
        self.reference = None
        self.trial = None
        self.color_collect.clear()
        self.color_trial = None
        self.clear_color_result()
        self.results = {}
        self.motion = {}
        self.score_source = {}
        self.motion_plan = None
        self.ai_button.configure(state="disabled", text="3. Bật AI liên tục")
        self.ref_button.configure(state="disabled")
        self.trial_button.configure(state="disabled")
        self.color_button.configure(state="disabled")
        self.target.configure(bg="#111827")
        self.video.configure(image="", text="Camera đang tắt", width=35, height=10)
        self.photo = None
        self.root.resizable(True, True)
        with self.lock:
            self.latest = None
        self.status.set(
            "Đã ngừng thu. Lượt chấm đang chạy sẽ kết thúc rồi bỏ khung; camera được giải phóng sau lượt đọc."
        )
        self.render_results()

    def close(self) -> None:
        self.stop_camera()
        self.closed = True
        self.root.destroy()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--models-dir", type=Path, required=True)
    parser.add_argument("--camera", type=int, default=0)
    parser.add_argument(
        "--ui-preview", action="store_true", help="Synthetic UI only; camera cannot open"
    )
    parser.add_argument("--close-after-ms", type=int, help="Only available with --ui-preview")
    args = parser.parse_args(argv)
    if args.close_after_ms is not None and (not args.ui_preview or args.close_after_ms < 100):
        parser.error("--close-after-ms requires --ui-preview and >=100")
    import tkinter as tk

    root = tk.Tk()
    lab = WebcamLab(root, models_dir=args.models_dir, camera=args.camera, preview=args.ui_preview)
    lab.render_results()
    if args.close_after_ms is not None:
        root.after(args.close_after_ms, lab.close)
    root.mainloop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
