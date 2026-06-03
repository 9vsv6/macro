import time
import threading
import ctypes
import json
import random
import math
import os
import base64
import customtkinter as ctk
from pynput import mouse, keyboard
from tkinter import filedialog, messagebox, Toplevel, Canvas
import queue
import cv2
import pyautogui
import numpy as np

# Enhanced Modern Color Palette
APP_BG = "#0c0c0e"          
PANEL_BG = "#141416"        
HEADER_BG = "#1a1a1e"       
BORDER_COLOR = "#222226"     
ACCENT_BLUE = "#2563eb"     
ACCENT_GREEN = "#16a34a"    
ACCENT_RED = "#dc2626"      
ACCENT_PURPLE = "#7c3aed"   
TEXT_MAIN = "#f3f4f6"       
TEXT_MUTED = "#9ca3af"      

ctk.set_appearance_mode("Dark")

# ── Windows API Specifications & Native Binding Engines ────────────────────────
GetForegroundWindow = ctypes.windll.user32.GetForegroundWindow
GetWindowThreadProcessId = ctypes.windll.user32.GetWindowThreadProcessId
OpenProcess = ctypes.windll.kernel32.OpenProcess
CloseHandle = ctypes.windll.kernel32.CloseHandle
QueryFullProcessImageNameW = ctypes.windll.kernel32.QueryFullProcessImageNameW
EnumWindows = ctypes.windll.user32.EnumWindows
IsWindowVisible = ctypes.windll.user32.IsWindowVisible
GetWindowTextW = ctypes.windll.user32.GetWindowTextW
GetDC = ctypes.windll.user32.GetDC
ReleaseDC = ctypes.windll.user32.ReleaseDC
GetPixel = ctypes.windll.gdi32.GetPixel
GetWindowRect = ctypes.windll.user32.GetWindowRect

PROCESS_QUERY_INFORMATION = 0x0400
PROCESS_VM_READ = 0x0010

class RECT(ctypes.Structure):
    _fields_ = [("left", ctypes.c_long), ("top", ctypes.c_long), ("right", ctypes.c_long), ("bottom", ctypes.c_long)]

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

def get_active_window_hwnd_and_exe():
    hwnd = GetForegroundWindow()
    return (hwnd, get_exe_from_hwnd(hwnd)) if hwnd else (None, "")

def get_all_visible_windows_info():
    results = []
    def cb(hwnd, _):
        if IsWindowVisible(hwnd):
            tb = ctypes.create_unicode_buffer(512)
            GetWindowTextW(hwnd, tb, 512)
            if tb.value.strip():
                e = get_exe_from_hwnd(hwnd)
                if e and not e.startswith("macro_app"): 
                    results.append((hwnd, e, tb.value.strip()))
        return True
    EnumWindows(ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_long, ctypes.c_long)(cb), 0)
    return results

def get_screen_pixel_color(x, y):
    hdc = GetDC(0)
    pixel = GetPixel(hdc, x, y)
    ReleaseDC(0, hdc)
    return f"#{pixel & 0xFF:02x}{(pixel >> 8) & 0xFF:02x}{(pixel >> 16) & 0xFF:02x}".upper()

# ── Humanized Path-Tracking Algorithms (Bézier Matrix) ────────────────────────
def human_mouse_move(mouse_ctl, start_x, start_y, target_x, target_y, steps=20):
    if start_x == target_x and start_y == target_y: return
    cx1 = start_x + (target_x - start_x) * random.uniform(0.1, 0.3) + random.randint(-10, 10)
    cy1 = start_y + (target_y - start_y) * random.uniform(0.1, 0.3) + random.randint(-10, 10)
    cx2 = target_x - (target_x - start_x) * random.uniform(0.1, 0.3) + random.randint(-10, 10)
    cy2 = target_y - (target_y - start_y) * random.uniform(0.1, 0.3) + random.randint(-10, 10)
    for i in range(steps + 1):
        t = i / steps
        t_skewed = math.sin(t * math.pi / 2) if t < 0.5 else 1 - math.cos(t * math.pi / 2)
        curr_x = int((1-t_skewed)**3*start_x + 3*(1-t_skewed)**2*t_skewed*cx1 + 3*(1-t_skewed)*t_skewed**2*cx2 + t_skewed**3*target_x)
        curr_y = int((1-t_skewed)**3*start_y + 3*(1-t_skewed)**2*t_skewed*cy1 + 3*(1-t_skewed)*t_skewed**2*cx2 + t_skewed**3*target_y)
        mouse_ctl.position = (curr_x, curr_y)
        time.sleep(random.uniform(0.001, 0.002))

# ── SendInput Native Structures ───────────────────────────────────────────────
SendInput = ctypes.windll.user32.SendInput
PUL = ctypes.POINTER(ctypes.c_ulong)
class KeyBdInput(ctypes.Structure): _fields_ = [("wVk", ctypes.c_ushort), ("wScan", ctypes.c_ushort), ("dwFlags", ctypes.c_ulong), ("time", ctypes.c_ulong), ("dwExtraInfo", PUL)]
class HardwareInput(ctypes.Structure): _fields_ = [("uMsg", ctypes.c_ulong), ("wParamL", ctypes.c_short), ("wParamH", ctypes.c_ushort)]
class MouseInput(ctypes.Structure): _fields_ = [("dx", ctypes.c_long), ("dy", ctypes.c_long), ("mouseData", ctypes.c_ulong), ("dwFlags", ctypes.c_ulong), ("time", ctypes.c_ulong), ("dwExtraInfo", PUL)]
class Input_I(ctypes.Union): _fields_ = [("ki", KeyBdInput), ("mi", MouseInput), ("hi", HardwareInput)]
class Input(ctypes.Structure): _fields_ = [("type", ctypes.c_ulong), ("ii", Input_I)]

VK_TO_SCAN = {0x41:0x1E,0x42:0x30,0x43:0x2E,0x44:0x20,0x45:0x12,0x46:0x21,0x47:0x22,0x48:0x23,0x49:0x17,0x4A:0x24,0x4B:0x25,0x4C:0x26,0x4D:0x32,0x4E:0x31,0x4F:0x18,0x50:0x19,0x51:0x10,0x52:0x13,0x53:0x1F,0x54:0x14,0x55:0x16,0x56:0x2F,0x57:0x11,0x58:0x2D,0x59:0x15,0x5A:0x2C,0x30:0x0B,0x31:0x02,0x32:0x03,0x33:0x04,0x34:0x05,0x35:0x06,0x36:0x07,0x37:0x08,0x38:0x09,0x39:0x0A,0x20:0x39,0x0D:0x1C,0x1B:0x01,0x09:0x0F,0x08:0x0E,0xA0:0x2A,0xA1:0x36,0xA2:0x1D,0xA4:0x38,0x14:0x3A,0x25:0x4B,0x26:0x48,0x27:0x4D,0x28:0x50}
SCAN_TO_NAME = {0x1E:"A",0x30:"B",0x2E:"C",0x20:"D",0x12:"E",0x21:"F",0x22:"G",0x23:"H",0x17:"I",0x24:"J",0x25:"K",0x26:"L",0x32:"M",0x31:"N",0x18:"O",0x19:"P",0x10:"Q",0x13:"R",0x1F:"S",0x14:"T",0x16:"U",0x2F:"V",0x11:"W",0x2D:"X",0x15:"Y",0x2C:"Z",0x02:"1",0x03:"2",0x04:"3",0x05:"4",0x06:"5",0x07:"6",0x08:"7",0x09:"8",0x0A:"9",0x0B:"0",0x39:"SPACE",0x1C:"ENTER",0x01:"ESC",0x0F:"TAB",0x0E:"BACKSPACE"}

def send_hardware_input(vk_code, is_release=False):
    scan = VK_TO_SCAN.get(vk_code, 0)
    if not scan: return False
    flags = 0x0008 | (0x0002 if is_release else 0)
    ii_ = Input_I()
    ii_.ki = KeyBdInput(0, scan, flags, 0, ctypes.pointer(ctypes.c_ulong(0)))
    command = Input(ctypes.c_ulong(1), ii_)
    SendInput(1, ctypes.pointer(command), ctypes.sizeof(command))
    return True

class ScreenSnipper(Toplevel):
    def __init__(self, callback):
        super().__init__()
        self.callback = callback
        self.attributes("-alpha", 0.35, "-fullscreen", True, "-topmost", True)
        self.config(cursor="cross")
        self.canvas = Canvas(self, cursor="cross", bg="black", highlightthickness=0)
        self.canvas.pack(fill="both", expand=True)
        self.canvas.bind("<ButtonPress-1>", self.on_press)
        self.canvas.bind("<B1-Motion>", self.on_drag)
        self.canvas.bind("<ButtonRelease-1>", self.on_release)
        self.start_x = self.start_y = self.rect = None

    def on_press(self, e):
        self.start_x, self.start_y = e.x, e.y
        self.rect = self.canvas.create_rectangle(e.x, e.y, e.x, e.y, outline="#7c3aed", width=2, fill="#7c3aed")

    def on_drag(self, e):
        self.canvas.coords(self.rect, self.start_x, self.start_y, e.x, e.y)

    def on_release(self, e):
        x1, y1, x2, y2 = min(self.start_x, e.x), min(self.start_y, e.y), max(self.start_x, e.x), max(self.start_y, e.y)
        self.destroy()
        if (x2 - x1) > 5 and (y2 - y1) > 5:
            self.callback(x1, y1, x2 - x1, y2 - y1)

class LiveHUD(Toplevel):
    def __init__(self, stop_callback):
        super().__init__()
        self.overrideredirect(True)
        self.attributes("-topmost", True, "-alpha", 0.9)
        self.geometry("260x70+30+30")
        self.configure(bg="#141416")
        
        self.border = Canvas(self, width=260, height=70, bg="#141416", highlightthickness=1, highlightbackground="#222226")
        self.border.pack(fill="both", expand=True)
        
        self.status_text = self.border.create_text(15, 22, text="● MACRO ACTIVE", font=("Segoe UI", 11, "bold"), fill="#16a34a", anchor="w")
        self.loop_text = self.border.create_text(15, 45, text="Loop Iterations: 0", font=("Consolas", 10), fill="#9ca3af", anchor="w")
        
        btn = ctk.CTkButton(self, text="STOP", width=65, height=34, fg_color="#dc2626", hover_color="#b91c1c", font=ctk.CTkFont(size=11, weight="bold"), command=stop_callback)
        btn.place(x=180, y=18)

    def update_stats(self, loops):
        self.border.itemconfig(self.loop_text, text=f"Loop Iterations: {loops}")

class MacroApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("Vision Macro Suite Pro")
        self.geometry("1280x880")
        self.minsize(1000, 700)
        self.configure(fg_color=APP_BG)

        self.macro_actions = []
        self.profiles_db = {}
        self.active_profile_name = "Default Profile"
        self.is_recording = self.is_playing = False
        self.selected_record_hotkey, self.selected_play_hotkey = "HOME", "PAGE_UP"
        self.loop_var = ctk.StringVar(value="One Time")
        self.exe_switch_var = ctk.StringVar(value="off")
        self.bezier_switch_var = ctk.StringVar(value="on")
        self.fuzz_switch_var = ctk.StringVar(value="on")
        
        self.global_trigger_image_path = None

        self.ui_queue = queue.Queue()
        self.action_ui_rows = []
        self.selected_action_index = self.listening_for_new_hotkey = None
        self.listening_for_manual_action = False
        self.currently_pressed_keys = set()
        self.recorded_target_hwnd = None
        self.recorded_target_exe = "Unknown Window"
        
        self.dragged_index = None
        self.drag_y_start = 0

        self.setup_layout_grid()
        self.start_global_hotkey_listeners()
        self.check_ui_queue()

    def setup_layout_grid(self):
        self.grid_columnconfigure(0, weight=1, minsize=240) 
        self.grid_columnconfigure(1, weight=3, minsize=360) 
        self.grid_columnconfigure(2, weight=4, minsize=440) 
        self.grid_rowconfigure(0, weight=1)

        # PROFILE EXPLORER (LEFT PANEL)
        self.sidebar_frame = ctk.CTkFrame(self, fg_color=PANEL_BG, border_color=BORDER_COLOR, border_width=1, corner_radius=0)
        self.sidebar_frame.grid(row=0, column=0, sticky="nsew")
        
        ctk.CTkLabel(self.sidebar_frame, text="📁 PROFILE EXPLORER", font=ctk.CTkFont(size=13, weight="bold"), text_color=TEXT_MAIN).pack(anchor="w", padx=16, pady=(20, 10))
        self.profile_listbox = ctk.CTkScrollableFrame(self.sidebar_frame, fg_color="#0c0c0e", border_color=BORDER_COLOR, border_width=1, corner_radius=6)
        self.profile_listbox.pack(fill="both", expand=True, padx=14, pady=10)
        
        ctk.CTkButton(self.sidebar_frame, text="➕ Create Profile", fg_color=ACCENT_BLUE, hover_color="#1d4ed8", font=ctk.CTkFont(size=12, weight="bold"), height=32, command=self.create_new_profile_entry).pack(fill="x", padx=14, pady=14)
        self.refresh_profile_catalog_ui()

        # PROPERTIES CONTROLS (MIDDLE PANEL)
        self.middle_frame = ctk.CTkScrollableFrame(self, fg_color="transparent")
        self.middle_frame.grid(row=0, column=1, sticky="nsew", padx=14, pady=14)

        id_card = ctk.CTkFrame(self.middle_frame, fg_color=PANEL_BG, border_color=BORDER_COLOR, border_width=1, corner_radius=10)
        id_card.pack(fill="x", pady=(0, 12))
        ctk.CTkLabel(id_card, text="Automation Pipeline Engine", font=ctk.CTkFont(size=16, weight="bold"), text_color=TEXT_MAIN).pack(pady=(12, 2))
        self.status_label = ctk.CTkLabel(id_card, text="● STABLE SYSTEM IDLE", font=ctk.CTkFont(size=11, weight="bold"), text_color=TEXT_MUTED)
        self.status_label.pack(pady=(0, 12))

        # CENTER PANEL: GLOBAL IMAGE TRIGGER CONTROL
        img_trigger_card = ctk.CTkFrame(self.middle_frame, fg_color=PANEL_BG, border_color=BORDER_COLOR, border_width=1, corner_radius=10)
        img_trigger_card.pack(fill="x", pady=6)
        
        self.trigger_header_container = ctk.CTkFrame(img_trigger_card, fg_color="transparent")
        self.trigger_header_container.pack(fill="x", padx=12, pady=4)
        
        self.trigger_status_title = ctk.CTkLabel(self.trigger_header_container, text="📸 GLOBAL SEQUENCE IMAGE TRIGGER", font=ctk.CTkFont(size=11, weight="bold"), text_color=TEXT_MAIN)
        self.trigger_status_title.pack(side="left", pady=4)
        
        self.clear_img_trigger_btn = ctk.CTkButton(self.trigger_header_container, text="❌ Clear", width=55, height=18, fg_color="#2b2d31", hover_color=ACCENT_RED, text_color=TEXT_MUTED, font=ctk.CTkFont(size=10, weight="bold"), command=self.remove_global_trigger_image)
        
        btn_container = ctk.CTkFrame(img_trigger_card, fg_color="transparent")
        btn_container.pack(fill="x", padx=10, pady=(2, 10))
        
        self.select_trigger_img_btn = ctk.CTkButton(btn_container, text="📂 Select Image File", fg_color="#2b2d31", hover_color="#3d4047", font=ctk.CTkFont(size=12, weight="bold"), height=34, command=self.set_global_center_trigger_image)
        self.select_trigger_img_btn.pack(side="left", expand=True, fill="x", padx=(4, 2))
        
        self.snipe_trigger_img_btn = ctk.CTkButton(btn_container, text="🎯 Snipe Vision Node", fg_color=ACCENT_PURPLE, hover_color="#6d28d9", font=ctk.CTkFont(size=12, weight="bold"), height=34, command=self.trigger_global_center_screen_sniper)
        self.snipe_trigger_img_btn.pack(side="right", expand=True, fill="x", padx=(2, 4))

        # Actions Panel
        act_card = ctk.CTkFrame(self.middle_frame, fg_color="transparent")
        act_card.pack(fill="x", pady=6)
        self.play_btn = ctk.CTkButton(act_card, text=f"▶ Run Sequence ({self.selected_play_hotkey})", fg_color=ACCENT_GREEN, hover_color="#15803d", font=ctk.CTkFont(size=13, weight="bold"), height=40, command=self.toggle_playback)
        self.play_btn.pack(fill="x", pady=3)
        self.record_btn = ctk.CTkButton(act_card, text=f"🔴 Capture Sequence ({self.selected_record_hotkey})", fg_color=ACCENT_RED, hover_color="#b91c1c", font=ctk.CTkFont(size=13, weight="bold"), height=40, command=self.toggle_recording)
        self.record_btn.pack(fill="x", pady=3)

        self.anchor_card = ctk.CTkFrame(self.middle_frame, fg_color=PANEL_BG, border_color=BORDER_COLOR, border_width=1, corner_radius=10)
        self.anchor_card.pack(fill="x", pady=6)
        self.anchor_status_lbl = ctk.CTkLabel(self.anchor_card, text="Anchor Window: Independent", font=ctk.CTkFont(size=11, family="Consolas"), text_color=ACCENT_BLUE, anchor="w")
        self.anchor_status_lbl.pack(fill="x", padx=14, pady=10)

        hk_card = ctk.CTkFrame(self.middle_frame, fg_color=PANEL_BG, border_color=BORDER_COLOR, border_width=1, corner_radius=10)
        hk_card.pack(fill="x", pady=6)
        ctk.CTkLabel(hk_card, text="⌨️  SYSTEM HOTKEY DRIVERS", font=ctk.CTkFont(size=11, weight="bold"), text_color=TEXT_MAIN).pack(anchor="w", padx=12, pady=6)
        
        hk_body = ctk.CTkFrame(hk_card, fg_color="transparent")
        hk_body.pack(fill="x", padx=14, pady=8)
        hk_body.grid_columnconfigure(0, weight=1)
        hk_body.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(hk_body, text="Record Shortcut Key:", text_color=TEXT_MUTED, font=ctk.CTkFont(size=12)).grid(row=0, column=0, padx=2, pady=5, sticky="w")
        self.rec_hk_btn = ctk.CTkButton(hk_body, text=self.selected_record_hotkey, width=120, height=26, fg_color="#222226", hover_color="#2d2d34", command=lambda: self.start_listening_for_hotkey('record'))
        self.rec_hk_btn.grid(row=0, column=1, padx=2, pady=5, sticky="e")
        
        ctk.CTkLabel(hk_body, text="Playback Shortcut Key:", text_color=TEXT_MUTED, font=ctk.CTkFont(size=12)).grid(row=1, column=0, padx=2, pady=5, sticky="w")
        self.play_hk_btn = ctk.CTkButton(hk_body, text=self.selected_play_hotkey, width=120, height=26, fg_color="#222226", hover_color="#2d2d34", command=lambda: self.start_listening_for_hotkey('play'))
        self.play_hk_btn.grid(row=1, column=1, padx=2, pady=5, sticky="e")

        drv_card = ctk.CTkFrame(self.middle_frame, fg_color=PANEL_BG, border_color=BORDER_COLOR, border_width=1, corner_radius=10)
        drv_card.pack(fill="x", pady=6)
        ctk.CTkLabel(drv_card, text="⏱️ INTERACTION CONFIGURATIONS", font=ctk.CTkFont(size=11, weight="bold"), text_color=TEXT_MAIN).pack(anchor="w", padx=12, pady=6)
        db = ctk.CTkFrame(drv_card, fg_color="transparent")
        db.pack(fill="x", padx=14, pady=8)
        ctk.CTkRadioButton(db, text="One Time Execution", variable=self.loop_var, value="One Time", font=ctk.CTkFont(size=12), command=self.change_loop_mode).pack(anchor="w", pady=2)
        ctk.CTkRadioButton(db, text="Infinite Processing Loops", variable=self.loop_var, value="Loop", font=ctk.CTkFont(size=12), command=self.change_loop_mode).pack(anchor="w", pady=2)
        ctk.CTkRadioButton(db, text="Custom Loop Count Iterations", variable=self.loop_var, value="Count", font=ctk.CTkFont(size=12), command=self.change_loop_mode).pack(anchor="w", pady=2)
        self.dynamic_loop_inputs = ctk.CTkFrame(self.middle_frame, fg_color="transparent")
        self.dynamic_loop_inputs.pack(fill="x", pady=2)

        hb = ctk.CTkFrame(self.middle_frame, fg_color=PANEL_BG, border_color=BORDER_COLOR, border_width=1, corner_radius=10)
        hb.pack(fill="x", pady=6)
        ctk.CTkLabel(hb, text="🛡️ ANTI-DETECTION HUMANIZATION", font=ctk.CTkFont(size=11, weight="bold"), text_color=ACCENT_GREEN).pack(anchor="w", padx=12, pady=6)
        hbb = ctk.CTkFrame(hb, fg_color="transparent")
        hbb.pack(fill="x", padx=14, pady=8)
        ctk.CTkSwitch(hbb, text="Enable Organic Bézier Curves", font=ctk.CTkFont(size=12), variable=self.bezier_switch_var, onvalue="on", offvalue="off").pack(anchor="w", pady=3)
        ctk.CTkSwitch(hbb, text="Randomize Target Jitter", font=ctk.CTkFont(size=12), variable=self.fuzz_switch_var, onvalue="on", offvalue="off").pack(anchor="w", pady=3)

        fb = ctk.CTkFrame(self.middle_frame, fg_color=PANEL_BG, border_color=BORDER_COLOR, border_width=1, corner_radius=10)
        fb.pack(fill="x", pady=6)
        ctk.CTkButton(fb, text="💾 Save to JSON", fg_color="#1a1a22", text_color=TEXT_MAIN, height=32, command=self.export_macro).pack(side="left", expand=True, fill="x", padx=8, pady=10)
        ctk.CTkButton(fb, text="📂 Load JSON", fg_color="#1a1a22", text_color=TEXT_MAIN, height=32, command=self.import_macro).pack(side="right", expand=True, fill="x", padx=8, pady=10)

        # TIMELINE FLOW (RIGHT PANEL)
        self.right_frame = ctk.CTkFrame(self, fg_color=PANEL_BG, border_color=BORDER_COLOR, border_width=1, corner_radius=12)
        self.right_frame.grid(row=0, column=2, sticky="nsew", padx=20, pady=20)

        th = ctk.CTkFrame(self.right_frame, fg_color="transparent")
        th.pack(fill="x", pady=(16, 10), padx=16)
        ctk.CTkLabel(th, text="Visual Pipeline Flow", font=ctk.CTkFont(size=15, weight="bold"), text_color=TEXT_MAIN).pack(side="left")
        ctk.CTkButton(th, text="🗑️ Clear Timeline", fg_color=ACCENT_RED, hover_color="#b91c1c", font=ctk.CTkFont(size=11, weight="bold"), width=110, height=28, command=self.clear_macro).pack(side="right")

        self.timeline_scroll = ctk.CTkScrollableFrame(self.right_frame, fg_color="#09090b", border_color=BORDER_COLOR, border_width=1, corner_radius=8)
        self.timeline_scroll.pack(fill="both", expand=True, padx=16, pady=4)

        et = ctk.CTkFrame(self.right_frame, fg_color="transparent")
        et.pack(fill="x", pady=14, padx=16)
        
        self.add_manual_btn = ctk.CTkButton(et, text="➕ Add Keyboard Key", fg_color=ACCENT_BLUE, hover_color="#1d4ed8", font=ctk.CTkFont(size=12, weight="bold"), height=34, command=self.toggle_inline_action_listener)
        self.add_manual_btn.pack(side="right", padx=2)

    def set_global_center_trigger_image(self):
        fp = filedialog.askopenfilename(title="Select Trigger Image Snippet", filetypes=[("Images", "*.png *.jpg *.jpeg")])
        if fp:
            self.global_trigger_image_path = fp
            fn = os.path.basename(fp)
            self.trigger_status_title.configure(text=f"📷 TRIGGER IMAGE BOUND: {fn.upper()}", text_color=ACCENT_GREEN)
            self.clear_img_trigger_btn.pack(side="right", padx=6, pady=2)

    def trigger_global_center_screen_sniper(self):
        if self.is_playing or self.is_recording: return
        self.withdraw()
        time.sleep(0.2)
        ScreenSnipper(self.process_center_panel_sniped_trigger)

    def process_center_panel_sniped_trigger(self, x, y, w, h):
        self.deiconify()
        captured_matrix = pyautogui.screenshot(region=(x, y, w, h))
        os.makedirs("./assets", exist_ok=True)
        assigned_path = f"./assets/global_trigger_{int(time.time())}.png"
        captured_matrix.save(assigned_path)
        
        self.global_trigger_image_path = assigned_path
        self.trigger_status_title.configure(text="📷 TRIGGER SNIP BOUND SUCCESSFUL", text_color=ACCENT_GREEN)
        self.clear_img_trigger_btn.pack(side="right", padx=6, pady=2)

    def remove_global_trigger_image(self):
        self.global_trigger_image_path = None
        self.trigger_status_title.configure(text="📸 GLOBAL SEQUENCE IMAGE TRIGGER", text_color=TEXT_MAIN)
        self.clear_img_trigger_btn.pack_forget()

    def clear_macro(self):
        if self.is_playing or self.is_recording: return
        self.macro_actions.clear()
        self.selected_action_index = None
        self.refresh_timeline_ui()

    # ── Profile Catalog Sync ──────────────────────────────────────────────────
    def create_new_profile_entry(self):
        name = f"Profile Vector {len(self.profiles_db)+1}"
        self.profiles_db[name] = []
        self.active_profile_name = name
        self.macro_actions = []
        self.refresh_profile_catalog_ui()
        self.refresh_timeline_ui()

    def select_profile_catalog_node(self, target_name):
        self.active_profile_name = target_name
        self.macro_actions = list(self.profiles_db.get(target_name, []))
        self.refresh_profile_catalog_ui()
        self.refresh_timeline_ui()

    def refresh_profile_catalog_ui(self):
        for widget in self.profile_listbox.winfo_children(): widget.destroy()
        if not self.profiles_db: self.profiles_db["Default Profile"] = []
        for p_name in self.profiles_db.keys():
            is_active = (p_name == self.active_profile_name)
            bg = "#1e1b4b" if is_active else "transparent"
            lbl_color = TEXT_MAIN if is_active else TEXT_MUTED
            btn = ctk.CTkButton(self.profile_listbox, text=f"🗃️ {p_name}", font=ctk.CTkFont(size=12, weight="bold" if is_active else "normal"), fg_color=bg, text_color=lbl_color, anchor="w", height=30, command=lambda name=p_name: self.select_profile_catalog_node(name))
            btn.pack(fill="x", pady=2, padx=4)

    def trigger_screen_sniper_flow(self):
        if self.is_playing or self.is_recording: return
        self.withdraw() 
        time.sleep(0.2)
        ScreenSnipper(self.process_sniped_bounding_box_assets)

    def process_sniped_bounding_box_assets(self, x, y, w, h):
        self.deiconify() 
        sniped_img = pyautogui.screenshot(region=(x, y, w, h))
        os.makedirs("./assets", exist_ok=True)
        asset_path = f"./assets/snippet_{int(time.time())}.png"
        sniped_img.save(asset_path)
        
        self.add_single_action_to_live_ui({
            'type': 'image_match_wait',
            'image_path': asset_path,
            'confidence': 0.85,
            'delay': 0.5
        })

    def on_row_drag_start(self, event, index):
        self.dragged_index = index
        self.drag_y_start = event.y_root
        self.select_timeline_item(index)

    def on_row_drag_motion(self, event, index):
        if self.dragged_index is None: return
        delta_y = event.y_root - self.drag_y_start
        
        if delta_y > 34 and self.dragged_index < len(self.macro_actions) - 1:
            i = self.dragged_index
            self.macro_actions[i], self.macro_actions[i+1] = self.macro_actions[i+1], self.macro_actions[i]
            self.dragged_index = i + 1
            self.drag_y_start = event.y_root
            self.refresh_timeline_ui()
            self.select_timeline_item(i + 1)
        elif delta_y < -34 and self.dragged_index > 0:
            i = self.dragged_index
            self.macro_actions[i], self.macro_actions[i-1] = self.macro_actions[i-1], self.macro_actions[i]
            self.dragged_index = i - 1
            self.drag_y_start = event.y_root
            self.refresh_timeline_ui()
            self.select_timeline_item(i - 1)

    def on_row_drag_release(self, event, index):
        self.dragged_index = None
        self.profiles_db[self.active_profile_name] = list(self.macro_actions)

    def play_macro(self):
        mouse_ctl = mouse.Controller()
        actions = [a for a in self.macro_actions if a.get('name','').upper() not in (self.selected_record_hotkey.upper(), self.selected_play_hotkey.upper())]
        if not actions:
            self.ui_queue.put("STOP_PLAYBACK")
            return

        current_loop_mode = self.loop_var.get()
        max_loops = float('inf') if current_loop_mode == "Loop" else (int(self.count_entry.get()) if current_loop_mode == "Count" else 1)
        loop_delay = max(0.0, float(self.loop_delay_entry.get())) if current_loop_mode in ("Loop", "Count") else 0.1
        
        loop_count = 0
        self.hud_window = LiveHUD(stop_callback=self.toggle_playback)

        while self.is_playing and (max_loops == float('inf') or loop_count < max_loops):
            self.hud_window.update_stats(loop_count)

            if self.global_trigger_image_path and os.path.exists(self.global_trigger_image_path):
                global_matched = False
                template = cv2.imread(self.global_trigger_image_path, cv2.IMREAD_UNCHANGED)
                while self.is_playing and not global_matched:
                    screen = cv2.cvtColor(np.array(pyautogui.screenshot()), cv2.COLOR_RGB2BGR)
                    res = cv2.matchTemplate(screen, template, cv2.TM_CCOEFF_NORMED)
                    if cv2.minMaxLoc(res)[1] >= 0.85:
                        global_matched = True
                    else:
                        time.sleep(0.1)

            for action in actions:
                if not self.is_playing: break

                remaining = action.get('delay', 0)
                while remaining > 0 and self.is_playing:
                    sl = min(0.02, remaining); time.sleep(sl); remaining -= sl
                if not self.is_playing: break

                base_x, base_y = 0, 0
                if self.recorded_target_exe and self.recorded_target_exe != "Unknown Window":
                    for win_info in get_all_visible_windows_info():
                        if win_info[1] == self.recorded_target_exe:
                            rect = RECT()
                            if GetWindowRect(win_info[0], ctypes.byref(rect)):
                                base_x, base_y = rect.left, rect.top
                            break

                if action['type'] == 'image_match_wait':
                    template = cv2.imread(action['image_path'], cv2.IMREAD_UNCHANGED)
                    matched = False
                    while self.is_playing and not matched:
                        screen = cv2.cvtColor(np.array(pyautogui.screenshot()), cv2.COLOR_RGB2BGR)
                        res = cv2.matchTemplate(screen, template, cv2.TM_CCOEFF_NORMED)
                        if cv2.minMaxLoc(res)[1] >= action.get('confidence', 0.85): matched = True
                        else: time.sleep(0.1)
                    continue

                elif action['type'] == 'pixel_wait':
                    px, py = base_x + action['rel_x'], base_y + action['rel_y']
                    while self.is_playing and get_screen_pixel_color(px, py) != action['color'].upper(): time.sleep(0.05)
                    continue

                elif action['type'] == 'mouse':
                    tx, ty = base_x + action['rel_x'], base_y + action['rel_y']
                    if self.fuzz_switch_var.get() == "on":
                        tx += random.randint(-2, 2)
                        ty += random.randint(-2, 2)
                    if self.bezier_switch_var.get() == "on":
                        sp = mouse_ctl.position
                        human_mouse_move(mouse_ctl, sp[0], sp[1], tx, ty)
                    else:
                        mouse_ctl.position = (tx, ty)
                    time.sleep(random.uniform(0.005, 0.01))
                    mouse_ctl.click(action['details'][2])

                elif action['type'] == 'keyboard':
                    vk, rel = action.get('vk'), action.get('is_release', False)
                    if vk is not None:
                        repeats = action.get('repeat_count', 1)
                        if not rel and repeats > 1:
                            for _ in range(repeats):
                                if not self.is_playing: break
                                send_hardware_input(vk, is_release=False)
                                time.sleep(0.02)
                        else:
                            send_hardware_input(vk, is_release=rel)

            loop_count += 1
            if self.is_playing and (max_loops == float('inf') or loop_count < max_loops): time.sleep(loop_delay)

        self.hud_window.destroy()
        self.ui_queue.put("STOP_PLAYBACK")

    def toggle_inline_action_listener(self):
        if self.is_playing or self.is_recording: return
        if not self.listening_for_manual_action:
            self.listening_for_manual_action = True
            self.add_manual_btn.configure(text="Listening...", fg_color=ACCENT_RED)
            self.manual_mouse_listener = mouse.Listener(on_click=self._on_inline_mouse_click)
            self.manual_keyboard_listener = keyboard.Listener(on_press=self._on_inline_key_press)
            self.manual_mouse_listener.start(); self.manual_keyboard_listener.start()
        else: self.stop_inline_listener()

    def stop_inline_listener(self):
        self.listening_for_manual_action = False
        self.add_manual_btn.configure(text="➕ Add Keyboard Key", fg_color=ACCENT_BLUE)
        if hasattr(self, 'manual_mouse_listener'): self.manual_mouse_listener.stop()
        if hasattr(self, 'manual_keyboard_listener'): self.manual_keyboard_listener.stop()

    def update_row_texts_only(self):
        for idx, action in enumerate(self.macro_actions):
            if idx >= len(self.action_ui_rows): break
            children = self.action_ui_rows[idx].winfo_children()
            if children and isinstance(children[0], ctk.CTkButton): children[0].configure(text=self._action_text(idx, action))

    def update_action_delay(self, index, val_str):
        try:
            v = float(val_str)
            if v >= 0: self.macro_actions[index]['delay'] = v
        except ValueError: pass

    def add_single_action_to_live_ui(self, action):
        if 'rel_x' not in action and action['type'] == 'mouse':
            action['rel_x'], action['rel_y'] = action['details'][0], action['details'][1]
        self.macro_actions.append(action)
        self.profiles_db[self.active_profile_name] = list(self.macro_actions)
        
        idx = len(self.macro_actions)-1
        row = ctk.CTkFrame(self.timeline_scroll, fg_color="#141416", border_color=BORDER_COLOR, border_width=1, corner_radius=6, height=40)
        row.pack(fill="x", pady=3, padx=5)
        row.pack_propagate(False)
        
        lbl = ctk.CTkButton(row, text=self._action_text(idx, action), anchor="w", fg_color="transparent", font=ctk.CTkFont(family="Consolas", size=11), corner_radius=0, command=lambda i=idx: self.select_timeline_item(i))
        lbl.pack(side="left", fill="both", expand=True)
        
        lbl.bind("<ButtonPress-1>", lambda e, i=idx: self.on_row_drag_start(e, i), add="+")
        lbl.bind("<B1-Motion>", lambda e, i=idx: self.on_row_drag_motion(e, i))
        lbl.bind("<ButtonRelease-1>", lambda e, i=idx: self.on_row_drag_release(e, i))

        def_ = ctk.CTkFrame(row, fg_color="transparent")
        def_.pack(side="right", padx=4, fill="y")
        
        ent = ctk.CTkEntry(def_, width=48, height=24, font=ctk.CTkFont(family="Consolas", size=11), fg_color="#0c0c0e", border_color=BORDER_COLOR)
        ent.insert(0, f"{action['delay']:.2f}")
        ent.pack(side="left", padx=2)
        ent.bind("<FocusOut>", lambda e, i=idx, en=ent: self.update_action_delay(i, en.get()))
        
        del_btn = ctk.CTkButton(def_, text="✕", width=22, height=24, fg_color="transparent", text_color=TEXT_MUTED, hover_color=ACCENT_RED, font=ctk.CTkFont(size=11, weight="bold"), command=lambda i=idx: self.delete_specific_action_node(i))
        del_btn.pack(side="right", padx=2)

        self.action_ui_rows.append(row)

    def delete_specific_action_node(self, target_index):
        if self.is_playing or self.is_recording: return
        if target_index < len(self.macro_actions):
            self.macro_actions.pop(target_index)
            self.profiles_db[self.active_profile_name] = list(self.macro_actions)
            self.refresh_timeline_ui()

    def refresh_timeline_ui(self):
        for r in self.action_ui_rows: r.destroy()
        self.action_ui_rows.clear()
        acts = list(self.macro_actions); self.macro_actions = []
        for a in acts: self.add_single_action_to_live_ui(a)

    def select_timeline_item(self, index):
        if index < 0 or index >= len(self.macro_actions): return
        old = self.selected_action_index; self.selected_action_index = index
        if old is not None and old < len(self.action_ui_rows): self.action_ui_rows[old].configure(fg_color="#141416")
        if index < len(self.action_ui_rows): self.action_ui_rows[index].configure(fg_color="#1e293b")

    def toggle_exe_lock(self):
        if self.exe_switch_var.get() == "on": self.exe_entry_frame.pack(fill="x", padx=4, pady=4); self.refresh_running_exes_list()
        else: self.exe_entry_frame.pack_forget()

    def refresh_running_exes_list(self):
        lst = sorted(list(set([w[1] for w in get_all_visible_windows_info()])))
        self.exe_name_entry.configure(values=lst)
        if lst: self.exe_name_entry.set(lst[0])

    def change_loop_mode(self):
        for w in self.dynamic_loop_inputs.winfo_children(): w.destroy()
        if self.loop_var.get() in ("Count", "Loop"):
            rf = ctk.CTkFrame(self.dynamic_loop_inputs, fg_color=PANEL_BG, border_color=BORDER_COLOR, border_width=1, corner_radius=8)
            rf.pack(fill="x", pady=4)
            if self.loop_var.get() == "Count":
                ctk.CTkLabel(rf, text="Limit:", font=ctk.CTkFont(size=12)).pack(side="left", padx=8)
                self.count_entry = ctk.CTkEntry(rf, width=45, height=24); self.count_entry.insert(0, "5"); self.count_entry.pack(side="left", padx=4)
            ctk.CTkLabel(rf, text="Pause:", font=ctk.CTkFont(size=12)).pack(side="left", padx=8)
            self.loop_delay_entry = ctk.CTkEntry(rf, width=45, height=24); self.loop_delay_entry.insert(0, "0.1"); self.loop_delay_entry.pack(side="left", padx=4)

    def check_ui_queue(self):
        try:
            while True:
                if self.ui_queue.get_nowait() == "STOP_PLAYBACK": self.stop_playback_ui_reset()
        except queue.Empty: pass
        self.after(100, self.check_ui_queue)

    def start_listening_for_hotkey(self, target):
        self.listening_for_new_hotkey = target
        if target == 'record': self.rec_hk_btn.configure(text="Listening...", fg_color=ACCENT_RED)
        elif target == 'play': self.play_hk_btn.configure(text="Listening...", fg_color=ACCENT_GREEN)

    def start_global_hotkey_listeners(self):
        def on_press(key):
            try:
                kn = ""
                if hasattr(key,'name'): kn = key.name.upper()
                elif hasattr(key,'char') and key.char: kn = key.char.upper()
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
                        self.after(0, lambda: self.rec_hk_btn.configure(text=kn, fg_color="#222226"))
                        self.after(0, lambda: self.record_btn.configure(text=f"🔴 Capture Sequence ({kn})"))
                    elif tgt == 'play':
                        self.selected_play_hotkey = kn
                        self.after(0, lambda: self.play_hk_btn.configure(text=kn, fg_color="#222226"))
                        self.after(0, lambda: self.play_btn.configure(text=f"▶ Run Sequence ({kn})"))
                    return
                
                if kn == self.selected_record_hotkey.upper(): self.after(0, self.toggle_recording)
                elif kn == self.selected_play_hotkey.upper(): self.after(0, self.toggle_playback)
            except Exception: pass
        self.global_hotkey_listener = keyboard.Listener(on_press=on_press)
        self.global_hotkey_listener.start()

    def toggle_recording(self):
        if self.is_playing: return
        if not self.is_recording:
            hwnd, exe = get_active_window_hwnd_and_exe()
            if hwnd: self.recorded_target_hwnd, self.recorded_target_exe = hwnd, exe; self.anchor_status_lbl.configure(text=f"Anchor Window: {exe}")
            self.is_recording = True
            self.macro_actions.clear(); self.refresh_timeline_ui()
            self.start_time = time.time()
            self.mouse_listener, self.keyboard_listener = mouse.Listener(on_click=self.on_click), keyboard.Listener(on_press=self.on_press, on_release=self.on_release)
            self.mouse_listener.start(); self.keyboard_listener.start()
        else:
            self.is_recording = False
            self.mouse_listener.stop(); self.keyboard_listener.stop()

    def on_click(self, x, y, button, pressed):
        if pressed and self.is_recording:
            d = time.time() - self.start_time; self.start_time = time.time()
            rx, ry = x, y
            if self.recorded_target_hwnd:
                rect = RECT(); GetWindowRect(self.recorded_target_hwnd, ctypes.byref(rect))
                rx, ry = x - rect.left, y - rect.top
            self.after(0, lambda: self.add_single_action_to_live_ui({'type':'mouse','rel_x':rx,'rel_y':ry,'details':(x,y,button),'delay':d}))

    def _extract_key_info(self, key):
        special_translation = {
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
        if key in special_translation: 
            return special_translation[key]

        if hasattr(key, 'char') and key.char:
            return ord(key.char.upper()), key.char.upper()

        if hasattr(key, 'vk') and key.vk is not None:
            return key.vk, SCAN_TO_NAME.get(VK_TO_SCAN.get(key.vk, 0), f"VK_{key.vk}")

        return None, "UNKNOWN"

    def on_press(self, key):
        if self.is_recording:
            vk, name = self._extract_key_info(key)
            if not vk: return
            
            if self.macro_actions and self.macro_actions[-1]['type'] == 'keyboard' and self.macro_actions[-1]['name'] == name and not self.macro_actions[-1]['is_release']:
                self.macro_actions[-1]['repeat_count'] = self.macro_actions[-1].get('repeat_count', 1) + 1
                self.update_row_texts_only()
                return

            self.currently_pressed_keys.add(name)
            d = time.time() - self.start_time; self.start_time = time.time()
            self.after(0, lambda: self.add_single_action_to_live_ui({'type':'keyboard','vk':vk,'name':name,'is_release':False,'repeat_count':1,'delay':d}))

    def on_release(self, key):
        if self.is_recording:
            vk, name = self._extract_key_info(key)
            if not vk: return
            self.currently_pressed_keys.discard(name)
            d = time.time() - self.start_time; self.start_time = time.time()
            self.after(0, lambda: self.add_single_action_to_live_ui({'type':'keyboard','vk':vk,'name':name,'is_release':True,'delay':d}))

    def _on_inline_key_press(self, key):
        vk, name = self._extract_key_info(key)
        if vk:
            self.after(0, lambda: self.add_single_action_to_live_ui({'type':'keyboard','vk':vk,'name':name,'is_release':False,'delay':1.0}))
            self.after(0, lambda: self.add_single_action_to_live_ui({'type':'keyboard','vk':vk,'name':name,'is_release':True,'delay':0.05}))
        self.after(0, self.stop_inline_listener)

    def _on_inline_mouse_click(self, x, y, button, pressed):
        if pressed:
            self.after(0, lambda: self.add_single_action_to_live_ui({'type':'mouse','details':(x,y,button),'delay':1.0}))
            self.after(0, self.stop_inline_listener)

    def toggle_playback(self):
        if self.is_recording or not self.macro_actions: return
        if not self.is_playing:
            self.is_playing = True
            threading.Thread(target=self.play_macro, daemon=True).start()
        else: self.is_playing = False

    def stop_playback_ui_reset(self):
        self.is_playing = False
        self.status_label.configure(text="● STABLE SYSTEM IDLE")

    def export_macro(self):
        fp = filedialog.asksaveasfilename(defaultextension=".json", filetypes=[("JSON Profile", "*.json")])
        if fp:
            image_base64_string = None
            if self.global_trigger_image_path and os.path.exists(self.global_trigger_image_path):
                with open(self.global_trigger_image_path, "rb") as image_file:
                    image_base64_string = base64.b64encode(image_file.read()).decode('utf-8')
            
            payload = {
                'target': self.recorded_target_exe,
                'embedded_trigger_image': image_base64_string,
                'actions': self.macro_actions
            }
            with open(fp, 'w') as f: 
                json.dump(payload, f, indent=4)
            messagebox.showinfo("Export Successful", "Macro profile saved successfully!")

    # ── FIXED: Added instant packing handler for loading base64 configurations ──
    def import_macro(self):
        fp = filedialog.askopenfilename(filetypes=[("JSON Profile", "*.json")])
        if fp:
            try:
                with open(fp, 'r') as f: 
                    data = json.load(f)
                
                self.recorded_target_exe = data.get('target', 'Unknown Window')
                self.macro_actions = data.get('actions', [])
                
                encoded_image = data.get('embedded_trigger_image')
                if encoded_image:
                    os.makedirs("./assets", exist_ok=True)
                    reconstructed_path = f"./assets/global_trigger_{int(time.time())}.png"
                    
                    with open(reconstructed_path, "wb") as image_out:
                        image_out.write(base64.b64decode(encoded_image))
                        
                    self.global_trigger_image_path = reconstructed_path
                    fn = os.path.basename(reconstructed_path)
                    self.trigger_status_title.configure(text=f"📷 TRIGGER IMAGE BOUND: {fn.upper()}", text_color=ACCENT_GREEN)
                    # FIXED: This line now forces the clear button layout onto the screen right away
                    self.clear_img_trigger_btn.pack(side="right", padx=6, pady=2)
                else:
                    self.remove_global_trigger_image()

                self.refresh_timeline_ui()
            except Exception as error:
                messagebox.showerror("Import Error", f"Failed to open macro file: {str(error)}")

    def _action_text(self, idx, action):
        if action['type'] == 'mouse': return f" [{idx+1:02d}] Click ➔ [X:{action['rel_x']}, Y:{action['rel_y']}]"
        if action['type'] == 'pixel_wait': return f" [{idx+1:02d}] Pixel Match ➔ {action['color']}"
        if action['type'] == 'image_match_wait': return f" [{idx+1:02d}] Template Search ➔ {os.path.basename(action['image_path'])}"
        
        repeats = action.get('repeat_count', 1)
        hold_suffix = f" (Held down x{repeats})" if (not action.get('is_release') and repeats > 1) else ""
        return f" [{idx+1:02d}] Key { 'UP' if action.get('is_release') else 'DOWN' } ➔ [{action.get('name','?')}] {hold_suffix}"


if __name__ == "__main__":
    app = MacroApp()
    app.mainloop()
