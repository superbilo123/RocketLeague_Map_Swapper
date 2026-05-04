import tkinter as tk
from tkinter import filedialog, messagebox, ttk
import json
import os
import re
import shutil
import tempfile
import threading
import urllib.request
import webbrowser
import zipfile
from PIL import Image, ImageTk

# ── Windows DPI fix — makes the app crisp on high-DPI/modern screens ───────────
try:
    import ctypes
    ctypes.windll.shcore.SetProcessDpiAwareness(2)
except Exception:
    try:
        ctypes.windll.user32.SetProcessDPIAware()
    except Exception:
        pass

# ── Constants ──────────────────────────────────────────────────────────────────
APP_NAME        = "RL Map Swapper"
APP_VERSION     = "1.0.2"
_CONFIG_DIR     = os.path.join(os.environ.get("APPDATA", os.path.expanduser("~")), "RLmapswapper-config")
os.makedirs(_CONFIG_DIR, exist_ok=True)
CONFIG_FILE     = os.path.join(_CONFIG_DIR, "config.json")
MAPS_WEBSITE         = "https://bakkesplugins.com/maps"
TEXTURES_MOD_PAGE    = "https://videogamemods.com/vgm/rocketleague/mods/workshop-textures"
TEXTURES_DOWNLOAD_URL = ("https://uploads.videogamemods.com/communities/vgm/mods/"
                         "workshop-textures-8490c90c-fdce-4eb4-a30c-a9151f260c3d/files/"
                         "1496064905_Workshop-textures.zip")
_TEXTURES_UA         = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                        "AppleWebKit/537.36 (KHTML, like Gecko) "
                        "Chrome/124.0.0.0 Safari/537.36")
GITHUB_API_LATEST    = ("https://api.github.com/repos/superbilo123/"
                        "RocketLeague_Map_Swapper/releases/latest")
GITHUB_RELEASES_PAGE = "https://github.com/superbilo123/RocketLeague_Map_Swapper/releases"
_SPINNER_FRAMES      = ["◐", "◓", "◑", "◒"]
UPK_FILENAME    = "Labs_Underpass_P.upk"
BACKUP_FILENAME  = "Labs_Underpass_P.upk"
BACKUP_SUBFOLDER = "_Standard Underpass (Backup)"

DEFAULT_COOKED = r"C:\Program Files\Epic Games\rocketleague\TAGame\CookedPCConsole"

PREVIEW_W = 280   # sidebar width in pixels

# ── Colours ────────────────────────────────────────────────────────────────────
BG       = "#0d0f14"
SURFACE  = "#13161e"
SURFACE2 = "#1a1e2a"
BORDER   = "#252a38"
ACCENT   = "#4f8ef7"
ACCENT2  = "#2563c7"
GOLD     = "#f5c842"
GREEN    = "#3ecf6e"
TEXT     = "#e8eaf0"
TEXT_DIM = "#6b7280"
TEXT_MID = "#9aa3b2"

# ── Fonts ──────────────────────────────────────────────────────────────────────
FONT_TITLE = ("Trebuchet MS", 20, "bold")
FONT_LABEL = ("Trebuchet MS", 10, "bold")
FONT_BODY  = ("Trebuchet MS", 10)
FONT_SMALL = ("Trebuchet MS", 9)
FONT_BTN   = ("Trebuchet MS", 10, "bold")
FONT_MONO  = ("Courier New", 9)
FONT_MAP   = ("Trebuchet MS", 11, "bold")


# ── Config ─────────────────────────────────────────────────────────────────────
def load_config():
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE) as f:
                return json.load(f)
        except Exception:
            pass
    return {"maps_dir": "", "cooked_dir": DEFAULT_COOKED, "favourites": [], "active_map": ""}

def save_config(cfg):
    with open(CONFIG_FILE, "w") as f:
        json.dump(cfg, f, indent=2)


# ── Utility ────────────────────────────────────────────────────────────────────
def _find_upk(folder_path):
    for root, _, files in os.walk(folder_path):
        for f in files:
            if f.lower().endswith((".upk", ".udk")):
                return os.path.join(root, f)
    return None

_PREVIEW_EXTS = (".jfif", ".jpg", ".jpeg", ".png", ".webp", ".bmp", ".gif")

def _find_preview_image(folder_path):
    for root, _, files in os.walk(folder_path):
        for f in files:
            if f.lower().endswith(_PREVIEW_EXTS):
                return os.path.join(root, f)
    return None

_MAP_JSON_NAMES   = {"mapinfo.json", "info.json", "map.json", "metadata.json"}
_MAP_JSON_FIELDS  = {"title", "author", "description", "previewurl", "name", "desc"}
_FIELD_ALIASES    = {"desc": "Description", "name": "Title",
                     "map_name": "Title", "creator": "Author", "made_by": "Author"}

def _find_map_json(folder_path):
    fallback = None
    for root, _, files in os.walk(folder_path):
        for f in files:
            if not f.lower().endswith(".json"):
                continue
            path = os.path.join(root, f)
            if f.lower() in _MAP_JSON_NAMES:
                return path
            if fallback is None:
                fallback = path
    return fallback

def _parse_map_json(json_path):
    if json_path is None:
        return None
    raw = None
    for enc in ("utf-8-sig", "utf-8", "latin-1"):
        try:
            with open(json_path, encoding=enc) as f:
                text = f.read()
            try:
                raw = json.loads(text)
            except json.JSONDecodeError:
                # Try repairing trailing commas before } or ]
                fixed = re.sub(r",\s*([}\]])", r"\1", text)
                raw = json.loads(fixed)
            break
        except (UnicodeDecodeError, json.JSONDecodeError):
            continue
    if raw is None or not isinstance(raw, dict):
        return None
    normalised = {k.lower(): v for k, v in raw.items()}
    if not _MAP_JSON_FIELDS.intersection(normalised):
        return None
    # Apply field aliases so non-standard keys map to standard ones
    data = {}
    for k, v in raw.items():
        std_key = _FIELD_ALIASES.get(k.lower(), k.title())
        val = (v or "") if isinstance(v, str) else ("" if v is None else v)
        data.setdefault(std_key, val)
    desc = str(data.get("Description", ""))
    desc = re.sub(r"<br\s*/?>", "\n", desc, flags=re.IGNORECASE)
    desc = re.sub(r"<[^>]+>", "", desc).strip()
    data["Description"] = desc
    return data

def _sep(parent, color=BORDER, height=1):
    tk.Frame(parent, bg=color, height=height).pack(fill="x")

def _flat_btn(parent, text, command, bg=SURFACE, fg=TEXT, hover_bg=BORDER):
    b = tk.Button(
        parent, text=text, command=command,
        font=FONT_BTN, bg=bg, fg=fg,
        relief="flat", cursor="hand2", padx=12, pady=5, bd=0,
        activebackground=hover_bg, activeforeground=TEXT,
    )
    b.bind("<Enter>", lambda e, _b=b, _h=hover_bg: _b.config(bg=_h))
    b.bind("<Leave>", lambda e, _b=b, _bg=bg:      _b.config(bg=_bg))
    return b


# ── Main App ───────────────────────────────────────────────────────────────────
class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.cfg = load_config()
        self.title(APP_NAME)
        self.configure(bg=BG)
        self.geometry("1140x700")
        self.minsize(800, 500)

        self._check_anim_id    = None
        self._warning_visible  = False
        self._tex_warn_visible = False
        self._refresh_after_id = None

        self._build_ui()
        self.after(120, self._startup_checks)

    # ── Build UI ───────────────────────────────────────────────────────────────
    def _build_ui(self):

        # ── Header ──────────────────────────────────────────────────────────────
        hdr = tk.Frame(self, bg=SURFACE)
        hdr.pack(fill="x")
        hdr_in = tk.Frame(hdr, bg=SURFACE)
        hdr_in.pack(fill="x", padx=24, pady=14)

        tk.Label(hdr_in, text="⚡  RL Map Swapper",
                 font=FONT_TITLE, bg=SURFACE, fg=ACCENT).pack(side="left")

        link = tk.Label(hdr_in, text="⬇  Download Maps",
                        font=FONT_BODY, bg=SURFACE, fg=ACCENT, cursor="hand2")
        link.pack(side="right", padx=(0, 4))
        link.bind("<Button-1>", lambda _: webbrowser.open(MAPS_WEBSITE))
        link.bind("<Enter>",    lambda _: link.config(fg=TEXT))
        link.bind("<Leave>",    lambda _: link.config(fg=ACCENT))

        tk.Label(hdr_in, text="|", font=FONT_BODY, bg=SURFACE, fg=BORDER
                 ).pack(side="right", padx=6)

        self._upd_btn = tk.Label(hdr_in, text="🔄  Check for Updates",
                                 font=FONT_BODY, bg=SURFACE, fg=TEXT_MID, cursor="hand2")
        self._upd_btn.pack(side="right", padx=(0, 4))
        self._upd_btn.bind("<Button-1>", lambda _: self._check_for_updates())
        self._upd_btn.bind("<Enter>",    lambda _: self._upd_btn.config(fg=TEXT))
        self._upd_btn.bind("<Leave>",    lambda _: self._upd_btn.config(fg=TEXT_MID))

        tk.Label(hdr_in, text="|", font=FONT_BODY, bg=SURFACE, fg=BORDER
                 ).pack(side="right", padx=6)

        self._tex_btn = tk.Label(hdr_in, text="🖼  Get Workshop Textures",
                                 font=FONT_BODY, bg=SURFACE, fg=TEXT_MID, cursor="hand2")
        self._tex_btn.pack(side="right", padx=(0, 4))
        self._tex_btn.bind("<Button-1>", lambda _: self._install_workshop_textures())
        self._tex_btn.bind("<Enter>",    lambda _: self._tex_btn.config(fg=TEXT))
        self._tex_btn.bind("<Leave>",    lambda _: self._tex_btn.config(fg=TEXT_MID))

        _sep(self, BORDER, 2)

        # ── Banner container (stacks all warning banners, avoids overlap) ────────
        self._banners_frame = tk.Frame(self, bg=BG)
        self._banners_frame.pack(fill="x")

        # BakkesMod mods-folder banner (hidden until needed)
        self.warn_frame = tk.Frame(self._banners_frame, bg="#2a1a0e")
        tk.Label(self.warn_frame,
                 text="Warning: BakkesMod mods folder detected. This may block custom maps.",
                 font=FONT_BODY, bg="#2a1a0e", fg="#f5a742", anchor="w"
                 ).pack(side="left", padx=16, pady=10)
        tk.Button(self.warn_frame, text="Migrate to Maps Folder",
                  font=FONT_BTN, bg="#4a2e10", fg=GOLD,
                  relief="flat", cursor="hand2", padx=10, pady=4,
                  activebackground="#6a3e18", activeforeground=GOLD,
                  command=self._migrate_mods
                  ).pack(side="right", padx=12, pady=8)

        # Workshop textures banner (hidden until needed)
        self.tex_warn_frame = tk.Frame(self._banners_frame, bg="#0e1e2a")
        tk.Label(self.tex_warn_frame,
                 text="Workshop textures not detected. Custom maps may appear broken without them.",
                 font=FONT_BODY, bg="#0e1e2a", fg="#74b8f5", anchor="w"
                 ).pack(side="left", padx=16, pady=10)
        tk.Button(self.tex_warn_frame, text="I already have them",
                  font=FONT_BTN, bg="#0a1824", fg=TEXT_MID,
                  relief="flat", cursor="hand2", padx=10, pady=4,
                  activebackground="#152030", activeforeground=TEXT,
                  command=self._dismiss_tex_warning
                  ).pack(side="right", padx=(4, 12), pady=8)
        tk.Button(self.tex_warn_frame, text="Download Textures Now",
                  font=FONT_BTN, bg="#1a3a5c", fg="#74b8f5",
                  relief="flat", cursor="hand2", padx=10, pady=4,
                  activebackground="#254d78", activeforeground=TEXT,
                  command=self._install_workshop_textures
                  ).pack(side="right", padx=0, pady=8)

        # ── Settings ────────────────────────────────────────────────────────────
        sett = tk.Frame(self, bg=SURFACE2)
        sett.pack(fill="x")
        sett_in = tk.Frame(sett, bg=SURFACE2)
        sett_in.pack(fill="x", padx=20, pady=10)
        sett_in.columnconfigure(1, weight=1)

        tk.Label(sett_in, text="Maps Folder", font=FONT_LABEL,
                 bg=SURFACE2, fg=TEXT_MID
                 ).grid(row=0, column=0, sticky="w", padx=(0, 8), pady=(0, 6))
        self.maps_var = tk.StringVar(value=self.cfg.get("maps_dir", ""))
        self.maps_var.trace_add("write", self._on_maps_dir_changed)
        tk.Entry(sett_in, textvariable=self.maps_var, font=FONT_MONO,
                 bg=SURFACE, fg=TEXT, insertbackground=TEXT,
                 relief="flat", bd=0, highlightthickness=1,
                 highlightbackground=BORDER, highlightcolor=ACCENT
                 ).grid(row=0, column=1, sticky="ew", padx=(0, 6), ipady=5, pady=(0, 6))
        _flat_btn(sett_in, "Browse", self._browse_maps, hover_bg=ACCENT2
                  ).grid(row=0, column=2, pady=(0, 6), sticky="w")

        tk.Label(sett_in, text="CookedPCConsole", font=FONT_LABEL,
                 bg=SURFACE2, fg=TEXT_MID
                 ).grid(row=1, column=0, sticky="w", padx=(0, 8))
        self.cooked_var = tk.StringVar(value=self.cfg.get("cooked_dir", DEFAULT_COOKED))
        tk.Entry(sett_in, textvariable=self.cooked_var, font=FONT_MONO,
                 bg=SURFACE, fg=TEXT, insertbackground=TEXT,
                 relief="flat", bd=0, highlightthickness=1,
                 highlightbackground=BORDER, highlightcolor=ACCENT
                 ).grid(row=1, column=1, sticky="ew", padx=(0, 6), ipady=5)
        _flat_btn(sett_in, "Browse", self._browse_cooked, hover_bg=ACCENT2
                  ).grid(row=1, column=2, sticky="w")
        _flat_btn(sett_in, "💾  Save", self._save_settings,
                  bg=ACCENT2, hover_bg=ACCENT
                  ).grid(row=1, column=3, padx=(10, 0), sticky="w")

        _sep(self, BORDER)

        # ── Status bar ─────────────────────────────────────────────────────────
        status = tk.Frame(self, bg=BG)
        status.pack(fill="x", padx=20, pady=(10, 4))

        tk.Label(status, text="NOW LOADED:", font=FONT_SMALL,
                 bg=BG, fg=TEXT_DIM).pack(side="left")
        self.active_lbl = tk.Label(status, text="—",
                                   font=("Trebuchet MS", 10, "bold"), bg=BG, fg=GREEN)
        self.active_lbl.pack(side="left", padx=8)

        self.check_lbl = tk.Label(status, text="",
                                  font=("Trebuchet MS", 13, "bold"), bg=BG, fg=GREEN)
        self.check_lbl.pack(side="left")

        self.restore_btn = _flat_btn(
            status, "↩  Use Standard Underpass",
            self._restore_original, bg=SURFACE2, fg=TEXT_MID, hover_bg=BORDER
        )
        self.restore_btn.pack(side="right")

        _sep(self, BORDER)

        # ── Main content: list (left) + preview (right) ─────────────────────────
        content = tk.Frame(self, bg=BG)
        content.pack(fill="both", expand=True, padx=20, pady=(0, 16))

        # ── Left: map list ───────────────────────────────────────────────────────
        left = tk.Frame(content, bg=BG)
        left.pack(side="left", fill="both", expand=True)

        list_hdr = tk.Frame(left, bg=BG)
        list_hdr.pack(fill="x", pady=(8, 0))

        tk.Label(list_hdr, text="CUSTOM MAPS", font=FONT_LABEL,
                 bg=BG, fg=TEXT_DIM).pack(side="left")

        ref = tk.Label(list_hdr, text="⟳ Refresh", font=FONT_SMALL,
                       bg=BG, fg=ACCENT, cursor="hand2")
        ref.pack(side="right")
        ref.bind("<Button-1>", lambda _: self._load_map_list())

        self.fav_only = tk.BooleanVar(value=False)
        tk.Checkbutton(list_hdr, text="★ Favourites only",
                       variable=self.fav_only, font=FONT_SMALL,
                       bg=BG, fg=TEXT_MID, selectcolor=SURFACE2,
                       activebackground=BG, activeforeground=GOLD,
                       command=self._load_map_list
                       ).pack(side="right", padx=14)

        list_outer = tk.Frame(left, bg=BORDER)
        list_outer.pack(fill="both", expand=True, pady=(6, 0))

        self.canvas = tk.Canvas(list_outer, bg=SURFACE, highlightthickness=0, bd=0)
        sb = tk.Scrollbar(list_outer, orient="vertical", command=self.canvas.yview,
                          bg=SURFACE2, troughcolor=SURFACE2, width=10)
        self.canvas.configure(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y")
        self.canvas.pack(side="left", fill="both", expand=True)

        self.map_frame = tk.Frame(self.canvas, bg=SURFACE)
        self._map_win = self.canvas.create_window((0, 0), window=self.map_frame, anchor="nw")

        self.map_frame.bind("<Configure>",
            lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all")))
        self.canvas.bind("<Configure>",
            lambda e: self.canvas.itemconfig(self._map_win, width=e.width))
        self.canvas.bind("<Enter>",
            lambda e: self.canvas.bind_all("<MouseWheel>", self._scroll_canvas))
        self.canvas.bind("<Leave>",
            lambda e: self.canvas.unbind_all("<MouseWheel>"))

        # ── Draggable sash ───────────────────────────────────────────────────────
        sash = tk.Frame(content, bg=BORDER, width=6, cursor="sb_h_double_arrow")
        sash.pack(side="left", fill="y", padx=(8, 0))

        # ── Right: preview panel ─────────────────────────────────────────────────
        self._preview_panel = tk.Frame(content, bg=SURFACE, width=PREVIEW_W)
        self._preview_panel.pack(side="right", fill="y", padx=(8, 0))
        self._preview_panel.pack_propagate(False)
        preview_panel = self._preview_panel

        def _sash_press(e):
            sash._start_x = e.x_root
            sash._start_w = self._preview_panel.winfo_width()
        def _sash_drag(e):
            delta = sash._start_x - e.x_root
            self._preview_panel.config(width=max(180, min(600, sash._start_w + delta)))
        sash.bind("<ButtonPress-1>", _sash_press)
        sash.bind("<B1-Motion>",     _sash_drag)
        sash.bind("<Enter>", lambda _: sash.config(bg=ACCENT))
        sash.bind("<Leave>", lambda _: sash.config(bg=BORDER))

        tk.Label(preview_panel, text="PREVIEW", font=FONT_LABEL,
                 bg=SURFACE, fg=TEXT_DIM, anchor="w"
                 ).pack(fill="x", padx=12, pady=(10, 6))
        tk.Frame(preview_panel, bg=BORDER, height=1).pack(fill="x")

        self._preview_body = tk.Frame(preview_panel, bg=SURFACE)
        self._preview_body.pack(fill="both", expand=True)

        self._render_preview_placeholder()

        self._load_map_list()
        self._refresh_active_label()

    # ── Update check ──────────────────────────────────────────────────────────
    def _check_for_updates(self):
        if getattr(self, "_upd_checking", False):
            return
        self._upd_checking = True
        self._upd_spinner_idx = 0
        self._upd_spinner_id  = None
        self._upd_spin()
        threading.Thread(target=self._do_check_updates, daemon=True).start()

    def _upd_spin(self):
        frame = _SPINNER_FRAMES[self._upd_spinner_idx % len(_SPINNER_FRAMES)]
        self._upd_btn.config(text=f"{frame}  Checking...", fg=GREEN)
        self._upd_spinner_idx += 1
        self._upd_spinner_id = self.after(120, self._upd_spin)

    def _upd_spin_stop(self):
        if self._upd_spinner_id:
            self.after_cancel(self._upd_spinner_id)
            self._upd_spinner_id = None
        self._upd_btn.config(text="🔄  Check for Updates", fg=TEXT_MID)
        self._upd_checking = False

    def _do_check_updates(self):
        try:
            req = urllib.request.Request(
                GITHUB_API_LATEST,
                headers={"User-Agent": _TEXTURES_UA,
                         "Accept": "application/vnd.github+json"})
            with urllib.request.urlopen(req, timeout=10) as resp:
                data = json.loads(resp.read().decode())
            tag = data.get("tag_name", "").lstrip("v")
            if not tag:
                raise RuntimeError("No release tag found.")
        except Exception as ex:
            self.after(0, lambda m=str(ex): self._upd_error(m))
            return

        def _finish(tag=tag):
            self._upd_spin_stop()
            current = tuple(int(x) for x in APP_VERSION.split("."))
            latest  = tuple(int(x) for x in tag.split("."))
            if latest <= current:
                messagebox.showinfo(APP_NAME,
                    f"You are on the latest version (v{APP_VERSION}).")
            else:
                if messagebox.askyesno(APP_NAME,
                        f"A new version is available: v{tag}\n"
                        f"You have: v{APP_VERSION}\n\n"
                        "Open the releases page to download the update?"):
                    webbrowser.open(GITHUB_RELEASES_PAGE)
        self.after(0, _finish)

    def _upd_error(self, msg):
        self._upd_spin_stop()
        messagebox.showerror(APP_NAME,
            f"Could not check for updates:\n{msg}\n\n"
            "Check your internet connection or visit the releases page manually.")

    # ── Workshop Textures ──────────────────────────────────────────────────────
    def _install_workshop_textures(self):
        cooked = self.cooked_var.get()
        if not os.path.isdir(cooked):
            messagebox.showerror(APP_NAME,
                f"CookedPCConsole folder not found:\n{cooked}\n\n"
                "Set it above and save first.")
            return
        threading.Thread(target=self._do_install_textures, args=(cooked,), daemon=True).start()

    def _do_install_textures(self, cooked):
        self.after(0, lambda: self._tex_btn.config(text="⏳  Downloading…", fg=GOLD))
        try:
            zip_path = self._download_textures_zip()
        except Exception as ex:
            msg = (f"Download failed:\n{ex}\n\n"
                   "You can download the zip manually from:\n"
                   f"{TEXTURES_MOD_PAGE}\n"
                   "then use 'Install from zip…' to finish.")
            self.after(0, lambda m=msg: self._tex_install_failed(m))
            return

        self.after(0, lambda: self._tex_btn.config(text="📦  Installing…", fg=GOLD))
        try:
            installed, skipped, all_names = self._extract_textures(zip_path, cooked)
        except Exception as ex:
            msg = f"Install failed:\n{ex}"
            self.after(0, lambda m=msg: self._tex_install_failed(m))
            return
        finally:
            try:
                os.remove(zip_path)
            except Exception:
                pass

        def _done(installed=installed, skipped=skipped, all_names=all_names):
            self.cfg["textures_installed"] = True
            self.cfg["texture_files"] = all_names
            save_config(self.cfg)
            self._tex_btn.config(text="🖼  Get Workshop Textures", fg=TEXT_MID)
            if self._tex_warn_visible:
                self.tex_warn_frame.pack_forget()
                self._tex_warn_visible = False
            if installed == 0 and skipped > 0:
                messagebox.showinfo(APP_NAME,
                    f"Workshop textures are already installed ({skipped} file(s) present).\n"
                    "Nothing was changed.")
            else:
                msg = f"Installed {installed} texture file(s) to CookedPCConsole."
                if skipped:
                    msg += f"\n{skipped} file(s) were already present and skipped."
                messagebox.showinfo(APP_NAME, msg)
        self.after(0, _done)

    def _download_textures_zip(self):
        req = urllib.request.Request(TEXTURES_DOWNLOAD_URL,
                                     headers={"User-Agent": _TEXTURES_UA,
                                              "Referer": TEXTURES_MOD_PAGE})
        tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".zip")
        tmp.close()
        with urllib.request.urlopen(req, timeout=60) as resp, open(tmp.name, "wb") as f:
            shutil.copyfileobj(resp, f)
        return tmp.name

    def _extract_textures(self, zip_path, cooked):
        installed = skipped = 0
        all_names = []
        with zipfile.ZipFile(zip_path) as zf:
            upk_entries = [n for n in zf.namelist()
                           if n.lower().endswith((".upk", ".udk"))
                           and not n.endswith("/")]
            if not upk_entries:
                raise RuntimeError("No .upk/.udk files found inside the downloaded zip.")
            for entry in upk_entries:
                fname = os.path.basename(entry)
                all_names.append(fname)
                dest  = os.path.join(cooked, fname)
                if os.path.exists(dest):
                    skipped += 1
                    continue
                data = zf.read(entry)
                with open(dest, "wb") as f:
                    f.write(data)
                installed += 1
        return installed, skipped, all_names

    def _tex_install_failed(self, msg):
        self._tex_btn.config(text="🖼  Get Workshop Textures", fg=TEXT_MID)
        result = messagebox.askokcancel(APP_NAME,
            msg + "\n\nOpen the mod page in browser?")
        if result:
            webbrowser.open(TEXTURES_MOD_PAGE)

    def _backup_path(self):
        maps_dir = self.maps_var.get()
        if not maps_dir:
            maps_dir = self.cfg.get("maps_dir", "")
        return os.path.join(maps_dir, BACKUP_SUBFOLDER, BACKUP_FILENAME)

    def _scroll_canvas(self, event):
        self.canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")

    # ── Startup ────────────────────────────────────────────────────────────────
    def _startup_checks(self):
        self._check_bakkesmod_mods()
        self._check_workshop_textures()

    def _check_bakkesmod_mods(self):
        mods_path = os.path.join(self.cooked_var.get(), "mods")
        has = os.path.isdir(mods_path) and _find_upk(mods_path) is not None
        if has and not self._warning_visible:
            self.warn_frame.pack(fill="x")
            self._warning_visible = True
        elif not has and self._warning_visible:
            self.warn_frame.pack_forget()
            self._warning_visible = False

    def _check_workshop_textures(self):
        installed = self.cfg.get("textures_installed", False)
        if installed:
            saved = self.cfg.get("texture_files", [])
            cooked = self.cooked_var.get()
            if not saved or all(os.path.exists(os.path.join(cooked, f)) for f in saved):
                return
        if not self._tex_warn_visible:
            self.tex_warn_frame.pack(fill="x")
            self._tex_warn_visible = True

    def _dismiss_tex_warning(self):
        self.cfg["textures_installed"] = True
        if "texture_files" not in self.cfg:
            self.cfg["texture_files"] = []
        save_config(self.cfg)
        self.tex_warn_frame.pack_forget()
        self._tex_warn_visible = False

    def _migrate_mods(self):
        mods_path = os.path.join(self.cooked_var.get(), "mods")
        maps_dir  = self.maps_var.get()
        if not os.path.isdir(mods_path):
            messagebox.showinfo(APP_NAME, "Mods folder not found.")
            return
        if not os.path.isdir(maps_dir):
            messagebox.showerror(APP_NAME, "Please set a valid Maps Folder first.")
            return
        if os.path.normcase(os.path.abspath(maps_dir)) == os.path.normcase(os.path.abspath(mods_path)):
            messagebox.showinfo(APP_NAME, "Maps Folder and mods folder are the same — nothing to do.")
            return
        moved, errors, delete_fails = 0, [], []
        for item in os.listdir(mods_path):
            src = os.path.join(mods_path, item)
            if os.path.isfile(src) and item.lower().endswith((".upk", ".udk")):
                dest_dir = os.path.join(maps_dir, os.path.splitext(item)[0])
                os.makedirs(dest_dir, exist_ok=True)
                try:
                    shutil.copyfile(src, os.path.join(dest_dir, item))
                    moved += 1
                    try:
                        os.remove(src)
                    except Exception:
                        delete_fails.append(item)
                except Exception as ex:
                    errors.append(str(ex))
            elif os.path.isdir(src) and _find_upk(src) is not None:
                dest_dir = os.path.join(maps_dir, item)
                try:
                    for dirpath, _, filenames in os.walk(src):
                        rel = os.path.relpath(dirpath, src)
                        target = os.path.join(dest_dir, rel) if rel != "." else dest_dir
                        os.makedirs(target, exist_ok=True)
                        for fname in filenames:
                            shutil.copyfile(os.path.join(dirpath, fname), os.path.join(target, fname))
                    moved += 1
                    try:
                        shutil.rmtree(src)
                    except Exception:
                        delete_fails.append(item)
                except Exception as ex:
                    errors.append(str(ex))
        msg = f"Copied {moved} map(s) to your Maps Folder."
        if delete_fails:
            msg += (f"\n\n{len(delete_fails)} original(s) could not be removed from the mods "
                    f"folder (access denied).\nDelete them manually, or right-click the app "
                    f"and run as Administrator:\n" + "\n".join(delete_fails[:5]))
        if errors:
            msg += (f"\n\n{len(errors)} error(s) — if these are access denied, "
                    f"right-click the app and run as Administrator:\n" + "\n".join(errors[:3]))
        messagebox.showinfo(APP_NAME, msg)
        self._load_map_list()
        self._check_bakkesmod_mods()

    # ── Directory browsers ─────────────────────────────────────────────────────
    def _browse_maps(self):
        d = filedialog.askdirectory(title="Select your Maps Folder")
        if d: self.maps_var.set(d)

    def _browse_cooked(self):
        d = filedialog.askdirectory(title="Select CookedPCConsole folder")
        if d:
            self.cooked_var.set(d)
            self._check_bakkesmod_mods()

    def _save_settings(self):
        self.cfg["maps_dir"]   = self.maps_var.get()
        self.cfg["cooked_dir"] = self.cooked_var.get()
        save_config(self.cfg)
        self._load_map_list()
        self._check_bakkesmod_mods()
        self._flash_check("Settings saved", color=ACCENT)

    # ── Auto-refresh on maps dir change ────────────────────────────────────────
    def _on_maps_dir_changed(self, *_):
        if self._refresh_after_id:
            self.after_cancel(self._refresh_after_id)
        self._refresh_after_id = self.after(600, self._load_map_list)

    # ── Map list ───────────────────────────────────────────────────────────────
    def _load_map_list(self):
        self._refresh_after_id = None
        for w in self.map_frame.winfo_children():
            w.destroy()
        self.canvas.yview_moveto(0)

        maps_dir = self.maps_var.get()
        if not maps_dir or not os.path.isdir(maps_dir):
            tk.Label(self.map_frame,
                     text="⚠  Set a valid Maps Folder above and save.",
                     font=FONT_BODY, bg=SURFACE, fg=TEXT_DIM, pady=30).pack()
            return

        maps = []
        zips = []
        for entry in sorted(os.listdir(maps_dir)):
            if entry == BACKUP_SUBFOLDER:
                continue
            fpath = os.path.join(maps_dir, entry)
            if os.path.isdir(fpath):
                upk = _find_upk(fpath)
                if upk:
                    maps.append((entry, fpath, upk))
            elif entry.lower().endswith((".upk", ".udk")):
                maps.append((os.path.splitext(entry)[0], maps_dir, fpath))
            elif entry.lower().endswith(".zip"):
                zips.append((os.path.splitext(entry)[0], fpath))

        favs = self.cfg.get("favourites", [])
        if self.fav_only.get():
            maps = [m for m in maps if m[0] in favs]
        maps.sort(key=lambda m: (0 if m[0] in favs else 1, m[0].lower()))

        if not maps and not zips:
            tk.Label(self.map_frame, text="No maps found in the selected folder.",
                     font=FONT_BODY, bg=SURFACE, fg=TEXT_DIM, pady=30).pack()
            return

        for i, (name, fpath, upk) in enumerate(maps):
            json_path = _find_map_json(fpath) if os.path.isdir(fpath) else None
            map_info  = _parse_map_json(json_path) if json_path else None
            self._build_row(i, name, fpath, upk, _find_preview_image(fpath), favs, map_info)

        for i, (name, zip_path) in enumerate(zips):
            self._build_zip_row(len(maps) + i, name, zip_path)

    def _build_row(self, idx, name, folder_path, upk, jfif, favs, map_info=None):
        is_fav    = name in favs
        is_active = name == self.cfg.get("active_map", "")
        row_bg    = "#181c27" if idx % 2 == 0 else SURFACE

        btn_bg    = ACCENT     if not is_active else "#1e3a1e"
        btn_fg    = TEXT       if not is_active else GREEN
        btn_hover = ACCENT2    if not is_active else "#2a4a2a"
        btn_text  = "▶  Load" if not is_active else "✔  Loaded"

        row   = tk.Frame(self.map_frame, bg=row_bg)
        row.pack(fill="x")
        inner = tk.Frame(row, bg=row_bg)
        inner.pack(fill="x", padx=14, pady=8)

        if is_active:
            tk.Frame(row, bg=GREEN, width=4).place(relx=0, rely=0, relheight=1, x=0)

        # ★ Favourite toggle
        star = tk.Label(inner, text="★", font=("Trebuchet MS", 14),
                        bg=row_bg, fg=GOLD if is_fav else BORDER, cursor="hand2")
        star.pack(side="left", padx=(4, 10))
        star.bind("<Button-1>", lambda _, n=name: self._toggle_fav(n))

        # Map name
        name_lbl = tk.Label(inner, text=name, font=FONT_MAP,
                             bg=row_bg, fg=GREEN if is_active else TEXT, anchor="w")
        name_lbl.pack(side="left", fill="x", expand=True)

        # .upk hint
        upk_lbl = tk.Label(inner, text=os.path.basename(upk), font=FONT_MONO,
                            bg=row_bg, fg=TEXT_DIM, anchor="e")
        upk_lbl.pack(side="left", padx=(0, 12))

        # ── Load button ──────────────────────────────────────────────────────────
        load_btn = tk.Button(
            inner, text=btn_text, font=FONT_BTN,
            bg=btn_bg, fg=btn_fg,
            relief="flat", cursor="hand2", padx=14, pady=5, bd=0,
            activebackground=btn_hover, activeforeground=TEXT,
            command=lambda n=name, fp=folder_path, u=upk, j=jfif, mi=map_info: self._load_map(n, fp, u, j, mi)
        )
        load_btn.pack(side="right")
        load_btn.bind("<Enter>", lambda e, b=load_btn, h=btn_hover: b.config(bg=h))
        load_btn.bind("<Leave>", lambda e, b=load_btn, bg=btn_bg:   b.config(bg=bg))

        # ── Row click → show preview (anywhere except load_btn) ──────────────────
        for widget in (row, inner, name_lbl, upk_lbl):
            widget.bind("<Button-1>", lambda e, n=name, j=jfif, mi=map_info: self._show_preview_panel(n, j, mi))

        # ── Row hover ────────────────────────────────────────────────────────────
        def on_enter(e, r=row, ri=inner, orig=row_bg):
            r.config(bg=SURFACE2); ri.config(bg=SURFACE2)
            for w in ri.winfo_children():
                if w is not load_btn:
                    try: w.config(bg=SURFACE2)
                    except Exception: pass

        def on_leave(e, r=row, ri=inner, orig=row_bg):
            r.config(bg=orig); ri.config(bg=orig)
            for w in ri.winfo_children():
                if w is not load_btn:
                    try: w.config(bg=orig)
                    except Exception: pass

        row.bind("<Enter>",   on_enter)
        row.bind("<Leave>",   on_leave)
        inner.bind("<Enter>", on_enter)
        inner.bind("<Leave>", on_leave)

        _sep(self.map_frame, BORDER, 1)

    def _build_zip_row(self, idx, name, zip_path):
        row_bg = "#181c27" if idx % 2 == 0 else SURFACE
        row   = tk.Frame(self.map_frame, bg=row_bg)
        row.pack(fill="x")
        inner = tk.Frame(row, bg=row_bg)
        inner.pack(fill="x", padx=14, pady=8)

        tk.Label(inner, text="📦", font=("Trebuchet MS", 13),
                 bg=row_bg).pack(side="left", padx=(4, 10))
        tk.Label(inner, text=name, font=FONT_MAP,
                 bg=row_bg, fg=TEXT_MID, anchor="w").pack(side="left", fill="x", expand=True)
        tk.Label(inner, text=".zip", font=FONT_MONO,
                 bg=row_bg, fg=TEXT_DIM).pack(side="left", padx=(0, 12))

        ext_btn = tk.Button(
            inner, text="⬇  Extract", font=FONT_BTN,
            bg=SURFACE2, fg=TEXT_MID,
            relief="flat", cursor="hand2", padx=14, pady=5, bd=0,
            activebackground=BORDER, activeforeground=TEXT,
            command=lambda zp=zip_path: self._extract_zip(zp)
        )
        ext_btn.pack(side="right")
        ext_btn.bind("<Enter>", lambda _, b=ext_btn: b.config(bg=BORDER))
        ext_btn.bind("<Leave>", lambda _, b=ext_btn: b.config(bg=SURFACE2))

        _sep(self.map_frame, BORDER, 1)

    def _extract_zip(self, zip_path):
        maps_dir = self.maps_var.get()

        def do_extract():
            try:
                with zipfile.ZipFile(zip_path) as zf:
                    top_levels = {n.split("/")[0] for n in zf.namelist() if n}
                    if len(top_levels) == 1 and not any(
                        n.replace(next(iter(top_levels)), "").strip("/") == "" and not n.endswith("/")
                        for n in zf.namelist()
                    ):
                        # Single top-level folder — extract directly into maps_dir
                        zf.extractall(maps_dir)
                    else:
                        # Files at root — extract into a named subfolder
                        dest = os.path.join(maps_dir, os.path.splitext(os.path.basename(zip_path))[0])
                        os.makedirs(dest, exist_ok=True)
                        zf.extractall(dest)
                os.remove(zip_path)
                self.after(0, self._load_map_list)
            except PermissionError:
                self.after(0, lambda: messagebox.showerror(
                    APP_NAME,
                    "Permission denied while extracting.\n\n"
                    "The Maps Folder may require administrator access.\n"
                    "Try moving your Maps Folder to somewhere like Documents or Desktop, "
                    "or re-run this app as Administrator."))
            except Exception as ex:
                self.after(0, lambda: messagebox.showerror(APP_NAME, f"Extract failed:\n{ex}"))

        threading.Thread(target=do_extract, daemon=True).start()

    # ── Load map ───────────────────────────────────────────────────────────────
    def _load_map(self, name, folder_path, upk_path, jfif_path=None, map_info=None):
        cooked = self.cooked_var.get()
        if not os.path.isdir(cooked):
            messagebox.showerror(APP_NAME, f"CookedPCConsole folder not found:\n{cooked}")
            return
        dest   = os.path.join(cooked, UPK_FILENAME)
        backup = self._backup_path()

        def do_load():
            try:
                if not os.path.exists(backup) and os.path.exists(dest):
                    os.makedirs(os.path.dirname(backup), exist_ok=True)
                    shutil.copy2(dest, backup)
                shutil.copy2(upk_path, dest)
                self.cfg["active_map"] = name
                save_config(self.cfg)
                self.after(0, lambda: self._on_load_success(name, jfif_path, map_info))
            except PermissionError:
                self.after(0, lambda: messagebox.showerror(
                    APP_NAME, "Permission denied.\nTry running the app as Administrator."))
            except Exception as ex:
                self.after(0, lambda: messagebox.showerror(APP_NAME, f"Error:\n{ex}"))

        threading.Thread(target=do_load, daemon=True).start()

    def _on_load_success(self, name, jfif_path=None, map_info=None):
        self._refresh_active_label()
        self._load_map_list()
        self._animate_check()
        self._show_preview_panel(name, jfif_path, map_info)

    def _animate_check(self):
        if self._check_anim_id:
            self.after_cancel(self._check_anim_id)
        self.check_lbl.config(text=" ✔", fg=GREEN)
        schedule = [
            (300,  lambda: self.check_lbl.config(fg="#7eeaaa")),
            (600,  lambda: self.check_lbl.config(fg=GREEN)),
            (900,  lambda: self.check_lbl.config(fg="#7eeaaa")),
            (1200, lambda: self.check_lbl.config(fg=GREEN)),
            (2800, lambda: self.check_lbl.config(fg=TEXT_DIM)),
            (3600, lambda: self.check_lbl.config(text="")),
        ]
        for delay, fn in schedule:
            self._check_anim_id = self.after(delay, fn)

    def _flash_check(self, msg="", color=GREEN):
        self.check_lbl.config(text=f" ✔ {msg}", fg=color)
        self.after(2200, lambda: self.check_lbl.config(text=""))

    # ── In-app preview panel ───────────────────────────────────────────────────
    def _render_preview_placeholder(self):
        for w in self._preview_body.winfo_children():
            w.destroy()
        tk.Label(self._preview_body,
                 text="Click a map\nto preview",
                 font=FONT_BODY, bg=SURFACE, fg=TEXT_DIM,
                 justify="center").pack(expand=True)

    def _show_preview_panel(self, name, jfif_path, map_info=None):
        for w in self._preview_body.winfo_children():
            w.destroy()

        if jfif_path and os.path.exists(jfif_path):
            try:
                img = Image.open(jfif_path)
                img.thumbnail((PREVIEW_W - 20, 200), Image.LANCZOS)
                photo = ImageTk.PhotoImage(img)
                img_lbl = tk.Label(self._preview_body, image=photo, bg=SURFACE)
                img_lbl.image = photo
                img_lbl.pack(pady=(14, 8))
            except Exception:
                tk.Label(self._preview_body, text="(no preview)",
                         font=FONT_SMALL, bg=SURFACE, fg=TEXT_DIM).pack(pady=(20, 6))
        else:
            tk.Label(self._preview_body, text="(no preview)",
                     font=FONT_SMALL, bg=SURFACE, fg=TEXT_DIM).pack(pady=(20, 6))

        title = map_info.get("Title", name) if map_info else name
        tk.Label(self._preview_body, text=title, font=FONT_MAP,
                 bg=SURFACE, fg=ACCENT, wraplength=PREVIEW_W - 24,
                 justify="center").pack(padx=12, pady=(0, 4))

        if map_info:
            author = map_info.get("Author", "")
            if author:
                tk.Label(self._preview_body, text=f"by {author}", font=FONT_SMALL,
                         bg=SURFACE, fg=TEXT_MID, wraplength=PREVIEW_W - 24,
                         justify="center").pack(padx=12, pady=(0, 8))

            desc = map_info.get("Description", "").strip()
            if desc:
                tk.Frame(self._preview_body, bg=BORDER, height=1).pack(fill="x", padx=12, pady=(0, 6))
                tk.Label(self._preview_body, text="Description", font=FONT_LABEL,
                         bg=ACCENT2, fg=TEXT, anchor="w", padx=8, pady=4
                         ).pack(fill="x", padx=8, pady=(0, 4))
                desc_frame = tk.Frame(self._preview_body, bg=SURFACE)
                desc_frame.pack(fill="both", expand=True, padx=8, pady=(0, 8))
                sb = tk.Scrollbar(desc_frame, orient="vertical",
                                  bg=SURFACE2, troughcolor=SURFACE2, width=8)
                txt = tk.Text(desc_frame, wrap="word", font=FONT_SMALL,
                              bg=SURFACE2, fg=TEXT_MID, relief="flat",
                              bd=0, highlightthickness=0, padx=6, pady=6,
                              cursor="arrow", yscrollcommand=sb.set)
                sb.config(command=txt.yview)
                sb.pack(side="right", fill="y")
                txt.pack(side="left", fill="both", expand=True)
                txt.insert("1.0", desc)
                txt.config(state="disabled")

    # ── Restore original ───────────────────────────────────────────────────────
    def _restore_original(self):
        cooked = self.cooked_var.get()
        backup = self._backup_path()
        dest   = os.path.join(cooked, UPK_FILENAME)
        if not os.path.exists(backup):
            messagebox.showinfo(APP_NAME,
                "No backup found — the original has never been replaced by this app.")
            return
        try:
            shutil.copy2(backup, dest)
            self.cfg["active_map"] = ""
            save_config(self.cfg)
            self._refresh_active_label()
            self._load_map_list()
            self._flash_check("Standard Underpass restored", color=ACCENT)
            self._render_preview_placeholder()
        except PermissionError:
            messagebox.showerror(APP_NAME, "Permission denied. Try running as Administrator.")
        except Exception as ex:
            messagebox.showerror(APP_NAME, f"Error restoring:\n{ex}")

    # ── Favourites ─────────────────────────────────────────────────────────────
    def _toggle_fav(self, name):
        favs = self.cfg.setdefault("favourites", [])
        if name in favs: favs.remove(name)
        else:            favs.append(name)
        save_config(self.cfg)
        self._load_map_list()

    # ── Active map label + restore button state ─────────────────────────────────
    def _refresh_active_label(self):
        active     = self.cfg.get("active_map", "")
        has_backup = os.path.exists(self._backup_path())
        self.active_lbl.config(
            text=active if active else "Standard Underpass",
            fg=GREEN if active else TEXT_DIM
        )
        self.restore_btn.config(
            state="normal" if has_backup else "disabled",
            fg=TEXT_MID    if has_backup else TEXT_DIM
        )


# ── Entry point ────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    app = App()
    app.mainloop()
