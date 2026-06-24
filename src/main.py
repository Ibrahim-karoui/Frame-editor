import cv2
import tkinter as tk
from tkinter import filedialog, messagebox
from PIL import Image, ImageTk
import os
import subprocess
import threading
import sys

#───────── create exe file ─────────
base_path = getattr(sys, '_MEIPASS', os.path.dirname(os.path.abspath(__file__)))
FFMPEG = os.path.join(base_path, "assets", "ffmpeg.exe")
#───────────────────────────────────

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
RESULTS_DIR = os.path.join(BASE_DIR, "..", "results")

os.makedirs(RESULTS_DIR, exist_ok=True)

class VideoFrameEditor:
    def __init__(self, root):
        self.root = root
        self.root.title("Frame Editor")
        self.root.state("zoomed")

        self.video_path = None
        self.frames = []
        self.keep = []

        self.current = 0
        self.fps = 30
        self.speed_divisor = 1

        self.previewing = False
        self.preview_playing = False
        self.preview_frames_list = []
        self.preview_index = 0

        self.pending_step = None

        # ── Video area ───────────────────────────────────────────────────────────
        self.video_frame = tk.Frame(self.root, bg="black")
        self.video_frame.pack(fill="both", expand=True)

        self.image_label = tk.Label(self.video_frame, bg="black")
        self.image_label.pack(expand=True)

        # ── Controls ─────────────────────────────────────────────────────────────
        self.controls = tk.Frame(self.root, height=210, bg="#1e1e1e")
        self.controls.pack(fill="x", side="bottom")

        def mkbtn(parent, text, cmd, bg="#333"):
            return tk.Button(
                parent, text=text, command=cmd,
                padx=12, pady=6, bg=bg, fg="white",
                relief="flat", cursor="hand2",
            )

        def sep(parent):
            tk.Frame(parent, width=1, height=28, bg="#555").pack(side="left", padx=8)

        # ── Row 1 – fichier ──────────────────────────────────────────────────────
        row1 = tk.Frame(self.controls, bg="#1e1e1e")
        row1.pack(pady=(10, 2))

        mkbtn(row1, "📂 Load", self.load_video).pack(side="left", padx=4)
        mkbtn(row1, "💾 Save", self.save_video).pack(side="left", padx=4)
        mkbtn(row1, "↺ Discard & Restart", self.discard_and_restart, bg="#5a2020").pack(side="left", padx=4)

        # ── Row 2 – custom sampling ──────────────────────────────────────────────
        row2 = tk.Frame(self.controls, bg="#1e1e1e")
        row2.pack(pady=(2, 2))

        tk.Label(row2, text="Custom sampling:", fg="white", bg="#1e1e1e").pack(side="left")
        self.auto_entry = tk.Entry(row2, width=5)
        self.auto_entry.insert(0, "2")
        self.auto_entry.pack(side="left", padx=6)
        self.auto_entry.bind("<KeyRelease>", lambda e: self._update_sampling_label())

        self.preview_sampling_btn = mkbtn(row2, "👁 Preview Custom Sampling", self.preview_sampling)
        self.preview_sampling_btn.pack(side="left", padx=4)

        self.confirm_sampling_btn = mkbtn(row2, "✔ Confirm Sampling", self.confirm_sampling, bg="#1a5c1a")
        self.confirm_sampling_btn.pack(side="left", padx=4)
        self.confirm_sampling_btn.config(state="disabled")

        self.auto_info = tk.Label(row2, text="1/2", fg="#aaaaaa", bg="#1e1e1e", font=("Arial", 10))
        self.auto_info.pack(side="left", padx=10)

        self.speed_label = tk.Label(row2, text="Speed ×1", fg="#ffaa44", bg="#1e1e1e", font=("Arial", 10))
        self.speed_label.pack(side="left", padx=10)

        # ── Row 3 – navigation + édition ────────────────────────────────────────
        row3 = tk.Frame(self.controls, bg="#1e1e1e")
        row3.pack(pady=(2, 4))

        mkbtn(row3, "⬅ Prev", self.previous).pack(side="left", padx=4)
        mkbtn(row3, "⏹ Stop", self.stop_playback).pack(side="left", padx=4)
        mkbtn(row3, "Next ➡", self.next).pack(side="left", padx=4)

        sep(row3)

        mkbtn(row3, "🗑 Remove", self.remove_frame).pack(side="left", padx=4)

        sep(row3)

        tk.Label(row3, text="Go to frame:", fg="white", bg="#1e1e1e").pack(side="left", padx=(0, 4))
        self.goto_entry = tk.Entry(row3, width=6)
        self.goto_entry.pack(side="left", padx=(0, 4))
        self.goto_entry.bind("<Return>", lambda e: self.go_to_frame())
        mkbtn(row3, "Go", self.go_to_frame).pack(side="left", padx=(0, 4))

        sep(row3)

        self.preview_btn = mkbtn(row3, "▶ Preview Result", self.preview_result)
        self.preview_btn.pack(side="left", padx=4)
        mkbtn(row3, "◼ Stop Preview", self.stop_preview).pack(side="left", padx=4)

        # ── Status bar ───────────────────────────────────────────────────────────
        tk.Frame(self.controls, height=1, bg="#444").pack(fill="x", pady=(2, 0))
        self.status = tk.Label(self.controls, text="",
                               fg="white", bg="#1e1e1e", font=("Arial", 11))
        self.status.pack(pady=3)

        # Keyboard
        self.root.bind("<Left>",   lambda e: self.previous())
        self.root.bind("<Right>",  lambda e: self.next())
        self.root.bind("<space>",  lambda e: self.remove_frame())
        self.root.bind("<Escape>", lambda e: self.stop_preview())

    # ── HELPERS ──────────────────────────────────────────────────────────────────

    def _update_sampling_label(self):
        raw = self.auto_entry.get().strip()
        try:
            step = max(1, int(raw))
            total = len(self.frames)
            kept = len(range(0, total, step)) if total else 0
            label = f"1/{step}  →  {kept} frames" if total else f"1/{step}"
        except ValueError:
            label = "1/?"
        self.auto_info.config(text=label)

    def _set_preview_btn_color(self, active: bool):
        self.preview_btn.config(bg="#276CF5" if active else "#333")

    def _show_rgb(self, rgb, frame_index):
        h, w = rgb.shape[:2]
        win_w = self.root.winfo_width()
        win_h = self.root.winfo_height() - 210
        scale = min(win_w / w, win_h / h)
        rgb = cv2.resize(rgb, (int(w * scale), int(h * scale)))
        img = ImageTk.PhotoImage(Image.fromarray(rgb))
        self.image_label.configure(image=img)
        self.image_label.image = img
        kept    = sum(self.keep)
        removed = len(self.keep) - kept
        state   = "REMOVED" if not self.keep[frame_index] else "KEEP"
        self.status.config(
            text=f"Frame {frame_index + 1}/{len(self.frames)} | {state} | Kept {kept} | Removed {removed}"
        )

    def _effective_fps(self, extra_divisor=1):
        return max(1.0, self.fps / (self.speed_divisor * extra_divisor))

    def _parse_step(self):
        try:
            return max(1, int(self.auto_entry.get()))
        except ValueError:
            return None

    # ── LOAD ─────────────────────────────────────────────────────────────────────

    def load_video(self):
        path = filedialog.askopenfilename()
        if path:
            self._load_from_path(path)

    def _load_from_path(self, path):
        self.video_path = path
        cap = cv2.VideoCapture(path)
        self.frames, self.keep = [], []
        self.fps = cap.get(cv2.CAP_PROP_FPS) or 30
        while True:
            ret, frame = cap.read()
            if not ret:
                break
            self.frames.append(frame)
            self.keep.append(True)
        cap.release()
        self.current        = 0
        self.speed_divisor  = 1
        self.pending_step   = None
        self.previewing     = False
        self.preview_playing = False
        self._set_preview_btn_color(False)
        self.confirm_sampling_btn.config(state="disabled")
        self.speed_label.config(text="Speed ×1")
        self._update_sampling_label()
        self.show_frame()

    # ── DISPLAY ──────────────────────────────────────────────────────────────────

    def show_frame(self):
        if not self.frames:
            return
        rgb = cv2.cvtColor(self.frames[self.current], cv2.COLOR_BGR2RGB)
        h, w = rgb.shape[:2]
        win_w = self.root.winfo_width()
        win_h = self.root.winfo_height() - 210
        scale = min(win_w / w, win_h / h)
        rgb = cv2.resize(rgb, (int(w * scale), int(h * scale)))
        if not self.keep[self.current]:
            cv2.putText(rgb, "REMOVED", (30, 80),
                        cv2.FONT_HERSHEY_SIMPLEX, 2, (255, 0, 0), 5, cv2.LINE_AA)
        img = ImageTk.PhotoImage(Image.fromarray(rgb))
        self.image_label.configure(image=img)
        self.image_label.image = img
        kept    = sum(self.keep)
        removed = len(self.keep) - kept
        state   = "REMOVED" if not self.keep[self.current] else "KEEP"
        self.status.config(
            text=f"Frame {self.current + 1}/{len(self.frames)} | {state} | Kept {kept} | Removed {removed}"
        )

    # ── NAVIGATION ───────────────────────────────────────────────────────────────

    def next(self):
        if not self.frames:
            return
        if self.previewing:
            if self.preview_index < len(self.preview_frames_list) - 1:
                self.preview_index += 1
                self.current = self.preview_frames_list[self.preview_index]
                self.show_frame()
        else:
            if self.current < len(self.frames) - 1:
                self.current += 1
                self.show_frame()

    def previous(self):
        if not self.frames:
            return
        if self.previewing:
            if self.preview_index > 0:
                self.preview_index -= 1
                self.current = self.preview_frames_list[self.preview_index]
                self.show_frame()
        else:
            if self.current > 0:
                self.current -= 1
                self.show_frame()

    def go_to_frame(self):
        try:
            n = int(self.goto_entry.get()) - 1
        except ValueError:
            return
        if not self.frames:
            return
        n = max(0, min(n, len(self.frames) - 1))
        if self.previewing and self.preview_frames_list:
            closest = min(range(len(self.preview_frames_list)),
                          key=lambda i: abs(self.preview_frames_list[i] - n))
            self.preview_index = closest
            self.current = self.preview_frames_list[self.preview_index]
        else:
            self.current = n
        self.show_frame()

    # ── REMOVE ───────────────────────────────────────────────────────────────────

    def remove_frame(self):
        if not self.frames:
            return
        self.keep[self.current] = not self.keep[self.current]
        if self.current < len(self.frames) - 1:
            self.current += 1
        self.show_frame()

    # ── CUSTOM SAMPLING ──────────────────────────────────────────────────────────

    def preview_sampling(self):
        """Marque keep[] selon le step, lance le preview à vitesse divisée par le step en cours."""
        if not self.frames:
            return
        step = self._parse_step()
        if step is None:
            return

        self.pending_step = step

        for i in range(len(self.keep)):
            self.keep[i] = (i % step == 0)

        kept = sum(self.keep)
        self.auto_info.config(text=f"1/{step}  →  {kept} frames  (pending)")
        self.confirm_sampling_btn.config(state="normal")

        # Lance le preview en tenant compte du step courant en plus du diviseur cumulé
        self._start_preview(extra_divisor=step)

    def confirm_sampling(self):
        """Détruit définitivement les frames non gardées → nouveau working set."""
        if not self.frames or self.pending_step is None:
            return

        step = self.pending_step

        new_frames = [f for f, k in zip(self.frames, self.keep) if k]
        if not new_frames:
            return

        self.speed_divisor *= step
        self.speed_label.config(text=f"Speed ×1/{self.speed_divisor}")

        self.frames = new_frames
        self.keep   = [True] * len(self.frames)

        self.pending_step = None
        self.confirm_sampling_btn.config(state="disabled")

        self.previewing      = False
        self.preview_playing = False
        self._set_preview_btn_color(False)
        self.preview_frames_list = []
        self.preview_index   = 0
        self.current         = 0

        self.auto_info.config(text=f"Working set: {len(self.frames)} frames")
        self.show_frame()

    # ── PREVIEW ──────────────────────────────────────────────────────────────────

    def preview_result(self):
        if not self.frames:
            return
        self._start_preview()

    def _start_preview(self, extra_divisor=1):
        self.preview_frames_list = [i for i in range(len(self.frames)) if self.keep[i]]
        if not self.preview_frames_list:
            return

        self.preview_index   = 0
        self.current         = self.preview_frames_list[0]
        self.previewing      = True
        self.preview_playing = True
        self._set_preview_btn_color(True)
        self.show_frame()

        fps_to_use = self._effective_fps(extra_divisor=extra_divisor)

        def play():
            while self.preview_playing and self.preview_index < len(self.preview_frames_list):
                idx = self.preview_frames_list[self.preview_index]
                rgb = cv2.cvtColor(self.frames[idx], cv2.COLOR_BGR2RGB)

                def update(i=rgb, fi=idx):
                    self._show_rgb(i, fi)

                self.root.after(0, update)
                cv2.waitKey(int(1000 / fps_to_use))

                if self.preview_playing:
                    self.preview_index += 1
                    if self.preview_index < len(self.preview_frames_list):
                        self.current = self.preview_frames_list[self.preview_index]

            if self.previewing:
                self.preview_index   = max(0, len(self.preview_frames_list) - 1)
                self.preview_playing = False

        threading.Thread(target=play, daemon=True).start()

    def stop_playback(self):
        self.preview_playing = False

    def stop_preview(self):
        self.preview_playing = False
        self.previewing      = False
        self.preview_frames_list = []
        self.preview_index   = 0
        self.current         = 0
        self._set_preview_btn_color(False)
        if self.frames:
            self.show_frame()

    # ── DISCARD & RESTART ────────────────────────────────────────────────────────

    def discard_and_restart(self):
        if not self.video_path:
            return
        if messagebox.askyesno("Discard changes",
                               "Discard all changes and reload the original video from frame 0?"):
            self._load_from_path(self.video_path)

    # ── SAVE ─────────────────────────────────────────────────────────────────────

    def save_video(self):
        if not self.frames:
            return

        results_dir = os.path.join(
            os.path.dirname(os.path.abspath(__file__)),
            "..",
            "results"
        )
        os.makedirs(results_dir, exist_ok=True)

        temp_path = os.path.join(results_dir, "temp_clean.avi")

        output = os.path.join(
            results_dir,
            os.path.splitext(os.path.basename(self.video_path))[0] + "_sampled.mp4"
        )

        h, w = self.frames[0].shape[:2]

        writer = cv2.VideoWriter(
            temp_path,
            cv2.VideoWriter_fourcc(*"MJPG"),
            self.fps,
            (w, h),
        )

        for i, frame in enumerate(self.frames):
            if self.keep[i]:
                writer.write(frame)

        writer.release()

        subprocess.run(
            [
                FFMPEG,
                "-y",
                "-i", temp_path,
                "-c:v", "libx264",
                "-preset", "slow",
                "-crf", "18",
                "-pix_fmt", "yuv420p",
                output,
            ],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )

        os.remove(temp_path)

        self.status.config(text=f"Saved: {output}")

root = tk.Tk()
app  = VideoFrameEditor(root)
root.mainloop()