#!/usr/bin/env python3
"""
Aspire moi l'web — Windows Edition
Téléchargeur vidéo/audio : YouTube, TikTok, Twitter, Facebook
Vidéo unique uniquement (pas de playlists)
"""

import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import threading
import subprocess
import sys
import os
import json
import shutil
from pathlib import Path

# ── Config ────────────────────────────────────────────────────────────────────
CONFIG_PATH = Path.home() / ".aspiremoilweb_config.json"

def load_config():
    defaults = {"output_dir": str(Path.home() / "Downloads")}
    if CONFIG_PATH.exists():
        try:
            with open(CONFIG_PATH) as f:
                return {**defaults, **json.load(f)}
        except Exception:
            pass
    return defaults

def save_config(cfg):
    with open(CONFIG_PATH, "w") as f:
        json.dump(cfg, f)

# ── Trouver les outils bundlés ────────────────────────────────────────────────
def get_base_dir():
    """Retourne le dossier de base (fonctionne en mode .exe PyInstaller)"""
    if getattr(sys, 'frozen', False):
        return Path(sys._MEIPASS)
    return Path(__file__).parent

def find_ytdlp():
    base = get_base_dir()
    candidates = [
        base / "yt-dlp.exe",
        base / "yt-dlp" / "yt-dlp.exe",
        Path(sys.executable).parent / "yt-dlp.exe",
        shutil.which("yt-dlp"),
    ]
    for c in candidates:
        if c and Path(c).exists():
            return str(c)
    return None

def find_ffmpeg():
    base = get_base_dir()
    candidates = [
        base / "ffmpeg.exe",
        base / "ffmpeg" / "bin" / "ffmpeg.exe",
        Path(sys.executable).parent / "ffmpeg.exe",
        shutil.which("ffmpeg"),
    ]
    for c in candidates:
        if c and Path(c).exists():
            return str(c)
    return None

# ── Update yt-dlp ─────────────────────────────────────────────────────────────
def update_ytdlp(log_fn=print):
    ytdlp = find_ytdlp()
    if ytdlp:
        log_fn("  Mise à jour yt-dlp…")
        r = subprocess.run([ytdlp, "-U"], capture_output=True, text=True,
                          creationflags=subprocess.CREATE_NO_WINDOW if sys.platform=="win32" else 0)
        msg = (r.stdout + r.stderr).strip()
        log_fn(f"  {msg[:120]}" if msg else "  yt-dlp déjà à jour")
    else:
        log_fn("  ⚠ yt-dlp introuvable dans le bundle")

# ── Build yt-dlp args ─────────────────────────────────────────────────────────
VIDEO_QUALITIES = ["Meilleure dispo", "4K (2160p)", "1080p", "720p", "480p", "360p"]
AUDIO_FORMATS   = ["mp3", "m4a", "wav", "aac", "opus", "flac"]
VIDEO_FORMATS   = ["mp4", "mkv", "webm", "mov"]

def build_ytdlp_args(url, out_dir, mode, quality, fmt):
    ytdlp  = find_ytdlp() or "yt-dlp"
    ffmpeg = find_ffmpeg()

    NO_WINDOW = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0

    base = [ytdlp, "--no-playlist", "--playlist-items", "1", "--no-warnings"]
    if ffmpeg:
        base += ["--ffmpeg-location", str(Path(ffmpeg).parent)]

    template = str(Path(out_dir) / "%(title).80s.%(ext)s")
    base += ["-o", template]

    if mode == "audio":
        base += ["-x", "--audio-format", fmt, "--audio-quality", "0"]
    else:
        q_map = {
            "Meilleure dispo": "bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best",
            "4K (2160p)":      "bestvideo[height<=2160][ext=mp4]+bestaudio[ext=m4a]/best[height<=2160]",
            "1080p":           "bestvideo[height<=1080][ext=mp4]+bestaudio[ext=m4a]/best[height<=1080]",
            "720p":            "bestvideo[height<=720][ext=mp4]+bestaudio[ext=m4a]/best[height<=720]",
            "480p":            "bestvideo[height<=480][ext=mp4]+bestaudio[ext=m4a]/best[height<=480]",
            "360p":            "bestvideo[height<=360][ext=mp4]+bestaudio[ext=m4a]/best[height<=360]",
        }
        selector = q_map.get(quality, q_map["Meilleure dispo"])
        base += ["-f", selector, "--merge-output-format", "mp4"]
        if ffmpeg:
            base += [
                "--postprocessor-args",
                "ffmpeg:-vcodec libx264 -crf 23 -preset ultrafast -acodec aac -b:a 192k -pix_fmt yuv420p",
            ]

    base.append(url)
    return base

# ── Main App ──────────────────────────────────────────────────────────────────
class AspireApp(tk.Tk):
    BG     = "#F2EDE4"
    GLASS  = "#FAF7F2"
    BORDER = "#D6CCBC"
    ACCENT = "#1A1A1A"
    ACCENT2= "#3D3530"
    TEXT   = "#1A1A1A"
    MUTED  = "#7A6E64"
    FONT   = "Montserrat"

    def __init__(self):
        super().__init__()
        self.cfg = load_config()
        self.downloading = False
        self.proc = None
        self._setup_window()
        self._build_ui()
        self.after(400, self._startup_check)

    def _setup_window(self):
        self.title("Aspire moi l'web")
        self.resizable(False, False)
        self.configure(bg=self.BG)
        self.geometry("660x700")
        self.protocol("WM_DELETE_WINDOW", self.on_quit)

    def on_quit(self):
        if self.proc and self.proc.poll() is None:
            self.proc.terminate()
        self.destroy()

    def _build_ui(self):
        # Header
        hdr = tk.Frame(self, bg=self.BG)
        hdr.pack(fill="x", padx=28, pady=(26, 0))
        tk.Label(hdr, text="Aspire moi l'web",
                 font=(self.FONT, 24, "bold italic"),
                 fg=self.TEXT, bg=self.BG).pack(side="left")
        tk.Label(hdr, text="  YouTube · TikTok · Twitter · Facebook",
                 font=(self.FONT, 9, "italic"),
                 fg=self.MUTED, bg=self.BG).pack(side="left", padx=(10, 0))

        self._sep(pady=(16, 16))

        # URL
        self._label("Lien vidéo / audio")
        url_card = tk.Frame(self, bg=self.GLASS,
                            highlightbackground=self.BORDER, highlightthickness=1)
        url_card.pack(fill="x", padx=28, pady=(6, 0))
        self.url_var = tk.StringVar()
        tk.Entry(url_card, textvariable=self.url_var,
                 font=(self.FONT, 11, "italic"),
                 fg=self.TEXT, bg=self.GLASS,
                 bd=0, insertbackground=self.ACCENT,
                 relief="flat").pack(fill="x", padx=14, pady=12)

        paste_row = tk.Frame(self, bg=self.BG)
        paste_row.pack(fill="x", padx=28, pady=(7, 0))
        self._btn_small(paste_row, "Coller", self._paste_url).pack(side="left")
        self._btn_small(paste_row, "Effacer", lambda: self.url_var.set("")).pack(side="left", padx=(8, 0))

        self._sep(pady=(16, 14))

        # Mode
        self._label("Type")
        mode_row = tk.Frame(self, bg=self.BG)
        mode_row.pack(fill="x", padx=28, pady=(7, 0))
        self.mode_var = tk.StringVar(value="video")
        self.btn_video = self._toggle_btn(mode_row, "Vidéo", "video")
        self.btn_audio = self._toggle_btn(mode_row, "Audio", "audio")
        self.btn_video.pack(side="left", padx=(0, 8))
        self.btn_audio.pack(side="left")
        self.mode_var.trace_add("write", self._on_mode_change)

        self._sep(pady=(16, 14))

        # Qualité + Format
        opts_row = tk.Frame(self, bg=self.BG)
        opts_row.pack(fill="x", padx=28)
        q_col = tk.Frame(opts_row, bg=self.BG)
        q_col.pack(side="left", fill="x", expand=True, padx=(0, 14))
        tk.Label(q_col, text="Qualité", font=(self.FONT, 10, "bold italic"),
                 fg=self.MUTED, bg=self.BG, anchor="w").pack(fill="x")
        self.quality_var = tk.StringVar(value="Meilleure dispo")
        self.quality_combo = ttk.Combobox(q_col, textvariable=self.quality_var,
                                          state="readonly", font=(self.FONT, 10, "italic"))
        self.quality_combo["values"] = VIDEO_QUALITIES
        self.quality_combo.pack(fill="x", pady=(5, 0))

        f_col = tk.Frame(opts_row, bg=self.BG)
        f_col.pack(side="left", fill="x", expand=True)
        tk.Label(f_col, text="Format", font=(self.FONT, 10, "bold italic"),
                 fg=self.MUTED, bg=self.BG, anchor="w").pack(fill="x")
        self.format_var = tk.StringVar(value="mp4")
        self.format_combo = ttk.Combobox(f_col, textvariable=self.format_var,
                                         state="readonly", font=(self.FONT, 10, "italic"))
        self.format_combo["values"] = VIDEO_FORMATS
        self.format_combo.pack(fill="x", pady=(5, 0))
        self._style_combos()

        self._sep(pady=(16, 14))

        # Destination
        self._label("Dossier de destination")
        dest_row = tk.Frame(self, bg=self.BG)
        dest_row.pack(fill="x", padx=28, pady=(7, 0))
        self.dest_var = tk.StringVar(value=self.cfg["output_dir"])
        tk.Label(dest_row, textvariable=self.dest_var,
                 font=(self.FONT, 9, "italic"),
                 fg=self.TEXT, bg=self.GLASS, anchor="w",
                 relief="flat", bd=0,
                 highlightbackground=self.BORDER, highlightthickness=1,
                 padx=12, pady=9).pack(side="left", fill="x", expand=True)
        self._btn_small(dest_row, "Changer", self._choose_folder,
                        accent=True).pack(side="left", padx=(8, 0))

        self._sep(pady=(16, 14))

        # Barre de progression
        prog_bg = tk.Frame(self, bg=self.BORDER, height=6)
        prog_bg.pack(fill="x", padx=28)
        prog_bg.pack_propagate(False)
        self.prog_fill = tk.Frame(prog_bg, bg=self.ACCENT, height=6)
        self.prog_fill.place(x=0, y=0, relheight=1, relwidth=0)

        self.status_var = tk.StringVar(value="Prêt")
        tk.Label(self, textvariable=self.status_var,
                 font=(self.FONT, 9, "italic"),
                 fg=self.MUTED, bg=self.BG, anchor="w").pack(fill="x", padx=28, pady=(7, 0))

        # Bouton télécharger + annuler côte à côte
        btn_row = tk.Frame(self, bg=self.BG)
        btn_row.pack(fill="x", padx=28, pady=(14, 0))

        self.dl_btn = tk.Button(btn_row, text="Télécharger",
                                font=(self.FONT, 13, "bold italic"),
                                fg=self.BG, bg=self.ACCENT,
                                activebackground=self.ACCENT2,
                                activeforeground=self.BG,
                                relief="flat", bd=0,
                                cursor="hand2", pady=15,
                                command=self.start_download)
        self.dl_btn.pack(side="left", fill="x", expand=True)

        self.stop_btn = tk.Button(btn_row, text="⏹ Stop",
                                  font=(self.FONT, 13, "bold italic"),
                                  fg=self.TEXT, bg=self.GLASS,
                                  activebackground="#c0392b",
                                  activeforeground="white",
                                  relief="flat", bd=0,
                                  highlightbackground=self.BORDER,
                                  highlightthickness=1,
                                  cursor="hand2", pady=15,
                                  state="disabled",
                                  command=self._cancel_download)
        self.stop_btn.pack(side="left", padx=(8, 0), fill="x", expand=False, ipadx=20)

        self._sep(pady=(16, 0))

        # Log
        log_card = tk.Frame(self, bg=self.GLASS,
                            highlightbackground=self.BORDER, highlightthickness=1)
        log_card.pack(fill="both", expand=True, padx=28, pady=(0, 20))
        self.log_text = tk.Text(log_card, height=7,
                                font=("Consolas", 9),
                                fg=self.MUTED, bg=self.GLASS,
                                relief="flat", bd=0, wrap="word",
                                state="disabled", padx=12, pady=10)
        scroll = tk.Scrollbar(log_card, command=self.log_text.yview,
                              relief="flat", bd=0)
        self.log_text["yscrollcommand"] = scroll.set
        self.log_text.pack(side="left", fill="both", expand=True)
        scroll.pack(side="right", fill="y")

    def _sep(self, pady=(12, 12)):
        tk.Frame(self, bg=self.BORDER, height=1).pack(fill="x", padx=28, pady=pady)

    def _label(self, text):
        tk.Label(self, text=text, font=(self.FONT, 10, "bold italic"),
                 fg=self.MUTED, bg=self.BG, anchor="w").pack(fill="x", padx=28)

    def _btn_small(self, parent, text, cmd, accent=False):
        bg = self.ACCENT if accent else self.GLASS
        fg = self.BG if accent else self.TEXT
        return tk.Button(parent, text=text,
                         font=(self.FONT, 10, "bold italic"),
                         fg=fg, bg=bg,
                         activebackground=self.ACCENT2,
                         activeforeground=self.BG,
                         relief="flat", bd=0,
                         highlightbackground=self.BORDER,
                         highlightthickness=1,
                         padx=12, pady=6,
                         cursor="hand2", command=cmd)

    def _toggle_btn(self, parent, text, value):
        btn = tk.Button(parent, text=text,
                        font=(self.FONT, 11, "bold italic"),
                        relief="flat", bd=0,
                        highlightbackground=self.BORDER,
                        highlightthickness=1,
                        padx=20, pady=9,
                        cursor="hand2",
                        command=lambda: self.mode_var.set(value))
        self._refresh_toggle(btn, value)
        return btn

    def _on_mode_change(self, *_):
        mode = self.mode_var.get()
        self._refresh_toggle(self.btn_video, "video")
        self._refresh_toggle(self.btn_audio, "audio")
        if mode == "audio":
            self.quality_combo["values"] = ["Qualité max"]
            self.quality_var.set("Qualité max")
            self.quality_combo.config(state="disabled")
            self.format_combo["values"] = AUDIO_FORMATS
            self.format_var.set("mp3")
        else:
            self.quality_combo["values"] = VIDEO_QUALITIES
            self.quality_var.set("Meilleure dispo")
            self.quality_combo.config(state="readonly")
            self.format_combo["values"] = VIDEO_FORMATS
            self.format_var.set("mp4")

    def _refresh_toggle(self, btn, value):
        active = self.mode_var.get() == value
        btn.config(bg=self.ACCENT if active else self.GLASS,
                   fg=self.BG if active else self.TEXT)

    def _style_combos(self):
        style = ttk.Style()
        style.theme_use("default")
        style.configure("TCombobox",
                        fieldbackground=self.GLASS,
                        background=self.GLASS,
                        foreground=self.TEXT,
                        selectbackground=self.ACCENT,
                        selectforeground=self.BG,
                        bordercolor=self.BORDER,
                        padding=8)

    def _paste_url(self):
        try:
            self.url_var.set(self.clipboard_get().strip())
        except Exception:
            pass

    def _choose_folder(self):
        folder = filedialog.askdirectory(initialdir=self.dest_var.get())
        if folder:
            self.dest_var.set(folder)
            self.cfg["output_dir"] = folder
            save_config(self.cfg)

    def log(self, msg):
        self.log_text.config(state="normal")
        self.log_text.insert("end", msg + "\n")
        self.log_text.see("end")
        self.log_text.config(state="disabled")

    def set_status(self, msg):
        self.status_var.set(msg)

    def _update_progress(self, pct):
        self.prog_fill.place(x=0, y=0, relheight=1, relwidth=pct / 100)

    def _startup_check(self):
        self.log("Vérification des dépendances…")
        threading.Thread(target=self._check_deps, daemon=True).start()

    def _check_deps(self):
        if not find_ytdlp():
            self.after(0, lambda: self.log("  ⚠ yt-dlp introuvable dans le bundle !"))
        else:
            self.after(0, lambda: self.log("  ✓ yt-dlp OK"))
            update_ytdlp(lambda m: self.after(0, lambda m=m: self.log(m)))
        if not find_ffmpeg():
            self.after(0, lambda: self.log("  ⚠ ffmpeg introuvable dans le bundle !"))
        else:
            self.after(0, lambda: self.log("  ✓ ffmpeg OK"))
        self.after(0, lambda: self.set_status("Prêt"))
        self.after(0, lambda: self.log("✅ Prêt à télécharger.\n"))

    def start_download(self):
        url = self.url_var.get().strip()
        if not url:
            messagebox.showwarning("Lien manquant", "Collez un lien vidéo.")
            return
        if not url.startswith("http"):
            messagebox.showwarning("Lien invalide", "Le lien doit commencer par http://")
            return
        out_dir = self.dest_var.get()
        if not Path(out_dir).exists():
            messagebox.showerror("Dossier introuvable", f"'{out_dir}' n'existe pas.")
            return

        args = build_ytdlp_args(url, out_dir, self.mode_var.get(),
                                self.quality_var.get(), self.format_var.get())
        self.log(f"\n▶ Démarrage…")
        self.downloading = True
        self.dl_btn.config(state="disabled", bg="#999")
        self.stop_btn.config(state="normal")
        self._update_progress(0)
        self.set_status("Téléchargement en cours…")
        threading.Thread(target=self._run_download, args=(args,), daemon=True).start()

    def _cancel_download(self):
        if self.proc and self.proc.poll() is None:
            self.proc.terminate()
        self._reset_ui("Annulé.")

    def _run_download(self, args):
        NO_WINDOW = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
        try:
            self.proc = subprocess.Popen(args, stdout=subprocess.PIPE,
                                         stderr=subprocess.STDOUT,
                                         text=True, bufsize=1,
                                         creationflags=NO_WINDOW)
            for line in self.proc.stdout:
                line = line.rstrip()
                if not line:
                    continue
                self.after(0, lambda l=line: self.log(l))
                if "[download]" in line and "%" in line:
                    try:
                        pct = float(line.split("%")[0].split()[-1])
                        self.after(0, lambda p=min(pct * 0.85, 85): self._update_progress(p))
                        self.after(0, lambda l=line: self.set_status(l.strip()))
                    except Exception:
                        pass
                elif "[ffmpeg]" in line or "Merging" in line:
                    self.after(0, lambda: self._update_progress(90))
                    self.after(0, lambda: self.set_status("Encodage H.264…"))
            self.proc.wait()
            if self.proc.returncode == 0:
                self.after(0, lambda: self._update_progress(100))
                self.after(0, lambda: self._reset_ui("✅ Téléchargement terminé !"))
            else:
                self.after(0, lambda: self._reset_ui("⚠ Erreur — voir le log"))
        except Exception as e:
            self.after(0, lambda: self.log(f"Erreur: {e}"))
            self.after(0, lambda: self._reset_ui("Erreur"))

    def _reset_ui(self, msg):
        self.downloading = False
        self.proc = None
        self.dl_btn.config(state="normal", bg=self.ACCENT)
        self.stop_btn.config(state="disabled")
        self.set_status(msg)
        self.log(msg)


if __name__ == "__main__":
    app = AspireApp()
    app.mainloop()
