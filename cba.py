"""
Senior and Junior Secondary School -- CBA Photo Prep Tool
================================================
Batch face-aware cropping + compression tool for student ID photos
before CBA portal upload.

Run with:  python3 app.py

Optional sound files (drop these in the same folder as this script):
    boot.wav      - played once when the app starts
    scan.wav      - played briefly when processing begins
    complete.wav  - played when a batch finishes
    alert.wav     - played if any file needed manual review

Sound is optional -- the app works silently if the files are missing.
"""

import os
import sys
import threading
import time
import tkinter as tk
from tkinter import filedialog, ttk

from photo_ops import process_folder, list_image_files, SUPPORTED_EXT

SOUND_AVAILABLE = False
try:
    import pygame

    def _init_mixer():
        global SOUND_AVAILABLE
        try:
            pygame.mixer.init()
            SOUND_AVAILABLE = True
        except Exception:
            SOUND_AVAILABLE = False

    # Audio init can hang forever on machines with no working audio device
    # (seen on some headless/locked-down school PCs). Never let it block
    # the app from starting -- give it a couple seconds, then move on.
    _mixer_thread = threading.Thread(target=_init_mixer, daemon=True)
    _mixer_thread.start()
    _mixer_thread.join(timeout=2.0)
except Exception:
    SOUND_AVAILABLE = False

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# ---- Military / tactical green theme ----
BG_DARK = "#0c130c"
BG_PANEL = "#121a12"
GREEN_BRIGHT = "#39ff6a"
GREEN_MID = "#4caf50"
GREEN_DIM = "#2e5c2e"
AMBER = "#ffb020"
RED_ALERT = "#ff4444"
FONT_MONO = ("Consolas", 8)
FONT_MONO_BOLD = ("Consolas", 9, "bold")
FONT_HEADER = ("Consolas", 13, "bold")
FONT_SMALL = ("Consolas", 7)


def play_sound(name):
    if not SOUND_AVAILABLE:
        return
    path = os.path.join(BASE_DIR, name)
    if not os.path.exists(path):
        return

    def _play():
        try:
            pygame.mixer.Sound(path).play()
        except Exception:
            pass

    # Fire-and-forget on its own thread so a flaky sound file/driver
    # can never stall the UI or the processing batch.
    threading.Thread(target=_play, daemon=True).start()


class PhotoOpsApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("KIKULE SEC. SCHOOL -- CBA PHOTO PREP UNIT")
        self.geometry("880x620")
        self.configure(bg=BG_DARK)
        self.resizable(True, True)

        self.input_folder = tk.StringVar(value="")
        self.output_folder = tk.StringVar(value="")
        self.status_text = tk.StringVar(value="STANDING BY")

        self.out_width = tk.StringVar(value="600")
        self.out_height = tk.StringVar(value="750")
        self.max_size_kb = tk.StringVar(value="950")

        self._build_header()
        self._build_control_panel()
        self._build_settings_panel()
        self._build_progress()
        self._build_log()
        self._build_footer()

        self.after(300, lambda: play_sound("boot.wav"))
        self._log("SYSTEM READY.", GREEN_MID)
        self._log("Awaiting input directory selection...", GREEN_DIM)

    # ---------------------------------------------------------------
    # UI construction
    # ---------------------------------------------------------------
    def _build_header(self):
        header = tk.Frame(self, bg=BG_DARK)
        header.pack(fill="x", padx=16, pady=(14, 6))

        tk.Label(
            header, text="/// CBA PHOTO PREP UNIT ///",
            font=FONT_HEADER, fg=GREEN_BRIGHT, bg=BG_DARK
        ).pack(anchor="w")

        tk.Label(
            header, text="Kikule Secondary School -- Student ID Photo Processor",
            font=FONT_MONO, fg=GREEN_MID, bg=BG_DARK
        ).pack(anchor="w")

        sep = tk.Frame(self, bg=GREEN_DIM, height=2)
        sep.pack(fill="x", padx=16, pady=(4, 10))

    def _build_control_panel(self):
        panel = tk.Frame(self, bg=BG_PANEL, highlightbackground=GREEN_DIM, highlightthickness=1)
        panel.pack(fill="x", padx=16, pady=6)

        self._folder_row(panel, "INPUT DIR  >", self.input_folder, self._pick_input)
        self._folder_row(panel, "OUTPUT DIR >", self.output_folder, self._pick_output)

        btn_row = tk.Frame(panel, bg=BG_PANEL)
        btn_row.pack(fill="x", padx=14, pady=(4, 12))

        self.start_btn = tk.Button(
            btn_row, text="  ENGAGE / START PROCESSING  ",
            font=FONT_MONO_BOLD, fg=BG_DARK, bg=GREEN_BRIGHT,
            activebackground=GREEN_MID, activeforeground=BG_DARK,
            relief="flat", bd=0, padx=10, pady=8,
            command=self._start_processing
        )
        self.start_btn.pack(side="left")

        tk.Label(
            btn_row, textvariable=self.status_text,
            font=FONT_MONO_BOLD, fg=AMBER, bg=BG_PANEL
        ).pack(side="left", padx=20)

    def _folder_row(self, parent, label, var, command):
        row = tk.Frame(parent, bg=BG_PANEL)
        row.pack(fill="x", padx=14, pady=(12, 4))

        tk.Label(row, text=label, font=FONT_MONO_BOLD, fg=GREEN_MID, bg=BG_PANEL, width=12, anchor="w").pack(side="left")
        entry = tk.Entry(row, textvariable=var, font=FONT_MONO, fg=GREEN_BRIGHT, bg="#08100a",
                          insertbackground=GREEN_BRIGHT, relief="flat", highlightbackground=GREEN_DIM,
                          highlightthickness=1)
        entry.pack(side="left", fill="x", expand=True, padx=8, ipady=4)

        tk.Button(
            row, text="BROWSE", font=FONT_MONO, fg=GREEN_BRIGHT, bg="#1a2a1a",
            activebackground=GREEN_DIM, relief="flat", bd=0, padx=10,
            command=command
        ).pack(side="left")

    def _build_settings_panel(self):
        panel = tk.Frame(self, bg=BG_PANEL, highlightbackground=GREEN_DIM, highlightthickness=1)
        panel.pack(fill="x", padx=16, pady=6)

        tk.Label(
            panel, text="OUTPUT SPECS", font=FONT_MONO_BOLD, fg=GREEN_MID, bg=BG_PANEL
        ).pack(anchor="w", padx=14, pady=(10, 2))

        row = tk.Frame(panel, bg=BG_PANEL)
        row.pack(fill="x", padx=14, pady=(2, 4))

        self._spec_field(row, "WIDTH (px)", self.out_width, 6)
        self._spec_field(row, "HEIGHT (px)", self.out_height, 6)
        self._spec_field(row, "MAX SIZE (KB)", self.max_size_kb, 6)

        tk.Label(
            row, text="  <-- crop size + compression ceiling for every photo",
            font=FONT_SMALL, fg=GREEN_DIM, bg=BG_PANEL
        ).pack(side="left", padx=(10, 0))

        tk.Label(
            panel, text="Photos are cropped to this exact size (aspect ratio guides the face crop), then compressed to fit under the max size.",
            font=FONT_SMALL, fg=GREEN_DIM, bg=BG_PANEL
        ).pack(anchor="w", padx=14, pady=(0, 10))

    def _spec_field(self, parent, label, var, width_chars):
        wrap = tk.Frame(parent, bg=BG_PANEL)
        wrap.pack(side="left", padx=(0, 14))

        tk.Label(wrap, text=label, font=FONT_SMALL, fg=GREEN_MID, bg=BG_PANEL).pack(anchor="w")
        entry = tk.Entry(
            wrap, textvariable=var, font=FONT_MONO, fg=GREEN_BRIGHT, bg="#08100a",
            insertbackground=GREEN_BRIGHT, relief="flat", highlightbackground=GREEN_DIM,
            highlightthickness=1, width=width_chars
        )
        entry.pack(anchor="w", ipady=3)

    def _build_progress(self):
        frame = tk.Frame(self, bg=BG_DARK)
        frame.pack(fill="x", padx=16, pady=(10, 4))

        style = ttk.Style()
        style.theme_use("default")
        style.configure(
            "Military.Horizontal.TProgressbar",
            troughcolor="#08100a", background=GREEN_BRIGHT,
            bordercolor=GREEN_DIM, lightcolor=GREEN_BRIGHT, darkcolor=GREEN_MID
        )
        self.progress = ttk.Progressbar(
            frame, style="Military.Horizontal.TProgressbar",
            orient="horizontal", mode="determinate"
        )
        self.progress.pack(fill="x", ipady=4)

        self.progress_label = tk.Label(
            frame, text="0 / 0 FILES PROCESSED",
            font=FONT_MONO, fg=GREEN_DIM, bg=BG_DARK
        )
        self.progress_label.pack(anchor="e", pady=(2, 0))

    def _build_log(self):
        frame = tk.Frame(self, bg=BG_DARK)
        frame.pack(fill="both", expand=True, padx=16, pady=(6, 6))

        tk.Label(frame, text="OPERATION LOG", font=FONT_MONO_BOLD, fg=GREEN_MID, bg=BG_DARK).pack(anchor="w")

        log_frame = tk.Frame(frame, bg="#08100a", highlightbackground=GREEN_DIM, highlightthickness=1)
        log_frame.pack(fill="both", expand=True, pady=(4, 0))

        scrollbar = tk.Scrollbar(log_frame)
        scrollbar.pack(side="right", fill="y")

        self.log_box = tk.Text(
            log_frame, bg="#08100a", fg=GREEN_BRIGHT, font=FONT_MONO,
            insertbackground=GREEN_BRIGHT, relief="flat", wrap="word",
            yscrollcommand=scrollbar.set, state="disabled", padx=8, pady=6
        )
        self.log_box.pack(side="left", fill="both", expand=True)
        scrollbar.config(command=self.log_box.yview)

        self.log_box.tag_config("green", foreground=GREEN_BRIGHT)
        self.log_box.tag_config("dim", foreground=GREEN_DIM)
        self.log_box.tag_config("amber", foreground=AMBER)
        self.log_box.tag_config("red", foreground=RED_ALERT)

    def _build_footer(self):
        footer = tk.Frame(self, bg=BG_DARK)
        footer.pack(fill="x", padx=16, pady=(0, 12))
        tk.Label(
            footer, text="Output files keep original admission-number filenames -- saved as .jpg, sized per OUTPUT SPECS above.",
            font=FONT_MONO, fg=GREEN_DIM, bg=BG_DARK
        ).pack(anchor="w")

    # ---------------------------------------------------------------
    # Actions
    # ---------------------------------------------------------------
    def _pick_input(self):
        folder = filedialog.askdirectory(title="Select folder containing raw student photos")
        if folder:
            self.input_folder.set(folder)
            count = len(list_image_files(folder))
            self._log(f"Input directory locked: {folder}", GREEN_MID)
            self._log(f"{count} image file(s) detected ({', '.join(sorted(SUPPORTED_EXT))}).", GREEN_DIM)

    def _pick_output(self):
        folder = filedialog.askdirectory(title="Select output folder for processed photos")
        if folder:
            self.output_folder.set(folder)
            self._log(f"Output directory set: {folder}", GREEN_MID)

    def _log(self, message, color_tag=GREEN_BRIGHT):
        tag = {
            GREEN_BRIGHT: "green", GREEN_DIM: "dim", AMBER: "amber", RED_ALERT: "red"
        }.get(color_tag, "green")
        self.log_box.configure(state="normal")
        timestamp = time.strftime("%H:%M:%S")
        self.log_box.insert("end", f"[{timestamp}] {message}\n", tag)
        self.log_box.see("end")
        self.log_box.configure(state="disabled")

    def _start_processing(self):
        in_dir = self.input_folder.get().strip()
        out_dir = self.output_folder.get().strip()

        if not in_dir or not os.path.isdir(in_dir):
            self._log("ABORT: Valid input directory not set.", RED_ALERT)
            return
        if not out_dir:
            self._log("ABORT: Output directory not set.", RED_ALERT)
            return

        files = list_image_files(in_dir)
        if not files:
            self._log("ABORT: No supported image files found in input directory.", RED_ALERT)
            return

        try:
            width = int(self.out_width.get().strip())
            height = int(self.out_height.get().strip())
            max_kb = int(self.max_size_kb.get().strip())
            if width <= 0 or height <= 0 or max_kb <= 0:
                raise ValueError
        except ValueError:
            self._log("ABORT: Width, height, and max size must be positive whole numbers.", RED_ALERT)
            return

        max_bytes = max_kb * 1024
        target_bytes = int(max_bytes * 0.95)  # aim a bit under the ceiling for safety margin

        self.start_btn.config(state="disabled", bg=GREEN_DIM)
        self.status_text.set("PROCESSING...")
        self.progress["value"] = 0
        self.progress["maximum"] = len(files)
        self.progress_label.config(text=f"0 / {len(files)} FILES PROCESSED")

        self._log(f"OPERATION START -- {len(files)} file(s) queued. Target: {width}x{height}px, max {max_kb}KB.", AMBER)
        play_sound("scan.wav")

        thread = threading.Thread(
            target=self._run_batch, args=(in_dir, out_dir, width, height, target_bytes, max_bytes), daemon=True
        )
        thread.start()

    def _run_batch(self, in_dir, out_dir, width, height, target_bytes, max_bytes):
        fallback_count = [0]
        error_count = [0]

        def on_progress(i, total, result):
            def update_ui():
                self.progress["value"] = i
                self.progress_label.config(text=f"{i} / {total} FILES PROCESSED")

                if result.status == "OK":
                    self._log(f"{result.filename} -> OK  ({result.final_size_kb} KB)", GREEN_BRIGHT)
                elif result.status == "FALLBACK":
                    fallback_count[0] += 1
                    self._log(f"{result.filename} -> CENTER-CROP FALLBACK -- {result.detail} ({result.final_size_kb} KB)", AMBER)
                else:
                    error_count[0] += 1
                    self._log(f"{result.filename} -> ERROR -- {result.detail}", RED_ALERT)

            self.after(0, update_ui)

        process_folder(
            in_dir, out_dir, progress_callback=on_progress,
            output_width=width, output_height=height,
            target_bytes=target_bytes, max_bytes=max_bytes,
        )

        def finish():
            self.status_text.set("COMPLETE")
            self.start_btn.config(state="normal", bg=GREEN_BRIGHT)
            self._log("OPERATION COMPLETE.", GREEN_BRIGHT)
            if fallback_count[0]:
                self._log(f"{fallback_count[0]} file(s) used center-crop fallback (no face detected) -- worth a quick visual check.", AMBER)
            if error_count[0]:
                self._log(f"{error_count[0]} file(s) FAILED -- see log above.", RED_ALERT)
                play_sound("alert.wav")
            else:
                play_sound("complete.wav")

        self.after(0, finish)


if __name__ == "__main__":
    app = PhotoOpsApp()
    app.mainloop()
