import time
import threading
import ctypes
import json
import customtkinter as ctk
from pynput import mouse, keyboard
from tkinter import filedialog, messagebox
import queue

APP_BG = "#1a1a1a"
PANEL_BG = "#242424"
BORDER_COLOR = "#2d2d2d"
ACCENT_BLUE = "#1f6aa5"
ACCENT_GREEN = "#2e7d32"
ACCENT_RED = "#c62828"
TEXT_MAIN = "#ffffff"
TEXT_MUTED = "#9e9e9e"

ctk.set_appearance_mode("Dark")

# ── Windows EXE detection ──────────────────────────────────────────────────────
GetForegroundWindow      = ctypes.windll.user32.GetForegroundWindow
GetWindowThreadProcessId = ctypes.windll.user32.GetWindowThreadProcessId
OpenProcess              = ctypes.windll.kernel32.OpenProcess
CloseHandle              = ctypes.windll.kernel32.CloseHandle
QueryFullProcessImageNameW = ctypes.windll.kernel32.QueryFullProcessImageNameW
EnumWindows              = ctypes.windll.user32.EnumWindows
IsWindowVisible          = ctypes.windll.user32.IsWindowVisible
GetWindowTextW           = ctypes.windll.user32.GetWindowTextW

PROCESS_QUERY_INFORMATION = 0x0400
PROCESS_VM_READ           = 0x0010

def get_exe_from_hwnd(hwnd):
    pid = ctypes.c_ulong()
    GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
    handle = OpenProcess(PROCESS_QUERY_INFORMATION | PROCESS_VM_READ, False, pid.value)
    if not handle: return ""
    buf  = ctypes.create_unicode_buffer(1024)
    size = ctypes.c_ulong(1024)
    ok   = QueryFullProcessImageNameW(handle, 0, buf, ctypes.byref(size))
    CloseHandle(handle)
    return buf.value.split("\\")[-1].split("/")[-1].lower() if ok else ""

def get_active_window_exe():
    hwnd = GetForegroundWindow()
    return get_exe_from_hwnd(hwnd) if hwnd else ""

def get_all_visible_window_exes():
    exes = set()
    def cb(hwnd, _):
        if IsWindowVisible(hwnd):
            tb = ctypes.create_unicode_buffer(512)
            GetWindowTextW(hwnd, tb, 512)
            if tb.value.strip():
                e = get_exe_from_hwnd(hwnd)
                if e and not e.startswith("macro_app"): exes.add(e)
        return True
    EnumWindows(ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_long, ctypes.c_long)(cb), 0)
    return sorted(exes) if exes else ["notepad.exe"]

# ── SendInput – exact same structs as the proven working old code ──────────────
SendInput = ctypes.windll.user32.SendInput
PUL = ctypes.POINTER(ctypes.c_ulong)

class KeyBdInput(ctypes.Structure):
    _fields_ = [
        ("wVk",         ctypes.c_ushort),
        ("wScan",       ctypes.c_ushort),
        ("dwFlags",     ctypes.c_ulong),
        ("time",        ctypes.c_ulong),
        ("dwExtraInfo", PUL),
    ]

class HardwareInput(ctypes.Structure):
    _fields_ = [("uMsg", ctypes.c_ulong), ("wParamL", ctypes.c_short), ("wParamH", ctypes.c_ushort)]

class MouseInput(ctypes.Structure):
    _fields_ = [
        ("dx",          ctypes.c_long),
        ("dy",          ctypes.c_long),
        ("mouseData",   ctypes.c_ulong),
        ("dwFlags",     ctypes.c_ulong),
        ("time",        ctypes.c_ulong),
        ("dwExtraInfo", PUL),
    ]

class Input_I(ctypes.Union):
    _fields_ = [("ki", KeyBdInput), ("mi", MouseInput), ("hi", HardwareInput)]

class Input(ctypes.Structure):
    _fields_ = [("type", ctypes.c_ulong), ("ii", Input_I)]

# VK → PS/2 scan-code (uppercase AND lowercase letters both map here)
VK_TO_SCAN = {
    # Uppercase A-Z
    0x41:0x1E,0x42:0x30,0x43:0x2E,0x44:0x20,0x45:0x12,0x46:0x21,0x47:0x22,0x48:0x23,
    0x49:0x17,0x4A:0x24,0x4B:0x25,0x4C:0x26,0x4D:0x32,0x4E:0x31,0x4F:0x18,0x50:0x19,
    0x51:0x10,0x52:0x13,0x53:0x1F,0x54:0x14,0x55:0x16,0x56:0x2F,0x57:0x11,0x58:0x2D,
    0x59:0x15,0x5A:0x2C,
    # Lowercase a-z  (pynput sometimes gives these instead of uppercase VKs)
    0x61:0x1E,0x62:0x30,0x63:0x2E,0x64:0x20,0x65:0x12,0x66:0x21,0x67:0x22,0x68:0x23,
    0x69:0x17,0x6A:0x24,0x6B:0x25,0x6C:0x26,0x6D:0x32,0x6E:0x31,0x6F:0x18,0x70:0x19,
    0x71:0x10,0x72:0x13,0x73:0x1F,0x74:0x14,0x75:0x16,0x76:0x2F,0x77:0x11,0x78:0x2D,
    0x79:0x15,0x7A:0x2C,
    # Digits
    0x30:0x0B,0x31:0x02,0x32:0x03,0x33:0x04,0x34:0x05,0x35:0x06,
    0x36:0x07,0x37:0x08,0x38:0x09,0x39:0x0A,
    # System / navigation
    0x20:0x39,0x0D:0x1C,0x1B:0x01,0x09:0x0F,   # Space, Enter, Esc, Tab
    0x08:0x0E,0x10:0x2A,0xA0:0x2A,0xA1:0x36,   # Backspace, Shift L/R
    0x11:0x1D,0xA2:0x1D,0xA3:0x1D,             # Ctrl variants
    0x12:0x38,0xA4:0x38,0xA5:0x38,             # Alt variants
    0x14:0x3A,                                   # CapsLock
    0x25:0x4B,0x26:0x48,0x27:0x4D,0x28:0x50,   # Arrow keys
    0x24:0x47,0x21:0x49,0x22:0x51,0x23:0x4F,   # Home/PgUp/PgDn/End
    0x2D:0x52,0x2E:0x53,                        # Insert/Delete
    112:0x3B,113:0x3C,114:0x3D,115:0x3E,       # F1-F4
    116:0x3F,117:0x40,118:0x41,119:0x42,       # F5-F8
    120:0x43,121:0x44,122:0x57,123:0x58,       # F9-F12
}

EXTENDED_KEYS = {0x25,0x26,0x27,0x28,0x0D,0x24,0x21,0x22,0x23,0x2D,0x2E}

SCAN_TO_NAME = {
    0x1E:"A",0x30:"B",0x2E:"C",0x20:"D",0x12:"E",0x21:"F",0x22:"G",0x23:"H",
    0x17:"I",0x24:"J",0x25:"K",0x26:"L",0x32:"M",0x31:"N",0x18:"O",0x19:"P",
    0x10:"Q",0x13:"R",0x1F:"S",0x14:"T",0x16:"U",0x2F:"V",0x11:"W",0x2D:"X",
    0x15:"Y",0x2C:"Z",0x02:"1",0x03:"2",0x04:"3",0x05:"4",0x06:"5",
    0x07:"6",0x08:"7",0x09:"8",0x0A:"9",0x0B:"0",
    0x39:"SPACE",0x1C:"ENTER",0x01:"ESC",0x0F:"TAB",0x0E:"BACKSPACE",
    0x2A:"SHIFT",0x36:"R_SHIFT",0x1D:"CTRL",0x38:"ALT",0x3A:"CAPS_LOCK",
    0x4B:"LEFT",0x48:"UP",0x4D:"RIGHT",0x50:"DOWN",
    0x47:"HOME",0x49:"PAGE_UP",0x51:"PAGE_DOWN",0x4F:"END",
    0x52:"INSERT",0x53:"DELETE",
    0x3B:"F1",0x3C:"F2",0x3D:"F3",0x3E:"F4",0x3F:"F5",0x40:"F6",
    0x41:"F7",0x42:"F8",0x43:"F9",0x44:"F10",0x57:"F11",0x58:"F12",
}

def send_hardware_input(vk_code, is_release=False):
    """Proven working SendInput implementation (identical structure to old code)."""
    scan_code = VK_TO_SCAN.get(vk_code, 0)
    if scan_code == 0: return False
    flags = 0x0008                              # KEYEVENTF_SCANCODE
    if vk_code in EXTENDED_KEYS: flags |= 0x0001  # KEYEVENTF_EXTENDEDKEY
    if is_release:               flags |= 0x0002  # KEYEVENTF_KEYUP
    extra   = ctypes.c_ulong(0)
    ii_     = Input_I()
    ii_.ki  = KeyBdInput(0, scan_code, flags, 0, ctypes.pointer(extra))
    command = Input(ctypes.c_ulong(1), ii_)
    SendInput(1, ctypes.pointer(command), ctypes.sizeof(command))
    return True


class MacroApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("Python Macro Editor Pro")
        self.geometry("1060x720")
        self.configure(fg_color=APP_BG)

        self.macro_actions        = []
        self.is_recording         = False
        self.is_playing           = False
        self.start_time           = 0
        self.selected_record_hotkey = "HOME"
        self.selected_play_hotkey   = "PAGE_UP"
        self.listening_for_new_hotkey = None
        self.listening_for_manual_action = False
        self.loop_mode            = "One Time"
        self.currently_pressed_keys = set()
        self.ui_queue             = queue.Queue()
        self.action_ui_rows       = []
        self.selected_action_index = None
        self.mouse_listener       = None
        self.keyboard_listener    = None
        self.manual_mouse_listener    = None
        self.manual_keyboard_listener = None
        self.dragged_index  = None
        self.drag_y_start   = 0

        self.create_widgets()
        self.start_global_hotkey_listeners()
        self.check_ui_queue()

    # ── UI Construction ────────────────────────────────────────────────────────
    def create_widgets(self):
        # LEFT PANEL
        self.left_panel = ctk.CTkFrame(self, width=420, fg_color=PANEL_BG, border_color=BORDER_COLOR, border_width=1, corner_radius=12)
        self.left_panel.pack(side="left", fill="y", padx=20, pady=20)
        self.left_panel.pack_propagate(False)

        ctk.CTkLabel(self.left_panel, text="Macro Controls", font=ctk.CTkFont(family="Segoe UI", size=24, weight="bold"), text_color=TEXT_MAIN).pack(pady=(12, 2))
        self.status_label = ctk.CTkLabel(self.left_panel, text="ENGINE IDLE", font=ctk.CTkFont(family="Segoe UI", size=12, weight="bold"), text_color=TEXT_MUTED)
        self.status_label.pack(pady=(0, 6))

        action_card = ctk.CTkFrame(self.left_panel, fg_color="transparent")
        action_card.pack(fill="x", padx=20, pady=(0, 8))
        self.play_btn = ctk.CTkButton(action_card, text=f"▶ Run Sequence ({self.selected_play_hotkey})", fg_color=ACCENT_GREEN, height=38, command=self.toggle_playback)
        self.play_btn.pack(fill="x", pady=4)
        self.record_btn = ctk.CTkButton(action_card, text=f"🔴 Start Record ({self.selected_record_hotkey})", fg_color=ACCENT_RED, height=38, command=self.toggle_recording)
        self.record_btn.pack(fill="x", pady=4)

        cfg = ctk.CTkFrame(self.left_panel, fg_color="transparent")
        cfg.pack(fill="x", padx=20, pady=8)
        ctk.CTkLabel(cfg, text="Record/Stop Hotkey:", text_color=TEXT_MUTED, anchor="w").grid(row=0, column=0, padx=2, pady=6, sticky="w")
        self.rec_hk_btn = ctk.CTkButton(cfg, text=self.selected_record_hotkey, width=120, height=26, fg_color="#2d2f34", command=lambda: self.start_listening_for_hotkey('record'))
        self.rec_hk_btn.grid(row=0, column=1, padx=2, pady=6, sticky="e")
        ctk.CTkLabel(cfg, text="Play/Stop Hotkey:", text_color=TEXT_MUTED, anchor="w").grid(row=1, column=0, padx=2, pady=6, sticky="w")
        self.play_hk_btn = ctk.CTkButton(cfg, text=self.selected_play_hotkey, width=120, height=26, fg_color="#2d2f34", command=lambda: self.start_listening_for_hotkey('play'))
        self.play_hk_btn.grid(row=1, column=1, padx=2, pady=6, sticky="e")
        ctk.CTkLabel(cfg, text="Playback Mode:", text_color=TEXT_MUTED, anchor="w").grid(row=2, column=0, padx=2, pady=8, sticky="nw")

        self.loop_var = ctk.StringVar(value="One Time")
        rf = ctk.CTkFrame(cfg, fg_color="transparent")
        rf.grid(row=2, column=1, sticky="ne", padx=2, pady=2)
        ctk.CTkRadioButton(rf, text="One Time",     variable=self.loop_var, value="One Time", command=self.change_loop_mode).pack(anchor="w", pady=2)
        ctk.CTkRadioButton(rf, text="Infinite Loop",variable=self.loop_var, value="Loop",     command=self.change_loop_mode).pack(anchor="w", pady=2)
        ctk.CTkRadioButton(rf, text="Loop Count",   variable=self.loop_var, value="Count",    command=self.change_loop_mode).pack(anchor="w", pady=2)

        self.dynamic_loop_inputs = ctk.CTkFrame(self.left_panel, fg_color="transparent")
        self.dynamic_loop_inputs.pack(fill="x", padx=25, pady=2)

        # Process Shield
        exe_frame = ctk.CTkFrame(self.left_panel, fg_color="#1c1c1c", border_color=BORDER_COLOR, border_width=1, corner_radius=8)
        exe_frame.pack(fill="x", padx=20, pady=6)
        ctk.CTkLabel(exe_frame, text="PROCESS ENVIRONMENT SHIELD", font=ctk.CTkFont(size=11, weight="bold"), text_color=ACCENT_BLUE).pack(fill="x", padx=12, pady=(8, 2))
        self.exe_switch_var = ctk.StringVar(value="off")
        ctk.CTkSwitch(exe_frame, text="Enforce Active Window Lock", variable=self.exe_switch_var, onvalue="on", offvalue="off", command=self.toggle_exe_lock).pack(anchor="w", padx=12, pady=6)
        self.exe_entry_frame = ctk.CTkFrame(exe_frame, fg_color="transparent")
        self.exe_name_entry  = ctk.CTkComboBox(self.exe_entry_frame, values=[], height=26)
        self.exe_name_entry.pack(side="left", fill="x", expand=True, padx=(5,4))
        self.exe_detect_btn  = ctk.CTkButton(self.exe_entry_frame, text="Sync", width=55, height=26, fg_color=ACCENT_GREEN, command=self.refresh_running_exes_list)
        self.exe_detect_btn.pack(side="right", padx=5)

        # Import / Export
        ff = ctk.CTkFrame(self.left_panel, fg_color="transparent")
        ff.pack(fill="x", padx=20, pady=(8,4))
        ctk.CTkButton(ff, text="💾 Export", fg_color="#2b2d31", hover_color="#3d4047", corner_radius=6, command=self.export_macro, height=32).pack(side="left", expand=True, fill="x", padx=(0,4))
        ctk.CTkButton(ff, text="📂 Import", fg_color="#2b2d31", hover_color="#3d4047", corner_radius=6, command=self.import_macro, height=32).pack(side="right", expand=True, fill="x", padx=(4,0))

        self.info_label = ctk.CTkLabel(self.left_panel, text="Actions Logged: 0", font=ctk.CTkFont(size=11), text_color=TEXT_MUTED)
        self.info_label.pack(side="bottom", pady=2)

        # RIGHT PANEL – timeline
        rp = ctk.CTkFrame(self, fg_color=PANEL_BG, border_color=BORDER_COLOR, border_width=1, corner_radius=12)
        rp.pack(side="right", fill="both", expand=True, padx=(0,20), pady=20)

        th = ctk.CTkFrame(rp, fg_color="transparent")
        th.pack(fill="x", pady=(18,10), padx=15)
        ctk.CTkLabel(th, text="Action Timeline", font=ctk.CTkFont(family="Segoe UI", size=16, weight="bold"), text_color=TEXT_MAIN).pack(side="left")
        ctk.CTkButton(th, text="🗑️ Clear", fg_color=ACCENT_RED, width=80, height=30, command=self.clear_macro).pack(side="right")

        self.timeline_scroll = ctk.CTkScrollableFrame(rp, fg_color="#141517", border_color="#222327", border_width=1, corner_radius=8)
        self.timeline_scroll.pack(fill="both", expand=True, padx=15, pady=5)

        et = ctk.CTkFrame(rp, fg_color="transparent")
        et.pack(fill="x", pady=15, padx=15)
        ctk.CTkButton(et, text="▲ Move Up",   width=90, height=32, fg_color="#2d2f34", command=lambda: self.move_action(-1)).pack(side="left", padx=2)
        ctk.CTkButton(et, text="▼ Move Down", width=90, height=32, fg_color="#2d2f34", command=lambda: self.move_action(1)).pack(side="left",  padx=2)
        ctk.CTkButton(et, text="❌ Delete",   fg_color=ACCENT_RED, height=32, command=self.delete_action).pack(side="right", padx=2)
        self.add_manual_btn = ctk.CTkButton(et, text="➕ Add Action", fg_color=ACCENT_BLUE, width=110, height=32, command=self.toggle_inline_action_listener)
        self.add_manual_btn.pack(side="right", padx=2)

    # ── Inline action listener ─────────────────────────────────────────────────
    def toggle_inline_action_listener(self):
        if self.is_playing or self.is_recording: return
        if not self.listening_for_manual_action:
            self.listening_for_manual_action = True
            self.add_manual_btn.configure(text="Listening...", fg_color=ACCENT_RED)
            self.manual_mouse_listener    = mouse.Listener(on_click=self._on_inline_mouse_click)
            self.manual_keyboard_listener = keyboard.Listener(on_press=self._on_inline_key_press)
            self.manual_mouse_listener.start()
            self.manual_keyboard_listener.start()
        else:
            self._stop_inline_listener()

    def _stop_inline_listener(self):
        self.listening_for_manual_action = False
        self.add_manual_btn.configure(text="➕ Add Action", fg_color=ACCENT_BLUE)
        if self.manual_mouse_listener:    self.manual_mouse_listener.stop()
        if self.manual_keyboard_listener: self.manual_keyboard_listener.stop()

    def _on_inline_key_press(self, key):
        vk, name = self._extract_key_info(key)
        self.after(0, lambda: self.add_single_action_to_live_ui({'type':'keyboard','details':None,'vk':vk,'name':name,'is_release':False,'delay':1.0}))
        self.after(0, lambda: self.add_single_action_to_live_ui({'type':'keyboard','details':None,'vk':vk,'name':name,'is_release':True, 'delay':0.05}))
        self.after(0, self._stop_inline_listener)

    def _on_inline_mouse_click(self, x, y, button, pressed):
        if pressed:
            self.after(0, lambda: self.add_single_action_to_live_ui({'type':'mouse','details':(x,y,button),'delay':1.0}))
            self.after(0, self._stop_inline_listener)

    # ── Drag-reorder ───────────────────────────────────────────────────────────
    def on_drag_start(self, event, index):
        self.dragged_index = index
        self.drag_y_start  = event.y_root
        self.select_timeline_item(index)

    def on_drag_motion(self, event, index):
        if self.dragged_index is None: return
        delta = event.y_root - self.drag_y_start
        if delta > 32 and self.dragged_index < len(self.macro_actions)-1:
            i = self.dragged_index
            self.macro_actions[i], self.macro_actions[i+1] = self.macro_actions[i+1], self.macro_actions[i]
            self.dragged_index = i+1; self.drag_y_start = event.y_root
            self.update_row_texts_only(); self.select_timeline_item(i+1)
        elif delta < -32 and self.dragged_index > 0:
            i = self.dragged_index
            self.macro_actions[i], self.macro_actions[i-1] = self.macro_actions[i-1], self.macro_actions[i]
            self.dragged_index = i-1; self.drag_y_start = event.y_root
            self.update_row_texts_only(); self.select_timeline_item(i-1)

    def on_drag_release(self, event, index): self.dragged_index = None

    # ── Timeline helpers ───────────────────────────────────────────────────────
    def _action_text(self, idx, action):
        if action['type'] == 'mouse':
            btn  = str(action['details'][2]).split('.')[-1].upper()
            return f" [{idx+1}] 🖱️ CLICK ({btn}) ➔ X:{action['details'][0]}, Y:{action['details'][1]}"
        else:
            state = "PRESS" if not action.get('is_release') else "RELEASE"
            vk_s  = f"VK=0x{action['vk']:02X}" if action.get('vk') else "VK=?"
            return f" [{idx+1}] ⌨️ {state} [{action.get('name','?')}] {vk_s}"

    def update_row_texts_only(self):
        for idx, action in enumerate(self.macro_actions):
            if idx >= len(self.action_ui_rows): break
            children = self.action_ui_rows[idx].winfo_children()
            if children and isinstance(children[0], ctk.CTkButton):
                children[0].configure(text=self._action_text(idx, action))
            if len(children) > 1 and isinstance(children[1], ctk.CTkFrame):
                for sub in children[1].winfo_children():
                    if isinstance(sub, ctk.CTkEntry):
                        sub.delete(0,'end'); sub.insert(0, f"{action['delay']:.2f}")

    def update_action_delay(self, index, val_str):
        try:
            v = float(val_str)
            if v >= 0: self.macro_actions[index]['delay'] = v
        except ValueError: pass

    def add_single_action_to_live_ui(self, action):
        self.macro_actions.append(action)
        idx = len(self.macro_actions)-1
        row = ctk.CTkFrame(self.timeline_scroll, fg_color="#1d1f23", border_color="#2b2d31", border_width=1, corner_radius=6, height=40)
        row.pack(fill="x", pady=2, padx=5)
        row.pack_propagate(False)

        lbl = ctk.CTkButton(row, text=self._action_text(idx, action), anchor="w",
                            fg_color="transparent", hover_color="#282a2e",
                            font=ctk.CTkFont(size=12), corner_radius=0,
                            command=lambda i=idx: self.select_timeline_item(i))
        lbl.pack(side="left", fill="both", expand=True)
        lbl.bind("<ButtonPress-1>",   lambda e, i=idx: self.on_drag_start(e, i),   add="+")
        lbl.bind("<B1-Motion>",       lambda e, i=idx: self.on_drag_motion(e, i))
        lbl.bind("<ButtonRelease-1>", lambda e, i=idx: self.on_drag_release(e, i))

        def_ = ctk.CTkFrame(row, fg_color="transparent")
        def_.pack(side="right", padx=10, fill="y")
        ent = ctk.CTkEntry(def_, width=55, height=24, font=ctk.CTkFont(size=11), corner_radius=4)
        ent.insert(0, f"{action['delay']:.2f}")
        ent.pack(side="left", padx=2)
        ent.bind("<FocusOut>", lambda e, i=idx, en=ent: self.update_action_delay(i, en.get()))
        ctk.CTkLabel(def_, text="s wait", font=ctk.CTkFont(size=11), text_color=TEXT_MUTED).pack(side="left", padx=2)

        self.action_ui_rows.append(row)
        self.info_label.configure(text=f"Actions Logged: {len(self.macro_actions)}")

    def refresh_timeline_ui(self):
        for row in self.action_ui_rows: row.destroy()
        self.action_ui_rows.clear()
        sel = self.selected_action_index
        self.selected_action_index = None
        acts = list(self.macro_actions); self.macro_actions = []
        for a in acts: self.add_single_action_to_live_ui(a)
        if sel is not None and sel < len(self.macro_actions): self.select_timeline_item(sel)

    def select_timeline_item(self, index):
        if index < 0 or index >= len(self.macro_actions): return
        old = self.selected_action_index; self.selected_action_index = index
        if old is not None and old < len(self.action_ui_rows):
            self.action_ui_rows[old].configure(fg_color="#1d1f23", border_color="#2b2d31")
        if index < len(self.action_ui_rows):
            self.action_ui_rows[index].configure(fg_color="#23354d", border_color=ACCENT_BLUE)

    def move_action(self, direction):
        if self.selected_action_index is None: return
        o = self.selected_action_index; n = o + direction
        if 0 <= n < len(self.macro_actions):
            self.macro_actions[o], self.macro_actions[n] = self.macro_actions[n], self.macro_actions[o]
            self.update_row_texts_only(); self.select_timeline_item(n)

    def delete_action(self):
        if self.selected_action_index is None: return
        self.macro_actions.pop(self.selected_action_index)
        self.selected_action_index = None; self.refresh_timeline_ui()

    # ── Misc helpers ───────────────────────────────────────────────────────────
    def toggle_exe_lock(self):
        if self.exe_switch_var.get() == "on":
            self.exe_entry_frame.pack(fill="x", padx=20, pady=(4,12))
            self.exe_name_entry.configure(state="readonly")
            self.exe_detect_btn.configure(state="normal")
            self.refresh_running_exes_list()
        else:
            self.exe_entry_frame.pack_forget()
            self.exe_name_entry.configure(state="disabled")
            self.exe_detect_btn.configure(state="disabled")

    def refresh_running_exes_list(self):
        lst = get_all_visible_window_exes()
        self.exe_name_entry.configure(values=lst)
        if lst: self.exe_name_entry.set(lst[0])

    def change_loop_mode(self):
        self.loop_mode = self.loop_var.get()
        for w in self.dynamic_loop_inputs.winfo_children(): w.destroy()
        if self.loop_mode == "Count":
            ctk.CTkLabel(self.dynamic_loop_inputs, text="Loops:", text_color=TEXT_MUTED).pack(side="left", padx=5)
            self.count_entry = ctk.CTkEntry(self.dynamic_loop_inputs, width=55, height=24)
            self.count_entry.insert(0, "5")
            self.count_entry.pack(side="left", padx=5)
        if self.loop_mode in ("Loop", "Count"):
            ctk.CTkLabel(self.dynamic_loop_inputs, text="Delay between loops (s):", text_color=TEXT_MUTED).pack(side="left", padx=(10, 5))
            self.loop_delay_entry = ctk.CTkEntry(self.dynamic_loop_inputs, width=55, height=24)
            self.loop_delay_entry.insert(0, "0.0")
            self.loop_delay_entry.pack(side="left", padx=5)

    def check_ui_queue(self):
        try:
            while True:
                msg = self.ui_queue.get_nowait()
                if msg == "STOP_PLAYBACK": self.stop_playback_ui_reset()
        except queue.Empty: pass
        self.after(100, self.check_ui_queue)

    def start_listening_for_hotkey(self, target):
        if self.is_recording or self.is_playing: return
        self.listening_for_new_hotkey = target
        if target == 'record': self.rec_hk_btn.configure(text="Listening...", fg_color=ACCENT_RED)
        elif target == 'play': self.play_hk_btn.configure(text="Listening...", fg_color=ACCENT_GREEN)

    def export_macro(self):
        if not self.macro_actions: return
        fp = filedialog.asksaveasfilename(defaultextension=".json", filetypes=[("JSON Profile","*.json")])
        if fp:
            out = []
            for a in self.macro_actions:
                if a['type'] == 'mouse':
                    out.append({'type':'mouse','x':a['details'][0],'y':a['details'][1],'button':str(a['details'][2]).split('.')[-1],'delay':a['delay']})
                else:
                    out.append({'type':'keyboard','vk':a.get('vk'),'name':a.get('name','?'),'is_release':a.get('is_release',False),'delay':a['delay']})
            with open(fp,'w') as f: json.dump(out, f, indent=4)

    def import_macro(self):
        if self.is_playing or self.is_recording: return
        fp = filedialog.askopenfilename(filetypes=[("JSON Profile","*.json")])
        if fp:
            try:
                with open(fp,'r') as f: data = json.load(f)
                self.macro_actions.clear()
                for it in data:
                    if it['type'] == 'mouse':
                        self.macro_actions.append({'type':'mouse','details':(it['x'],it['y'],getattr(mouse.Button,it['button'].lower(),mouse.Button.left)),'delay':it['delay']})
                    else:
                        self.macro_actions.append({'type':'keyboard','details':None,'vk':it.get('vk'),'name':it.get('name'),'is_release':it.get('is_release',False),'delay':it['delay']})
                self.refresh_timeline_ui()
            except Exception: pass

    # ── Global hotkey listener ─────────────────────────────────────────────────
    def start_global_hotkey_listeners(self):
        def on_press(key):
            try:
                kn = ""
                if hasattr(key,'name'): kn = key.name.upper()
                elif hasattr(key,'char') and key.char: kn = key.char.upper()
                # Explicit overrides for common hotkey keys
                if key == keyboard.Key.home:      kn = "HOME"
                if key == keyboard.Key.page_up:   kn = "PAGE_UP"
                if key == keyboard.Key.page_down: kn = "PAGE_DOWN"
                if key == keyboard.Key.end:       kn = "END"
                if key == keyboard.Key.space:     kn = "SPACE"
                if key == keyboard.Key.esc and self.is_playing:
                    self.is_playing = False; return
                if self.listening_for_new_hotkey is not None:
                    tgt = self.listening_for_new_hotkey; self.listening_for_new_hotkey = None
                    if tgt == 'record':
                        self.selected_record_hotkey = kn
                        self.after(0, lambda: self.rec_hk_btn.configure(text=kn, fg_color="#2d2f34"))
                        self.after(0, lambda: self.record_btn.configure(text=f"🔴 Start Record ({kn})"))
                    elif tgt == 'play':
                        self.selected_play_hotkey = kn
                        self.after(0, lambda: self.play_hk_btn.configure(text=kn, fg_color="#2d2f34"))
                        self.after(0, lambda: self.play_btn.configure(text=f"▶ Run Sequence ({kn})"))
                    return
                if kn == self.selected_record_hotkey.upper(): self.after(0, self.toggle_recording)
                elif kn == self.selected_play_hotkey.upper(): self.after(0, self.toggle_playback)
            except Exception: pass
        self.global_hotkey_listener = keyboard.Listener(on_press=on_press)
        self.global_hotkey_listener.start()

    # ── Recording ─────────────────────────────────────────────────────────────
    def toggle_recording(self):
        if self.is_playing or self.listening_for_new_hotkey: return
        if not self.is_recording:
            self.is_recording = True
            for row in self.action_ui_rows: row.destroy()
            self.action_ui_rows.clear(); self.macro_actions.clear(); self.currently_pressed_keys.clear()
            self.start_time = time.time()
            self.record_btn.configure(text=f"⏹ Stop Record ({self.selected_record_hotkey})", fg_color="#9a1f1f")
            self.status_label.configure(text="CAPTURING OPERATIONS", text_color=ACCENT_RED)
            self.mouse_listener    = mouse.Listener(on_click=self.on_click)
            self.keyboard_listener = keyboard.Listener(on_press=self.on_press, on_release=self.on_release)
            self.mouse_listener.start(); self.keyboard_listener.start()
        else:
            self.is_recording = False
            self.record_btn.configure(text=f"🔴 Start Record ({self.selected_record_hotkey})", fg_color=ACCENT_RED)
            self.status_label.configure(text="ENGINE IDLE", text_color=TEXT_MUTED)
            if self.mouse_listener:    self.mouse_listener.stop()
            if self.keyboard_listener: self.keyboard_listener.stop()
            # Trim the stop-hotkey keystrokes from end of recording
            while self.macro_actions and self.macro_actions[-1].get('name','').upper() == self.selected_record_hotkey.upper():
                self.macro_actions.pop()
            self.update_row_texts_only()

    def on_click(self, x, y, button, pressed):
        if pressed and self.is_recording:
            delay = time.time() - self.start_time; self.start_time = time.time()
            self.after(0, lambda: self.add_single_action_to_live_ui({'type':'mouse','details':(x,y,button),'delay':delay}))

    def _extract_key_info(self, key):
        """Extract (vk_code, display_name) from a pynput key event."""
        # Special keys
        special = {
            keyboard.Key.space:     (0x20, "SPACE"),
            keyboard.Key.enter:     (0x0D, "ENTER"),
            keyboard.Key.shift:     (0xA0, "SHIFT"),    keyboard.Key.shift_l:  (0xA0, "SHIFT"),
            keyboard.Key.shift_r:   (0xA1, "R_SHIFT"),
            keyboard.Key.ctrl:      (0xA2, "CTRL"),     keyboard.Key.ctrl_l:   (0xA2, "CTRL"),
            keyboard.Key.ctrl_r:    (0xA3, "R_CTRL"),
            keyboard.Key.alt:       (0xA4, "ALT"),      keyboard.Key.alt_l:    (0xA4, "ALT"),
            keyboard.Key.alt_r:     (0xA5, "R_ALT"),
            keyboard.Key.tab:       (0x09, "TAB"),
            keyboard.Key.backspace: (0x08, "BACKSPACE"),
            keyboard.Key.delete:    (0x2E, "DELETE"),
            keyboard.Key.esc:       (0x1B, "ESC"),
            keyboard.Key.up:        (0x26, "UP"),       keyboard.Key.down:      (0x28, "DOWN"),
            keyboard.Key.left:      (0x25, "LEFT"),     keyboard.Key.right:     (0x27, "RIGHT"),
            keyboard.Key.home:      (0x24, "HOME"),     keyboard.Key.end:       (0x23, "END"),
            keyboard.Key.page_up:   (0x21, "PAGE_UP"),  keyboard.Key.page_down: (0x22, "PAGE_DOWN"),
            keyboard.Key.insert:    (0x2D, "INSERT"),   keyboard.Key.caps_lock: (0x14, "CAPS_LOCK"),
            keyboard.Key.f1: (0x70,"F1"),  keyboard.Key.f2:  (0x71,"F2"),
            keyboard.Key.f3: (0x72,"F3"),  keyboard.Key.f4:  (0x73,"F4"),
            keyboard.Key.f5: (0x74,"F5"),  keyboard.Key.f6:  (0x75,"F6"),
            keyboard.Key.f7: (0x76,"F7"),  keyboard.Key.f8:  (0x77,"F8"),
            keyboard.Key.f9: (0x78,"F9"),  keyboard.Key.f10: (0x79,"F10"),
            keyboard.Key.f11:(0x7A,"F11"), keyboard.Key.f12: (0x7B,"F12"),
        }
        if key in special: return special[key]

        # Character keys – use uppercase VK so it hits VK_TO_SCAN
        if hasattr(key, 'char') and key.char:
            vk   = ord(key.char.upper())
            name = key.char.upper()
            return vk, name

        # Fallback: raw .vk attribute
        if hasattr(key, 'vk') and key.vk is not None:
            vk   = key.vk
            name = SCAN_TO_NAME.get(VK_TO_SCAN.get(vk, 0), f"VK{vk:02X}")
            return vk, name

        return None, "UNKNOWN"

    def on_press(self, key):
        if self.is_recording:
            vk, name = self._extract_key_info(key)
            if name in self.currently_pressed_keys: return
            self.currently_pressed_keys.add(name)
            delay = time.time() - self.start_time; self.start_time = time.time()
            self.after(0, lambda: self.add_single_action_to_live_ui({'type':'keyboard','details':None,'vk':vk,'name':name,'is_release':False,'delay':delay}))

    def on_release(self, key):
        if self.is_recording:
            vk, name = self._extract_key_info(key)
            self.currently_pressed_keys.discard(name)
            delay = time.time() - self.start_time; self.start_time = time.time()
            self.after(0, lambda: self.add_single_action_to_live_ui({'type':'keyboard','details':None,'vk':vk,'name':name,'is_release':True,'delay':delay}))

    def clear_macro(self):
        if self.is_playing or self.is_recording: return
        self.macro_actions.clear(); self.selected_action_index = None; self.refresh_timeline_ui()

    # ── Playback ──────────────────────────────────────────────────────────────
    def toggle_playback(self):
        if self.is_recording or self.listening_for_new_hotkey: return
        if not self.is_playing:
            if not self.macro_actions: return
            self.is_playing = True
            self.play_btn.configure(text=f"⏹ Stop Play ({self.selected_play_hotkey})", fg_color="#1565c0")
            self.status_label.configure(text="PLAYING MACRO RUNTIME", text_color=ACCENT_GREEN)
            threading.Thread(target=self.play_macro, daemon=True).start()
        else:
            self.is_playing = False

    def play_macro(self):
        mouse_ctl = mouse.Controller()
        actions   = list(self.macro_actions)   # snapshot

        # Strip trailing hotkey artifacts
        while actions and actions[-1].get('name','').upper() in (
                self.selected_record_hotkey.upper(), self.selected_play_hotkey.upper()):
            actions.pop()
        if not actions:
            self.ui_queue.put("STOP_PLAYBACK"); return

        # Read loop settings fresh at play-start
        current_loop_mode = self.loop_var.get()
        max_loops = 1
        if current_loop_mode == "Loop":
            max_loops = 999_999_999
        elif current_loop_mode == "Count":
            try: max_loops = max(1, int(self.count_entry.get()))
            except Exception: max_loops = 1

        loop_delay = 0.0
        if current_loop_mode in ("Loop", "Count"):
            try: loop_delay = max(0.0, float(self.loop_delay_entry.get()))
            except Exception: loop_delay = 0.0

        active_keys = set()
        loop_count  = 0

        while self.is_playing and loop_count < max_loops:
            for action in actions:
                if not self.is_playing: break

                # Window lock
                if self.exe_switch_var.get() == "on":
                    tgt = self.exe_name_entry.get().strip().lower()
                    if tgt:
                        while self.is_playing and get_active_window_exe() != tgt:
                            time.sleep(0.05)

                # Interruptible delay
                remaining = action.get('delay', 0)
                while remaining > 0 and self.is_playing:
                    sl = min(0.02, remaining)
                    time.sleep(sl); remaining -= sl
                if not self.is_playing: break

                # Execute
                if action['type'] == 'mouse':
                    x, y, btn = action['details']
                    mouse_ctl.position = (x, y)
                    mouse_ctl.click(btn)

                elif action['type'] == 'keyboard':
                    vk  = action.get('vk')
                    rel = action.get('is_release', False)
                    if vk is None: continue
                    if send_hardware_input(vk, is_release=rel):
                        if rel: active_keys.discard(vk)
                        else:   active_keys.add(vk)
                    else:
                        try:
                            kb = keyboard.Controller()
                            pk = keyboard.KeyCode.from_vk(vk)
                            if rel: kb.release(pk)
                            else:   kb.press(pk)
                        except Exception: pass

            loop_count += 1

            # Inter-loop delay (interruptible)
            if self.is_playing and loop_count < max_loops and loop_delay > 0:
                remaining = loop_delay
                while remaining > 0 and self.is_playing:
                    sl = min(0.02, remaining)
                    time.sleep(sl); remaining -= sl

        # Release any stuck keys
        for vk in list(active_keys):
            send_hardware_input(vk, is_release=True)

        self.ui_queue.put("STOP_PLAYBACK")

    def stop_playback_ui_reset(self):
        self.is_playing = False
        self.play_btn.configure(text=f"▶ Run Sequence ({self.selected_play_hotkey})", fg_color=ACCENT_GREEN)
        self.status_label.configure(text="ENGINE IDLE", text_color=TEXT_MUTED)


if __name__ == "__main__":
    app = MacroApp()
    app.mainloop()
