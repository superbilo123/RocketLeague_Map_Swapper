import tkinter as tk
from tkinter import filedialog, messagebox
import json
import os
import shutil
import threading
import webbrowser
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
_CONFIG_DIR     = os.path.join(os.environ.get("APPDATA", os.path.expanduser("~")), "RLmapswapper-config")
os.makedirs(_CONFIG_DIR, exist_ok=True)
CONFIG_FILE     = os.path.join(_CONFIG_DIR, "config.json")
MAPS_WEBSITE    = "https://bakkesplugins.com/maps"
UPK_FILENAME    = "Labs_Underpass_P.upk"
BACKUP_FILENAME = "Labs_Underpass_P_ORIGINAL_BACKUP.upk"

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
    for f in os.listdir(folder_path):
        if f.lower().endswith(".upk"):
            return os.path.join(folder_path, f)
    return None

def _find_jfif(folder_path):
    for f in os.listdir(folder_path):
        if f.lower().endswith(".jfif"):
            return os.path.join(folder_path, f)
    return None

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

        self._check_anim_id   = None
        self._warning_visible = False
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

        _sep(self, BORDER, 2)

        # ── BakkesMod warning banner (hidden until needed) ──────────────────────
        self.warn_frame = tk.Frame(self, bg="#2a1a0e")
        tk.Label(self.warn_frame,
                 text="⚠️  BakkesMod mods folder detected — this may block custom maps.",
                 font=FONT_BODY, bg="#2a1a0e", fg="#f5a742", anchor="w"
                 ).pack(side="left", padx=16, pady=10)
        tk.Button(self.warn_frame, text="Migrate to Maps Folder →",
                  font=FONT_BTN, bg="#4a2e10", fg=GOLD,
                  relief="flat", cursor="hand2", padx=10, pady=4,
                  activebackground="#6a3e18", activeforeground=GOLD,
                  command=self._migrate_mods
                  ).pack(side="right", padx=12, pady=8)

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
        self.canvas.bind_all("<MouseWheel>",
            lambda e: self.canvas.yview_scroll(int(-1*(e.delta/120)), "units"))

        # ── Vertical divider ─────────────────────────────────────────────────────
        tk.Frame(content, bg=BORDER, width=1).pack(side="left", fill="y", padx=(10, 0))

        # ── Right: preview panel ─────────────────────────────────────────────────
        preview_panel = tk.Frame(content, bg=SURFACE, width=PREVIEW_W)
        preview_panel.pack(side="right", fill="y", padx=(10, 0))
        preview_panel.pack_propagate(False)

        tk.Label(preview_panel, text="PREVIEW", font=FONT_LABEL,
                 bg=SURFACE, fg=TEXT_DIM, anchor="w"
                 ).pack(fill="x", padx=12, pady=(10, 6))
        tk.Frame(preview_panel, bg=BORDER, height=1).pack(fill="x")

        self._preview_body = tk.Frame(preview_panel, bg=SURFACE)
        self._preview_body.pack(fill="both", expand=True)

        self._render_preview_placeholder()

        self._load_map_list()
        self._refresh_active_label()

    # ── Startup ────────────────────────────────────────────────────────────────
    def _startup_checks(self):
        self._check_bakkesmod_mods()

    def _check_bakkesmod_mods(self):
        mods_path = os.path.join(self.cooked_var.get(), "mods")
        has = (os.path.isdir(mods_path) and
               any(f.lower().endswith(".upk") for f in os.listdir(mods_path)))
        if has and not self._warning_visible:
            self.warn_frame.pack(fill="x", after=self.winfo_children()[1])
            self._warning_visible = True
        elif not has and self._warning_visible:
            self.warn_frame.pack_forget()
            self._warning_visible = False

    def _migrate_mods(self):
        mods_path = os.path.join(self.cooked_var.get(), "mods")
        maps_dir  = self.maps_var.get()
        if not os.path.isdir(mods_path):
            messagebox.showinfo(APP_NAME, "Mods folder not found.")
            return
        if not os.path.isdir(maps_dir):
            messagebox.showerror(APP_NAME, "Please set a valid Maps Folder first.")
            return
        moved, errors = 0, []
        for item in os.listdir(mods_path):
            if item.lower().endswith(".upk"):
                src  = os.path.join(mods_path, item)
                dest = os.path.join(maps_dir, os.path.splitext(item)[0])
                os.makedirs(dest, exist_ok=True)
                try:
                    shutil.move(src, os.path.join(dest, item))
                    moved += 1
                except Exception as ex:
                    errors.append(str(ex))
        msg = f"Moved {moved} map(s) to your Maps Folder."
        if errors:
            msg += f"\n\n{len(errors)} error(s):\n" + "\n".join(errors[:3])
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

        maps_dir = self.maps_var.get()
        if not maps_dir or not os.path.isdir(maps_dir):
            tk.Label(self.map_frame,
                     text="⚠  Set a valid Maps Folder above and save.",
                     font=FONT_BODY, bg=SURFACE, fg=TEXT_DIM, pady=30).pack()
            return

        maps = []
        for folder in sorted(os.listdir(maps_dir)):
            fpath = os.path.join(maps_dir, folder)
            if os.path.isdir(fpath):
                upk = _find_upk(fpath)
                if upk:
                    maps.append((folder, fpath, upk))

        favs = self.cfg.get("favourites", [])
        if self.fav_only.get():
            maps = [m for m in maps if m[0] in favs]
        maps.sort(key=lambda m: (0 if m[0] in favs else 1, m[0].lower()))

        if not maps:
            tk.Label(self.map_frame, text="No maps found in the selected folder.",
                     font=FONT_BODY, bg=SURFACE, fg=TEXT_DIM, pady=30).pack()
            return

        for i, (name, fpath, upk) in enumerate(maps):
            self._build_row(i, name, fpath, upk, _find_jfif(fpath), favs)

    def _build_row(self, idx, name, folder_path, upk, jfif, favs):
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
            command=lambda n=name, fp=folder_path, u=upk, j=jfif: self._load_map(n, fp, u, j)
        )
        load_btn.pack(side="right")
        load_btn.bind("<Enter>", lambda e, b=load_btn, h=btn_hover: b.config(bg=h))
        load_btn.bind("<Leave>", lambda e, b=load_btn, bg=btn_bg:   b.config(bg=bg))

        # ── Row click → show preview (anywhere except load_btn) ──────────────────
        for widget in (row, inner, name_lbl, upk_lbl):
            widget.bind("<Button-1>", lambda e, n=name, j=jfif: self._show_preview_panel(n, j))

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

    # ── Load map ───────────────────────────────────────────────────────────────
    def _load_map(self, name, folder_path, upk_path, jfif_path=None):
        cooked = self.cooked_var.get()
        if not os.path.isdir(cooked):
            messagebox.showerror(APP_NAME, f"CookedPCConsole folder not found:\n{cooked}")
            return
        dest   = os.path.join(cooked, UPK_FILENAME)
        backup = os.path.join(cooked, BACKUP_FILENAME)

        def do_load():
            try:
                if not os.path.exists(backup) and os.path.exists(dest):
                    shutil.copy2(dest, backup)
                shutil.copy2(upk_path, dest)
                self.cfg["active_map"] = name
                save_config(self.cfg)
                self.after(0, lambda: self._on_load_success(name, jfif_path))
            except PermissionError:
                self.after(0, lambda: messagebox.showerror(
                    APP_NAME, "Permission denied.\nTry running the app as Administrator."))
            except Exception as ex:
                self.after(0, lambda: messagebox.showerror(APP_NAME, f"Error:\n{ex}"))

        threading.Thread(target=do_load, daemon=True).start()

    def _on_load_success(self, name, jfif_path=None):
        self._refresh_active_label()
        self._load_map_list()
        self._animate_check()
        self._show_preview_panel(name, jfif_path)

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

    def _show_preview_panel(self, name, jfif_path):
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

        tk.Label(self._preview_body, text=name, font=FONT_MAP,
                 bg=SURFACE, fg=ACCENT, wraplength=PREVIEW_W - 24,
                 justify="center").pack(padx=12, pady=(0, 12))

    # ── Restore original ───────────────────────────────────────────────────────
    def _restore_original(self):
        cooked = self.cooked_var.get()
        backup = os.path.join(cooked, BACKUP_FILENAME)
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
        has_backup = os.path.exists(os.path.join(self.cooked_var.get(), BACKUP_FILENAME))
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
