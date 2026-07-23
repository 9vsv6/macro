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
import asyncio
from PIL import Image, ImageTk  

# Try importing pygame for native DirectInput/XInput controller polling hooks
try:
    import pygame
    HAS_PYGAME = True
except ImportError:
    HAS_PYGAME = False

import cv2
import numpy as np

def match_template_enhanced(screen, template, confidence=0.85, match_engine="standard", auto_fallback=True):
    """
    Advanced multi-engine template matching with support for obscured, covered,
    or partially hidden icons (e.g. badges, text overlays, shifting grass/bg).
    """
    if screen is None or template is None:
        return False, 0.0, (0, 0)
    
    sh, sw = screen.shape[:2]
    th, tw = template.shape[:2]
    if th > sh or tw > sw:
        return False, 0.0, (0, 0)
        
    try:
        if match_engine == "grayscale":
            g_screen = cv2.cvtColor(screen, cv2.COLOR_BGR2GRAY)
            g_template = cv2.cvtColor(template, cv2.COLOR_BGR2GRAY)
            res = cv2.matchTemplate(g_screen, g_template, cv2.TM_CCOEFF_NORMED)
            min_val, max_val, min_loc, max_loc = cv2.minMaxLoc(res)
            if max_val >= confidence:
                return True, max_val, max_loc

        elif match_engine in ("circle_mask", "ignore_background"):
            mask = np.zeros((th, tw), dtype=np.uint8)
            cv2.ellipse(mask, (tw // 2, th // 2), (max(1, int(tw * 0.45)), max(1, int(th * 0.45))), 0, 0, 360, 255, -1)
            try:
                res = cv2.matchTemplate(screen, template, cv2.TM_CCORR_NORMED, mask=mask)
            except Exception:
                masked_template = cv2.bitwise_and(template, template, mask=mask)
                res = cv2.matchTemplate(screen, masked_template, cv2.TM_CCOEFF_NORMED)
            min_val, max_val, min_loc, max_loc = cv2.minMaxLoc(res)
            if max_val >= confidence:
                return True, max_val, max_loc

        elif match_engine in ("hsv_color", "dominant_color"):
            hsv_tpl = cv2.cvtColor(template, cv2.COLOR_BGR2HSV)
            ch, cw = max(1, th // 4), max(1, tw // 4)
            center_hsv = hsv_tpl[ch:th-ch, cw:tw-cw]
            mean_hsv = np.mean(center_hsv, axis=(0, 1))
            
            lower_hsv = np.array([max(0, int(mean_hsv[0]) - 25), max(30, int(mean_hsv[1]) - 80), max(30, int(mean_hsv[2]) - 80)], dtype=np.uint8)
            upper_hsv = np.array([min(179, int(mean_hsv[0]) + 25), min(255, int(mean_hsv[1]) + 80), min(255, int(mean_hsv[2]) + 80)], dtype=np.uint8)
            
            hsv_screen = cv2.cvtColor(screen, cv2.COLOR_BGR2HSV)
            color_mask_screen = cv2.inRange(hsv_screen, lower_hsv, upper_hsv)
            color_mask_tpl = cv2.inRange(hsv_tpl, lower_hsv, upper_hsv)
            
            res = cv2.matchTemplate(color_mask_screen, color_mask_tpl, cv2.TM_CCORR_NORMED)
            min_val, max_val, min_loc, max_loc = cv2.minMaxLoc(res)
            target_conf = max(0.40, confidence - 0.15)
            if max_val >= target_conf:
                return True, max_val, max_loc

        # Default standard BGR match
        res = cv2.matchTemplate(screen, template, cv2.TM_CCOEFF_NORMED)
        min_val, max_val, min_loc, max_loc = cv2.minMaxLoc(res)
        if max_val >= confidence:
            return True, max_val, max_loc

        # Auto fallback for obscured icons if auto_fallback is active
        if auto_fallback:
            # 1. Circular Mask with 0.60 threshold
            mask = np.zeros((th, tw), dtype=np.uint8)
            cv2.ellipse(mask, (tw // 2, th // 2), (max(1, int(tw * 0.42)), max(1, int(th * 0.42))), 0, 0, 360, 255, -1)
            try:
                res_m = cv2.matchTemplate(screen, template, cv2.TM_CCORR_NORMED, mask=mask)
                _, max_val_m, _, max_loc_m = cv2.minMaxLoc(res_m)
                if max_val_m >= min(0.60, confidence):
                    return True, max_val_m, max_loc_m
            except Exception:
                pass

            # 2. Lower threshold tolerance (0.55) if icon is partially covered by badges or text
            if max_val >= 0.55:
                return True, max_val, max_loc

        return False, max_val, max_loc
    except Exception as e:
        print(f"Match Template Error: {e}")
        return False, 0.0, (0, 0)


# Enhanced Premium Color Palette
APP_BG = "#191919"          
PANEL_BG = "#202020"        
HEADER_BG = "#202020"       
BORDER_COLOR = "#2d2d2d"     
ACCENT_BLUE = "#0078d4"     
ACCENT_GREEN = "#107c41"    
ACCENT_RED = "#c42b1c"      
ACCENT_PURPLE = "#881798"   
TEXT_MAIN = "#ffffff"       
TEXT_MUTED = "#a0a0a0"      

ctk.set_appearance_mode("Dark")

# ── Windows API Specifications & Native Binding Engines ────────────────────────
GetForegroundWindow = ctypes.windll.user32.GetForegroundWindow
GetWindowThreadProcessId = ctypes.windll.user32.GetWindowThreadProcessId
OpenProcess = ctypes.windll.kernel32.OpenProcess if hasattr(ctypes.windll.kernel32, 'OpenProcess') else ctypes.windll.kernel32.OpenProcess
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

class POINT(ctypes.Structure):
    _fields_ = [("x", ctypes.c_long), ("y", ctypes.c_long)]

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

def get_window_pixel_color(hwnd, x, y):
    user32 = ctypes.windll.user32
    gdi32 = ctypes.windll.gdi32
    if not hwnd or not user32.IsWindow(hwnd):
        return get_screen_pixel_color(x, y)
    hdc = user32.GetWindowDC(hwnd)
    pixel = gdi32.GetPixel(hdc, int(x), int(y))
    user32.ReleaseDC(hwnd, hdc)
    return f"#{pixel & 0xFF:02x}{(pixel >> 8) & 0xFF:02x}{(pixel >> 16) & 0xFF:02x}".upper()

def send_hardware_mouse_move(target_x, target_y):
    user32 = ctypes.windll.user32
    sw = user32.GetSystemMetrics(0)
    sh = user32.GetSystemMetrics(1)
    nx = int((target_x * 65535) / (sw - 1)) if sw > 1 else 0
    ny = int((target_y * 65535) / (sh - 1)) if sh > 1 else 0
    flags = 0x8000 | 0x0001
    ii_ = Input_I()
    ii_.mi = MouseInput(nx, ny, 0, flags, 0, ctypes.pointer(ctypes.c_ulong(0)))
    command = Input(ctypes.c_ulong(0), ii_)
    SendInput(1, ctypes.pointer(command), ctypes.sizeof(command))

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
        curr_y = int((1-t_skewed)**3*start_y + 3*(1-t_skewed)**2*t_skewed*cy1 + 3*(1-t_skewed)*t_skewed**2*cy2 + t_skewed**3*target_y)
        send_hardware_mouse_move(curr_x, curr_y)
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

def send_hardware_mouse_click(button_name="left", is_release=False):
    btn = button_name.lower()
    if "right" in btn:
        flags = 0x0010 if is_release else 0x0008
    elif "middle" in btn:
        flags = 0x0040 if is_release else 0x0020
    else:
        flags = 0x0004 if is_release else 0x0002
        
    ii_ = Input_I()
    ii_.mi = MouseInput(0, 0, 0, flags, 0, ctypes.pointer(ctypes.c_ulong(0)))
    command = Input(ctypes.c_ulong(0), ii_)
    SendInput(1, ctypes.pointer(command), ctypes.sizeof(command))

def win32_screenshot(region=None):
    from PIL import Image
    user32 = ctypes.windll.user32
    gdi32 = ctypes.windll.gdi32
    
    if region:
        x, y, w, h = region
    else:
        x = 0
        y = 0
        w = user32.GetSystemMetrics(0)
        h = user32.GetSystemMetrics(1)
        
    hScreenDC = user32.GetDC(0)
    hMemDC = gdi32.CreateCompatibleDC(hScreenDC)
    hBitmap = gdi32.CreateCompatibleBitmap(hScreenDC, w, h)
    gdi32.SelectObject(hMemDC, hBitmap)
    gdi32.BitBlt(hMemDC, 0, 0, w, h, hScreenDC, x, y, 0x00CC0020)
    
    class BITMAPINFOHEADER(ctypes.Structure):
        _fields_ = [
            ('biSize', ctypes.c_ulong),
            ('biWidth', ctypes.c_long),
            ('biHeight', ctypes.c_long),
            ('biPlanes', ctypes.c_ushort),
            ('biBitCount', ctypes.c_ushort),
            ('biCompression', ctypes.c_ulong),
            ('biSizeImage', ctypes.c_ulong),
            ('biXPelsPerMeter', ctypes.c_long),
            ('biYPelsPerMeter', ctypes.c_long),
            ('biClrUsed', ctypes.c_ulong),
            ('biClrImportant', ctypes.c_ulong)
        ]
        
    bmi = BITMAPINFOHEADER()
    bmi.biSize = ctypes.sizeof(BITMAPINFOHEADER)
    bmi.biWidth = w
    bmi.biHeight = -h
    bmi.biPlanes = 1
    bmi.biBitCount = 32
    bmi.biCompression = 0
    bmi.biSizeImage = w * h * 4
    
    buffer = ctypes.create_string_buffer(bmi.biSizeImage)
    gdi32.GetDIBits(hScreenDC, hBitmap, 0, h, buffer, ctypes.byref(bmi), 0)
    
    gdi32.DeleteObject(hBitmap)
    gdi32.DeleteDC(hMemDC)
    user32.ReleaseDC(0, hScreenDC)
    
    img = Image.frombuffer("RGBA", (w, h), buffer, "raw", "BGRA", 0, 1)
    return img.convert("RGB")


def get_vk_from_key_name(key_name):
    key_map = {
        "SPACE": 0x20, "ENTER": 0x0D, "ESC": 0x1B, "TAB": 0x09, "BACKSPACE": 0x08,
        "SHIFT": 0xA0, "CTRL": 0xA2, "ALT": 0xA4, "CAPS": 0x14,
        "UP": 0x26, "DOWN": 0x28, "LEFT": 0x25, "RIGHT": 0x27
    }
    k_upper = key_name.upper().strip()
    if k_upper in key_map:
        return key_map[k_upper]
    if len(k_upper) == 1:
        return ord(k_upper)
    return None

class CTKTooltip:
    def __init__(self, widget, text):
        self.widget = widget
        self.text = text
        self.tooltip_window = None
        self.widget.bind("<Enter>", self.show_tooltip)
        self.widget.bind("<Leave>", self.hide_tooltip)

    def show_tooltip(self, event=None):
        if self.tooltip_window or not self.text:
            return
        x = self.widget.winfo_rootx() + 20
        y = self.widget.winfo_rooty() + self.widget.winfo_height() + 5
        self.tooltip_window = tw = Toplevel(self.widget)
        tw.wm_overrideredirect(True)
        tw.wm_geometry(f"+{x}+{y}")
        tw.attributes("-topmost", True)
        tw.configure(bg="#1e1e24")
        
        from tkinter import Label, Frame
        inner = Frame(tw, bg="#18181b")
        inner.pack(padx=1, pady=1)
        
        label = Label(inner, text=self.text, justify="left", bg="#18181b", fg="#f4f4f5",
                      font=("Segoe UI", 9), padx=8, pady=4)
        label.pack()

    def hide_tooltip(self, event=None):
        tw = self.tooltip_window
        self.tooltip_window = None
        if tw:
            tw.destroy()


class IconActionChoiceModal(Toplevel):
    def __init__(self, parent, on_select, image_path=None):
        super().__init__(parent)
        self.parent = parent
        self.on_select = on_select
        self.image_path = image_path
        self.title("Icon Detection Settings & Action")
        
        has_preview = bool(image_path and os.path.exists(image_path))
        self.geometry("420x430" if has_preview else "420x330")
        self.resizable(False, False)
        self.configure(bg="#09090b")
        self.attributes("-topmost", True)
        self.transient(parent)
        self.grab_set()
        
        self.update_idletasks()
        px = parent.winfo_x() + (parent.winfo_width() // 2) - 210
        py = parent.winfo_y() + (parent.winfo_height() // 2) - (215 if has_preview else 165)
        self.geometry(f"+{px}+{py}")
        
        frame = ctk.CTkFrame(self, fg_color="#09090b")
        frame.pack(fill="both", expand=True, padx=15, pady=15)
        
        if has_preview:
            try:
                from PIL import Image
                img = Image.open(image_path)
                img.thumbnail((160, 70))
                ctk_img = ctk.CTkImage(light_image=img, dark_image=img, size=(img.width, img.height))
                
                preview_card = ctk.CTkFrame(frame, fg_color="#121214", border_color="#2b2d31", border_width=1, corner_radius=8)
                preview_card.pack(fill="x", pady=(0, 10))
                
                ctk.CTkLabel(preview_card, text="📸 Target Sniped Icon Target:", font=ctk.CTkFont(size=11, weight="bold"), text_color="#a1a1aa").pack(anchor="w", padx=10, pady=(4, 2))
                
                img_lbl = ctk.CTkLabel(preview_card, image=ctk_img, text="")
                img_lbl.image = ctk_img
                img_lbl.pack(pady=(2, 6))
            except Exception as e:
                print(f"Modal image preview error: {e}")
        
        lbl = ctk.CTkLabel(frame, text="Select Behavior on Icon Match:", font=ctk.CTkFont(size=12, weight="bold"), text_color="#f4f4f5")
        lbl.pack(anchor="w", pady=(0, 6))
        
        btn_frame = ctk.CTkFrame(frame, fg_color="transparent")
        btn_frame.pack(fill="x", pady=(0, 12))
        
        self.choice = "click"
        
        def set_choice(c):
            self.choice = c
            click_btn.configure(fg_color="#7c3aed" if c == 'click' else "#2b2d31")
            hover_btn.configure(fg_color="#7c3aed" if c == 'hover' else "#2b2d31")
            key_btn.configure(fg_color="#7c3aed" if c == 'press_key' else "#2b2d31")
            
        click_btn = ctk.CTkButton(
            btn_frame, 
            text="🖱️ Left Click", 
            fg_color="#7c3aed", 
            hover_color="#6d28d9", 
            text_color="#f4f4f5",
            font=ctk.CTkFont(size=11, weight="bold"),
            width=110,
            command=lambda: set_choice('click')
        )
        click_btn.pack(side="left", padx=2, expand=True)
        
        hover_btn = ctk.CTkButton(
            btn_frame, 
            text="👁️ Hover Only", 
            fg_color="#2b2d31", 
            hover_color="#3d4047", 
            text_color="#f4f4f5",
            font=ctk.CTkFont(size=11, weight="bold"),
            width=110,
            command=lambda: set_choice('hover')
        )
        hover_btn.pack(side="left", padx=2, expand=True)
        
        key_btn = ctk.CTkButton(
            btn_frame, 
            text="⌨️ Press Key", 
            fg_color="#2b2d31", 
            hover_color="#3d4047", 
            text_color="#f4f4f5",
            font=ctk.CTkFont(size=11, weight="bold"),
            width=110,
            command=lambda: set_choice('press_key')
        )
        key_btn.pack(side="left", padx=2, expand=True)
        
        # Obscured / Tolerance Level Option
        ctk.CTkLabel(frame, text="🛡️ Icon Obscured / Tolerance Mode:", font=ctk.CTkFont(size=11, weight="bold"), text_color="#10b981").pack(anchor="w", pady=(4, 2))
        
        self.tolerance_var = ctk.StringVar(value="Obscured / Behind Badges (60% Confidence)")
        tolerance_menu = ctk.CTkOptionMenu(
            frame,
            values=[
                "Standard Clear Icon (85% Confidence)",
                "Obscured / Behind Badges (60% Confidence)",
                "Heavy Occlusion / Covered (50% Confidence)"
            ],
            variable=self.tolerance_var,
            fg_color="#1e1f22",
            button_color="#2b2d31",
            button_hover_color="#3d4047",
            dropdown_fg_color="#18181b"
        )
        tolerance_menu.pack(fill="x", pady=(0, 10))

        # Match Strategy Option
        ctk.CTkLabel(frame, text="🎨 Detection Strategy:", font=ctk.CTkFont(size=11, weight="bold"), text_color="#f4f4f5").pack(anchor="w", pady=(2, 2))
        
        self.strategy_var = ctk.StringVar(value="Circle Mask (Ignore Corner Background)")
        strategy_menu = ctk.CTkOptionMenu(
            frame,
            values=[
                "Standard BGR Color",
                "Circle Mask (Ignore Corner Background)",
                "Grayscale (Lighting/Shadow Tolerant)",
                "Dominant Color (HSV Filter)"
            ],
            variable=self.strategy_var,
            fg_color="#1e1f22",
            button_color="#2b2d31",
            button_hover_color="#3d4047",
            dropdown_fg_color="#18181b"
        )
        strategy_menu.pack(fill="x", pady=(0, 12))

        confirm_btn = ctk.CTkButton(
            frame,
            text="✔ Confirm & Save Action",
            fg_color="#10b981",
            hover_color="#059669",
            font=ctk.CTkFont(size=12, weight="bold"),
            height=34,
            command=self.submit
        )
        confirm_btn.pack(fill="x", pady=(4, 0))

    def submit(self):
        conf_map = {
            "Standard Clear Icon (85% Confidence)": 0.85,
            "Obscured / Behind Badges (60% Confidence)": 0.60,
            "Heavy Occlusion / Covered (50% Confidence)": 0.50
        }
        strat_map = {
            "Standard BGR Color": "standard",
            "Circle Mask (Ignore Corner Background)": "circle_mask",
            "Grayscale (Lighting/Shadow Tolerant)": "grayscale",
            "Dominant Color (HSV Filter)": "hsv_color"
        }
        
        conf = conf_map.get(self.tolerance_var.get(), 0.60)
        engine = strat_map.get(self.strategy_var.get(), "circle_mask")
        
        self.destroy()
        self.on_select({
            'behavior': self.choice,
            'confidence': conf,
            'match_engine': engine
        })


def detect_object_bounds_at_point(click_x, click_y, margin=6):
    """
    Takes a screenshot around (click_x, click_y) and uses edge detection + contours
    to automatically find the exact bounding box of the full object (button, icon, badge).
    """
    user32 = ctypes.windll.user32
    sw = user32.GetSystemMetrics(0)
    sh = user32.GetSystemMetrics(1)

    roi_size = 360
    rx1 = max(0, click_x - roi_size // 2)
    ry1 = max(0, click_y - roi_size // 2)
    rx2 = min(sw, click_x + roi_size // 2)
    ry2 = min(sh, click_y + roi_size // 2)
    rw = rx2 - rx1
    rh = ry2 - ry1

    if rw <= 10 or rh <= 10:
        return (max(0, click_x - 30), max(0, click_y - 30), 60, 60)

    try:
        full_shot = win32_screenshot((rx1, ry1, rw, rh))
        img = cv2.cvtColor(np.array(full_shot), cv2.COLOR_RGB2BGR)

        local_cx = click_x - rx1
        local_cy = click_y - ry1

        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        blurred = cv2.GaussianBlur(gray, (5, 5), 0)

        best_rect = None
        min_dist_to_center = float('inf')

        methods = []
        edges_canny = cv2.Canny(blurred, 30, 150)
        methods.append(edges_canny)

        _, thresh_otsu = cv2.threshold(blurred, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        methods.append(thresh_otsu)
        methods.append(cv2.bitwise_not(thresh_otsu))

        for bin_img in methods:
            contours, _ = cv2.findContours(bin_img, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            for c in contours:
                area = cv2.contourArea(c)
                if area < 100 or area > (rw * rh * 0.88):
                    continue
                x, y, w, h = cv2.boundingRect(c)
                if (x - 12 <= local_cx <= x + w + 12) and (y - 12 <= local_cy <= y + h + 12):
                    box_cx = x + w / 2
                    box_cy = y + h / 2
                    dist = math.hypot(box_cx - local_cx, box_cy - local_cy)
                    if dist < min_dist_to_center:
                        min_dist_to_center = dist
                        best_rect = (x, y, w, h)

        if best_rect:
            bx, by, bw, bh = best_rect
            final_x = max(0, rx1 + bx - margin)
            final_y = max(0, ry1 + by - margin)
            final_w = min(sw - final_x, bw + margin * 2)
            final_h = min(sh - final_y, bh + margin * 2)
            return (final_x, final_y, final_w, final_h)
    except Exception as e:
        print(f"Smart Select Error: {e}")

    return (max(0, click_x - 32), max(0, click_y - 32), 64, 64)


class ScreenSnipper(Toplevel):
    def __init__(self, parent, callback):
        super().__init__(parent)
        self.parent = parent
        self.callback = callback
        self.snipe_mode = "rectangle" # Modes: "rectangle", "smart_object", "window"
        
        self.attributes("-alpha", 0.35, "-fullscreen", True, "-topmost", True)
        self.config(cursor="cross")
        self.canvas = Canvas(self, cursor="cross", bg="black", highlightthickness=0)
        self.canvas.pack(fill="both", expand=True)
        
        self.canvas.bind("<ButtonPress-1>", self.on_press)
        self.canvas.bind("<B1-Motion>", self.on_drag)
        self.canvas.bind("<ButtonRelease-1>", self.on_release)
        self.bind("<Escape>", self.on_escape)
        self.start_x = self.start_y = self.rect = None

        self.setup_floating_toolbar()

    def setup_floating_toolbar(self):
        user32 = ctypes.windll.user32
        sw = user32.GetSystemMetrics(0)
        
        toolbar_w = 510
        toolbar_h = 44
        pos_x = max(10, (sw // 2) - (toolbar_w // 2))
        pos_y = 15
        
        self.toolbar_frame = ctk.CTkFrame(
            self,
            width=toolbar_w,
            height=toolbar_h,
            fg_color="#121214",
            border_color="#2b2d31",
            border_width=1.5,
            corner_radius=22
        )
        self.toolbar_frame.place(x=pos_x, y=pos_y)
        self.toolbar_frame.pack_propagate(False)

        btn_box = ctk.CTkFrame(self.toolbar_frame, fg_color="transparent")
        btn_box.pack(fill="both", expand=True, padx=8, pady=4)

        self.btn_rect = ctk.CTkButton(
            btn_box,
            text="🔳 Rectangle",
            font=ctk.CTkFont(size=11, weight="bold"),
            fg_color="#8b5cf6",
            hover_color="#7c3aed",
            height=30,
            width=95,
            command=lambda: self.set_mode("rectangle")
        )
        self.btn_rect.pack(side="left", padx=2, expand=True)

        self.btn_smart = ctk.CTkButton(
            btn_box,
            text="🪄 Smart Object",
            font=ctk.CTkFont(size=11, weight="bold"),
            fg_color="#2b2d31",
            hover_color="#3d4047",
            height=30,
            width=110,
            command=lambda: self.set_mode("smart_object")
        )
        self.btn_smart.pack(side="left", padx=2, expand=True)

        self.btn_win = ctk.CTkButton(
            btn_box,
            text="🪟 Window",
            font=ctk.CTkFont(size=11, weight="bold"),
            fg_color="#2b2d31",
            hover_color="#3d4047",
            height=30,
            width=85,
            command=lambda: self.set_mode("window")
        )
        self.btn_win.pack(side="left", padx=2, expand=True)

        self.btn_full = ctk.CTkButton(
            btn_box,
            text="🖥️ Full Screen",
            font=ctk.CTkFont(size=11, weight="bold"),
            fg_color="#2b2d31",
            hover_color="#3d4047",
            height=30,
            width=95,
            command=self.snip_fullscreen
        )
        self.btn_full.pack(side="left", padx=2, expand=True)

        close_btn = ctk.CTkButton(
            btn_box,
            text="✕",
            font=ctk.CTkFont(size=12, weight="bold"),
            fg_color="transparent",
            hover_color="#ef4444",
            text_color="#a1a1aa",
            height=30,
            width=28,
            command=self.on_escape
        )
        close_btn.pack(side="right", padx=2)

    def set_mode(self, mode):
        self.snipe_mode = mode
        active_color = "#8b5cf6"
        inactive_color = "#2b2d31"
        self.btn_rect.configure(fg_color=active_color if mode == "rectangle" else inactive_color)
        self.btn_smart.configure(fg_color=active_color if mode == "smart_object" else inactive_color)
        self.btn_win.configure(fg_color=active_color if mode == "window" else inactive_color)

    def on_press(self, e):
        try:
            tb_x = self.toolbar_frame.winfo_x()
            tb_y = self.toolbar_frame.winfo_y()
            tb_w = self.toolbar_frame.winfo_width()
            tb_h = self.toolbar_frame.winfo_height()
            if tb_x <= e.x <= tb_x + tb_w and tb_y <= e.y <= tb_y + tb_h:
                return
        except Exception:
            pass

        self.start_x, self.start_y = e.x, e.y
        if self.rect:
            try: self.canvas.delete(self.rect)
            except Exception: pass

        if self.snipe_mode == "smart_object":
            x, y, w, h = detect_object_bounds_at_point(e.x, e.y)
            self.rect = self.canvas.create_rectangle(x, y, x + w, y + h, outline="#10b981", width=3)
            self.after(120, lambda: self.finish_snip(x, y, w, h))

        elif self.snipe_mode == "window":
            pt = POINT(e.x, e.y)
            user32 = ctypes.windll.user32
            hwnd = user32.WindowFromPoint(pt)
            if hwnd:
                rect = RECT()
                if GetWindowRect(hwnd, ctypes.byref(rect)):
                    wx, wy = rect.left, rect.top
                    ww = rect.right - rect.left
                    wh = rect.bottom - rect.top
                    self.rect = self.canvas.create_rectangle(wx, wy, wx + ww, wy + wh, outline="#0078d4", width=3)
                    self.after(120, lambda: self.finish_snip(wx, wy, ww, wh))
                    return
            self.rect = self.canvas.create_rectangle(e.x, e.y, e.x, e.y, outline="#7c3aed", width=2)
        else:
            self.rect = self.canvas.create_rectangle(e.x, e.y, e.x, e.y, outline="#7c3aed", width=2)

    def on_drag(self, e):
        if self.snipe_mode == "rectangle" and self.rect and self.start_x is not None:
            self.canvas.coords(self.rect, self.start_x, self.start_y, e.x, e.y)

    def on_release(self, e):
        if self.start_x is None:
            return

        x1, y1, x2, y2 = min(self.start_x, e.x), min(self.start_y, e.y), max(self.start_x, e.x), max(self.start_y, e.y)
        w = x2 - x1
        h = y2 - y1

        if self.snipe_mode == "rectangle":
            if w > 5 and h > 5:
                self.finish_snip(x1, y1, w, h)
            else:
                # Single click in rectangle mode: smart auto-select object around click!
                sx, sy, sw, sh = detect_object_bounds_at_point(e.x, e.y)
                self.finish_snip(sx, sy, sw, sh)

    def snip_fullscreen(self):
        user32 = ctypes.windll.user32
        sw = user32.GetSystemMetrics(0)
        sh = user32.GetSystemMetrics(1)
        self.finish_snip(0, 0, sw, sh)

    def finish_snip(self, x, y, w, h):
        self.withdraw()
        self.update()
        time.sleep(0.12)
        self.destroy()
        if w > 3 and h > 3:
            self.callback(x, y, w, h)
        else:
            if self.parent:
                self.parent.deiconify()

    def on_escape(self, event=None):
        self.destroy()
        if self.parent:
            self.parent.deiconify()

class LiveHUD(Toplevel):
    def __init__(self, parent, state, stop_callback):
        super().__init__(parent)
        self.parent = parent
        self.overrideredirect(True)
        self.attributes("-topmost", True, "-alpha", 0.85)
        self.geometry("340x110+40+40")
        self.configure(bg="#09090b")
        
        self._drag_data = {"x": 0, "y": 0}
        self.bind("<ButtonPress-1>", self.start_drag)
        self.bind("<B1-Motion>", self.drag_motion)
        
        status_color = "#10b981" if state == "running" else "#ef4444"
        status_label = "● RUNNING SEQUENCE" if state == "running" else "● RECORDING SEQUENCE"
        
        self.border = Canvas(self, width=340, height=110, bg="#09090b", highlightthickness=1.5, highlightbackground=status_color)
        self.border.pack(fill="both", expand=True)
        
        self.border.create_rectangle(0, 0, 340, 28, fill="#121214", outline="")
        self.status_text = self.border.create_text(15, 14, text=status_label, font=("Segoe UI", 10, "bold"), fill=status_color, anchor="w")
        self.stats_text = self.border.create_text(15, 48, text="Loops: 0  |  Runtime: 00:00", font=("Consolas", 10, "bold"), fill="#f4f4f5", anchor="w")
        self.action_text = self.border.create_text(15, 78, text="Action: Initializing...", font=("Segoe UI", 9), fill="#a1a1aa", anchor="w")
        
        btn = ctk.CTkButton(self, text="STOP", width=60, height=24, fg_color="#dc2626", hover_color="#b91c1c", font=ctk.CTkFont(family="Segoe UI", size=10, weight="bold"), command=stop_callback)
        btn.place(x=265, y=2)
        
        self.start_time = time.time()
        self.loops = 0
        self.state = state
        self.captured_count = 0
        
        self.update_timer()

    def start_drag(self, event):
        self._drag_data = {"x": event.x, "y": event.y}

    def drag_motion(self, event):
        deltax = event.x - self._drag_data["x"]
        deltay = event.y - self._drag_data["y"]
        x = self.winfo_x() + deltax
        y = self.winfo_y() + deltay
        self.geometry(f"+{x}+{y}")

    def update_timer(self):
        try:
            elapsed = int(time.time() - self.start_time)
            m, s = divmod(elapsed, 60)
            time_str = f"{m:02d}:{s:02d}"
            
            if self.state == "running":
                self.border.itemconfig(self.stats_text, text=f"Loops: {self.loops}  |  Runtime: {time_str}")
            else:
                self.border.itemconfig(self.stats_text, text=f"Captured: {self.captured_count}  |  Runtime: {time_str}")
                
            self.after(1000, self.update_timer)
        except Exception:
            pass

    def set_active_action(self, desc):
        try:
            if len(desc) > 38:
                desc = desc[:35] + "..."
            self.border.itemconfig(self.action_text, text=f"Action: {desc}")
        except Exception:
            pass

    def set_loops(self, count):
        self.loops = count

    def set_captured_count(self, count):
        self.captured_count = count

class ActionEditorModal(Toplevel):
    def __init__(self, parent, index, action, save_callback):
        super().__init__(parent)
        self.title(f"Node #{index+1} Editor - {action['type'].replace('_',' ').upper()}")
        self.geometry("450x570")
        self.resizable(False, False)
        self.configure(bg="#121214")
        self.transient(parent)
        self.grab_set()
        
        self.action = action
        self.save_callback = save_callback
        
        # Frame
        main_frame = ctk.CTkFrame(self, fg_color="#121214")
        main_frame.pack(fill="both", expand=True, padx=20, pady=20)
        
        # Delay (Generic)
        ctk.CTkLabel(main_frame, text="Delay (seconds):", font=ctk.CTkFont(weight="bold")).pack(anchor="w", pady=(5, 2))
        self.delay_ent = ctk.CTkEntry(main_frame, fg_color="#09090b", border_color="#1e1e24")
        self.delay_ent.insert(0, f"{action.get('delay', 0.1):.2f}")
        self.delay_ent.pack(fill="x", pady=(0, 10))
        
        self.fields = {}
        
        if action['type'] == 'mouse':
            # Checkbox: Record Mouse Coordinates (X/Y)
            self.use_coords_var = ctk.StringVar(value="on" if action.get('use_coords', True) else "off")
            
            def toggle_coords_fields():
                if self.use_coords_var.get() == "on":
                    x_lbl.pack(anchor="w", pady=(5, 2))
                    x_ent.pack(fill="x", pady=(0, 10))
                    y_lbl.pack(anchor="w", pady=(5, 2))
                    y_ent.pack(fill="x", pady=(0, 10))
                else:
                    x_lbl.pack_forget()
                    x_ent.pack_forget()
                    y_lbl.pack_forget()
                    y_ent.pack_forget()
            
            coords_cb = ctk.CTkCheckBox(main_frame, text="Use exact X/Y coordinates", variable=self.use_coords_var, onvalue="on", offvalue="off", command=toggle_coords_fields)
            coords_cb.pack(anchor="w", pady=5)
            
            # X coord
            x_lbl = ctk.CTkLabel(main_frame, text="Relative X:", font=ctk.CTkFont(weight="bold"))
            x_ent = ctk.CTkEntry(main_frame, fg_color="#09090b", border_color="#1e1e24")
            x_ent.insert(0, str(action.get('rel_x') if action.get('rel_x') is not None else 0))
            self.fields['rel_x'] = x_ent
            
            # Y coord
            y_lbl = ctk.CTkLabel(main_frame, text="Relative Y:", font=ctk.CTkFont(weight="bold"))
            y_ent = ctk.CTkEntry(main_frame, fg_color="#09090b", border_color="#1e1e24")
            y_ent.insert(0, str(action.get('rel_y') if action.get('rel_y') is not None else 0))
            self.fields['rel_y'] = y_ent
            
            toggle_coords_fields()
            
        elif action['type'] == 'keyboard':
            # VK code
            ctk.CTkLabel(main_frame, text="Virtual Key Code (VK):", font=ctk.CTkFont(weight="bold")).pack(anchor="w", pady=(5, 2))
            vk_ent = ctk.CTkEntry(main_frame, fg_color="#09090b", border_color="#1e1e24")
            vk_ent.insert(0, str(action.get('vk', 0)))
            vk_ent.pack(fill="x", pady=(0, 10))
            self.fields['vk'] = vk_ent
            
            # Key name
            ctk.CTkLabel(main_frame, text="Key Name:", font=ctk.CTkFont(weight="bold")).pack(anchor="w", pady=(5, 2))
            name_ent = ctk.CTkEntry(main_frame, fg_color="#09090b", border_color="#1e1e24")
            name_ent.insert(0, str(action.get('name', '')))
            name_ent.pack(fill="x", pady=(0, 10))
            self.fields['name'] = name_ent
            
            # Release checkbox
            self.rel_var = ctk.StringVar(value="on" if action.get('is_release', False) else "off")
            rel_cb = ctk.CTkCheckBox(main_frame, text="Is Key Release Event", variable=self.rel_var, onvalue="on", offvalue="off")
            rel_cb.pack(anchor="w", pady=5)
            
        elif action['type'] == 'image_match_wait':
            if action.get('image_path') and os.path.exists(action['image_path']):
                try:
                    from PIL import Image
                    img = Image.open(action['image_path'])
                    img.thumbnail((160, 65))
                    ctk_img = ctk.CTkImage(light_image=img, dark_image=img, size=(img.width, img.height))
                    
                    preview_card = ctk.CTkFrame(main_frame, fg_color="#09090b", border_color="#1e1e24", border_width=1, corner_radius=8)
                    preview_card.pack(fill="x", pady=(0, 10))
                    
                    ctk.CTkLabel(preview_card, text="📸 Target Sniped Icon Target:", font=ctk.CTkFont(size=11, weight="bold"), text_color="#a1a1aa").pack(anchor="w", padx=10, pady=(4, 2))
                    
                    img_lbl = ctk.CTkLabel(preview_card, image=ctk_img, text="")
                    img_lbl.image = ctk_img
                    img_lbl.pack(pady=(2, 6))
                except Exception as e:
                    pass

            # Confidence
            ctk.CTkLabel(main_frame, text="Matching Confidence Threshold (0.30 - 1.00):", font=ctk.CTkFont(weight="bold")).pack(anchor="w", pady=(5, 2))
            conf_ent = ctk.CTkEntry(main_frame, fg_color="#09090b", border_color="#1e1e24")
            conf_ent.insert(0, f"{action.get('confidence', 0.85):.2f}")
            conf_ent.pack(fill="x", pady=(0, 2))
            self.fields['confidence'] = conf_ent

            ctk.CTkLabel(main_frame, text="💡 Tip: Lower confidence (0.55-0.65) if icon is behind badges/text/objects.", font=ctk.CTkFont(size=10), text_color="#a1a1aa").pack(anchor="w", pady=(0, 8))

            # Match Engine Dropdown
            ctk.CTkLabel(main_frame, text="Detection Strategy (For Obscured Icons):", font=ctk.CTkFont(weight="bold")).pack(anchor="w", pady=(5, 2))
            engine_map = {
                "standard": "Standard BGR Color",
                "circle_mask": "Circle Mask (Ignore Corner Background)",
                "grayscale": "Grayscale (Lighting/Shadow Tolerant)",
                "hsv_color": "Dominant Color (HSV Filter)"
            }
            curr_engine = action.get('match_engine', 'standard')
            self.engine_var = ctk.StringVar(value=engine_map.get(curr_engine, "Standard BGR Color"))
            engine_menu = ctk.CTkOptionMenu(
                main_frame,
                values=list(engine_map.values()),
                variable=self.engine_var,
                fg_color="#2b2d31",
                button_color="#2b2d31",
                button_hover_color="#3d4047",
                dropdown_fg_color="#1e1f22"
            )
            engine_menu.pack(fill="x", pady=(0, 10))
            
            # Match Behavior Dropdown
            ctk.CTkLabel(main_frame, text="Action on Match:", font=ctk.CTkFont(weight="bold")).pack(anchor="w", pady=(5, 2))
            
            behavior_map = {
                "wait": "Wait Only (Pause sequence)",
                "hover": "Hover Only (Move cursor to icon)",
                "click": "Click Mouse (Left Click center)",
                "press_key": "Press Key (Execute keystroke)"
            }
            
            current_behavior = action.get('match_behavior')
            if not current_behavior:
                if action.get('click_on_match', False):
                    current_behavior = "press_key" if action.get('key_to_press') else "click"
                else:
                    current_behavior = "wait"
            
            self.behavior_var = ctk.StringVar(value=behavior_map.get(current_behavior, "Wait Only (Pause sequence)"))
            
            # Key to press widgets
            key_label = ctk.CTkLabel(main_frame, text="Keyboard Key to Press:", font=ctk.CTkFont(weight="bold"))
            key_ent = ctk.CTkEntry(main_frame, fg_color="#09090b", border_color="#1e1e24", placeholder_text="e.g. E, Space, Enter")
            key_ent.insert(0, str(action.get('key_to_press') or ''))
            self.fields['key_to_press'] = key_ent
            
            def on_behavior_change(val):
                if val == "Press Key (Execute keystroke)":
                    key_label.pack(anchor="w", pady=(5, 2))
                    key_ent.pack(fill="x", pady=(0, 10))
                else:
                    key_label.pack_forget()
                    key_ent.pack_forget()
                    
            behavior_menu = ctk.CTkOptionMenu(
                main_frame, 
                values=["Wait Only (Pause sequence)", "Hover Only (Move cursor to icon)", "Click Mouse (Left Click center)", "Press Key (Execute keystroke)"], 
                variable=self.behavior_var,
                command=on_behavior_change,
                fg_color="#2b2d31",
                button_color="#2b2d31",
                button_hover_color="#3d4047",
                dropdown_fg_color="#1e1f22"
            )
            behavior_menu.pack(fill="x", pady=(0, 10))
            
            # Click Target Position Dropdown
            ctk.CTkLabel(main_frame, text="Click/Hover Target Position:", font=ctk.CTkFont(weight="bold")).pack(anchor="w", pady=(5, 2))
            self.click_pos_var = ctk.StringVar(value=action.get('click_position', 'Center'))
            click_pos_menu = ctk.CTkOptionMenu(
                main_frame,
                values=["Center", "Top-Left", "Top-Right", "Bottom-Left", "Bottom-Right", "Random Corner"],
                variable=self.click_pos_var,
                fg_color="#2b2d31",
                button_color="#2b2d31",
                button_hover_color="#3d4047",
                dropdown_fg_color="#1e1f22"
            )
            click_pos_menu.pack(fill="x", pady=(0, 10))
            
            # Show/hide initially
            if self.behavior_var.get() == "Press Key (Execute keystroke)":
                key_label.pack(anchor="w", pady=(5, 2))
                key_ent.pack(fill="x", pady=(0, 10))
                
            self.add_conditional_fields(main_frame, action)
            
        elif action['type'] == 'pixel_wait':
            # X coord
            ctk.CTkLabel(main_frame, text="Relative X:", font=ctk.CTkFont(weight="bold")).pack(anchor="w", pady=(5, 2))
            x_ent = ctk.CTkEntry(main_frame, fg_color="#09090b", border_color="#1e1e24")
            x_ent.insert(0, str(action.get('rel_x', 0)))
            x_ent.pack(fill="x", pady=(0, 10))
            self.fields['rel_x'] = x_ent
            
            # Y coord
            ctk.CTkLabel(main_frame, text="Relative Y:", font=ctk.CTkFont(weight="bold")).pack(anchor="w", pady=(5, 2))
            y_ent = ctk.CTkEntry(main_frame, fg_color="#09090b", border_color="#1e1e24")
            y_ent.insert(0, str(action.get('rel_y', 0)))
            y_ent.pack(fill="x", pady=(0, 10))
            self.fields['rel_y'] = y_ent
            
            # Target color
            ctk.CTkLabel(main_frame, text="Target Hex Color:", font=ctk.CTkFont(weight="bold")).pack(anchor="w", pady=(5, 2))
            color_ent = ctk.CTkEntry(main_frame, fg_color="#09090b", border_color="#1e1e24")
            color_ent.insert(0, str(action.get('color', '#FFFFFF')))
            color_ent.pack(fill="x", pady=(0, 10))
            self.fields['color'] = color_ent
            
            self.add_conditional_fields(main_frame, action)
            
        elif action['type'] in ('ocr_wait', 'ocr_click'):
            # Region (x, y, w, h)
            ctk.CTkLabel(main_frame, text="Region Bounds (X, Y, W, H):", font=ctk.CTkFont(weight="bold")).pack(anchor="w", pady=(5, 2))
            reg_frame = ctk.CTkFrame(main_frame, fg_color="transparent")
            reg_frame.pack(fill="x", pady=(0, 10))
            
            rx, ry, rw, rh = action.get('region', (0,0,100,100))
            rx_ent = ctk.CTkEntry(reg_frame, width=80, fg_color="#09090b", border_color="#1e1e24")
            rx_ent.insert(0, str(rx)); rx_ent.pack(side="left", padx=2)
            ry_ent = ctk.CTkEntry(reg_frame, width=80, fg_color="#09090b", border_color="#1e1e24")
            ry_ent.insert(0, str(ry)); ry_ent.pack(side="left", padx=2)
            rw_ent = ctk.CTkEntry(reg_frame, width=80, fg_color="#09090b", border_color="#1e1e24")
            rw_ent.insert(0, str(rw)); rw_ent.pack(side="left", padx=2)
            rh_ent = ctk.CTkEntry(reg_frame, width=80, fg_color="#09090b", border_color="#1e1e24")
            rh_ent.insert(0, str(rh)); rh_ent.pack(side="left", padx=2)
            self.fields['region'] = (rx_ent, ry_ent, rw_ent, rh_ent)
            
            # Text query
            label_text = "Text to Search & Click:" if action['type'] == 'ocr_click' else "Text to Wait For:"
            ctk.CTkLabel(main_frame, text=label_text, font=ctk.CTkFont(weight="bold")).pack(anchor="w", pady=(5, 2))
            query_ent = ctk.CTkEntry(main_frame, fg_color="#09090b", border_color="#1e1e24")
            query_ent.insert(0, str(action.get('text_query', '')))
            query_ent.pack(fill="x", pady=(0, 10))
            self.fields['text_query'] = query_ent
            
            self.add_conditional_fields(main_frame, action)
            
        # Button frame
        btn_frame = ctk.CTkFrame(main_frame, fg_color="transparent")
        btn_frame.pack(fill="x", side="bottom", pady=10)
        
        ctk.CTkButton(btn_frame, text="Save Changes", fg_color="#8b5cf6", hover_color="#6d28d9", font=ctk.CTkFont(weight="bold"), command=self.save).pack(side="left", expand=True, fill="x", padx=5)
        ctk.CTkButton(btn_frame, text="Cancel", fg_color="#2b2d31", hover_color="#3d4047", command=self.destroy).pack(side="right", expand=True, fill="x", padx=5)

    def add_conditional_fields(self, parent, action):
        self.cond_var = ctk.StringVar(value="on" if action.get('is_conditional', False) else "off")
        cond_cb = ctk.CTkCheckBox(parent, text="Is branching conditional check (Check once)", variable=self.cond_var, onvalue="on", offvalue="off")
        cond_cb.pack(anchor="w", pady=5)
        
        goto_frame = ctk.CTkFrame(parent, fg_color="transparent")
        goto_frame.pack(fill="x", pady=5)
        
        ctk.CTkLabel(goto_frame, text="If True Goto Node #:").pack(side="left", padx=2)
        gt_ent = ctk.CTkEntry(goto_frame, width=50, fg_color="#09090b", border_color="#1e1e24")
        gt_ent.insert(0, str(action.get('goto_true') or ''))
        gt_ent.pack(side="left", padx=5)
        self.fields['goto_true'] = gt_ent
        
        ctk.CTkLabel(goto_frame, text="If False Goto Node #:").pack(side="left", padx=2)
        gf_ent = ctk.CTkEntry(goto_frame, width=50, fg_color="#09090b", border_color="#1e1e24")
        gf_ent.insert(0, str(action.get('goto_false') or ''))
        gf_ent.pack(side="left", padx=5)
        self.fields['goto_false'] = gf_ent

    def save(self):
        try:
            self.action['delay'] = float(self.delay_ent.get())
        except ValueError:
            pass
            
        for k, v in self.fields.items():
            if k == 'region':
                try:
                    self.action['region'] = (int(v[0].get()), int(v[1].get()), int(v[2].get()), int(v[3].get()))
                except ValueError:
                    pass
            elif k in ('rel_x', 'rel_y', 'vk'):
                try:
                    self.action[k] = int(v.get())
                except ValueError:
                    pass
            elif k in ('confidence'):
                try:
                    self.action[k] = float(v.get())
                except ValueError:
                    pass
            elif k in ('goto_true', 'goto_false'):
                val = v.get().strip()
                self.action[k] = int(val) if val.isdigit() else None
            else:
                self.action[k] = v.get()
                
        if 'key_to_press' in self.action:
            val = str(self.action['key_to_press']).strip()
            self.action['key_to_press'] = val.upper() if val else None
                
        if hasattr(self, 'engine_var'):
            engine_map_rev = {
                "Standard BGR Color": "standard",
                "Circle Mask (Ignore Corner Background)": "circle_mask",
                "Grayscale (Lighting/Shadow Tolerant)": "grayscale",
                "Dominant Color (HSV Filter)": "hsv_color"
            }
            self.action['match_engine'] = engine_map_rev.get(self.engine_var.get(), "standard")
            
        if hasattr(self, 'rel_var'):
            self.action['is_release'] = (self.rel_var.get() == "on")
        if hasattr(self, 'use_coords_var'):
            self.action['use_coords'] = (self.use_coords_var.get() == "on")
            if not self.action['use_coords']:
                self.action['rel_x'] = None
                self.action['rel_y'] = None
        if hasattr(self, 'behavior_var'):
            behavior_map_rev = {
                "Wait Only (Pause sequence)": "wait",
                "Hover Only (Move cursor to icon)": "hover",
                "Click Mouse (Left Click center)": "click",
                "Press Key (Execute keystroke)": "press_key"
            }
            beh = behavior_map_rev.get(self.behavior_var.get(), "wait")
            self.action['match_behavior'] = beh
            self.action['click_on_match'] = (beh in ("click", "press_key", "hover"))
        if hasattr(self, 'click_pos_var'):
            self.action['click_position'] = self.click_pos_var.get()
        if hasattr(self, 'cond_var'):
            self.action['is_conditional'] = (self.cond_var.get() == "on")
            
        self.save_callback()
        self.destroy()

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
        self.fast_click_switch_var = ctk.StringVar(value="off")
        self.record_coords_switch_var = ctk.StringVar(value="off")
        self.turbo_scan_switch_var = ctk.StringVar(value="on")
        self.obscured_autofix_switch_var = ctk.StringVar(value="on")
        
        self.global_trigger_image_path = None
        self.global_text_trigger_text = ""
        self.global_text_trigger_mode = "wait"
        self.global_text_trigger_region = None

        self.ui_queue = queue.Queue()
        self.action_ui_rows = []
        self.selected_action_index = self.listening_for_new_hotkey = None
        self.listening_for_manual_action = False
        self.currently_pressed_keys = set()
        self.recorded_target_hwnd = None
        self.recorded_target_exe = "Unknown Window"
        
        self.dragged_index = None
        self.drag_y_start = 0

        # Gamepad Analog Trigger Tracking Context Maps
        self.last_lt_pressed = False
        self.last_rt_pressed = False
        
        # THUMBSTICK LAST DIRECTIONAL STATE TRACKING MATRIX
        self.last_ls_dir = "CENT"
        self.last_rs_dir = "CENT"
        
        self.tracked_gamepad = None
        if HAS_PYGAME:
            pygame.init()
            pygame.joystick.init()
            threading.Thread(target=self.poll_controller_hardware_engine, daemon=True).start()

        # Build structural anchors and placeholder cards
        self.setup_layout_grid()
        
        # ── FIXED: DELAYED ALL BUTTON INITIALIZATION COMMAND LOOPS TO THE DEEP END ──
        # This completely guarantees that every single dynamic lookup executes crash-free.
        self.reset_anchor_btn = ctk.CTkButton(self.anchor_card, text="✕ Reset", width=60, height=20, fg_color="#2b2d31", hover_color=ACCENT_RED, text_color=TEXT_MUTED, font=ctk.CTkFont(size=10, weight="bold"), command=self.reset_anchor_window)
        self.reset_anchor_btn.pack(side="right", padx=14, pady=10)

        self.select_trigger_img_btn = ctk.CTkButton(self.btn_container, text="📂 Select Image File", fg_color="#2b2d31", hover_color="#3d4047", font=ctk.CTkFont(size=12, weight="bold"), height=34, command=self.set_global_center_trigger_image)
        self.select_trigger_img_btn.pack(side="left", expand=True, fill="x", padx=(4, 2))
        self.snipe_trigger_img_btn = ctk.CTkButton(self.btn_container, text="🎯 Snipe Vision Node", fg_color=ACCENT_PURPLE, hover_color="#6d28d9", font=ctk.CTkFont(size=12, weight="bold"), height=34, command=self.trigger_global_center_screen_sniper)
        self.snipe_trigger_img_btn.pack(side="right", expand=True, fill="x", padx=(2, 4))

        self.play_btn = ctk.CTkButton(self.act_card, text=f"▶ Run Sequence ({self.selected_play_hotkey})", fg_color=ACCENT_GREEN, hover_color="#15803d", font=ctk.CTkFont(size=13, weight="bold"), height=40, command=self.toggle_playback)
        self.play_btn.pack(fill="x", pady=3)
        self.record_btn = ctk.CTkButton(self.act_card, text=f"🔴 Capture Sequence ({self.selected_record_hotkey})", fg_color=ACCENT_RED, hover_color="#b91c1c", font=ctk.CTkFont(size=13, weight="bold"), height=40, command=self.toggle_recording)
        self.record_btn.pack(fill="x", pady=3)

        self.rec_hk_btn = ctk.CTkButton(self.hk_body, text=self.selected_record_hotkey, width=120, height=26, fg_color="#222226", hover_color="#2d2d34", command=lambda: self.start_listening_for_hotkey('record'))
        self.rec_hk_btn.grid(row=0, column=1, padx=2, pady=5, sticky="e")
        self.play_hk_btn = ctk.CTkButton(self.hk_body, text=self.selected_play_hotkey, width=120, height=26, fg_color="#222226", hover_color="#2d2d34", command=lambda: self.start_listening_for_hotkey('play'))
        self.play_hk_btn.grid(row=1, column=1, padx=2, pady=5, sticky="e")

        self.add_manual_btn = ctk.CTkButton(
            self.et_container, 
            text="➕ Add Action", 
            fg_color=ACCENT_BLUE, 
            hover_color="#4752c4", 
            text_color="#ffffff",
            font=ctk.CTkFont(size=11, weight="bold"), 
            height=28, 
            width=150, 
            command=self.trigger_manual_action_choice_flow
        )
        self.add_manual_btn.pack(side="right", padx=2, pady=2)

        self.toggle_image_trigger_view()
        self.toggle_text_trigger_view()
        self.start_global_hotkey_listeners()
        self.check_ui_queue()
        self.refresh_profile_catalog_ui()

        # Hover Tooltips Configurations
        CTKTooltip(self.reset_anchor_btn, "Clear the anchored window target to make the macro run relative to the full screen.")
        CTKTooltip(self.select_trigger_img_btn, "Load a global trigger image from disk. The sequence will not run until this image is detected on screen.")
        CTKTooltip(self.snipe_trigger_img_btn, "Snip a global trigger image directly from your screen.")
        CTKTooltip(self.play_btn, "Start executing the timeline actions in a loop or single iteration.")
        CTKTooltip(self.record_btn, "Record keyboard and mouse inputs dynamically in real-time from active windows.")
        CTKTooltip(self.rec_hk_btn, "Click to assign a new hotkey to start/stop sequence recording.")
        CTKTooltip(self.play_hk_btn, "Click to assign a new hotkey to start/stop sequence playback.")
        CTKTooltip(self.add_ocr_click_btn, "Add text to Wait & Click. If 'Scan Whole Screen' is on, it scans the whole screen; otherwise, it triggers snipping.")
        CTKTooltip(self.add_ocr_wait_btn, "Add text to Wait for. If 'Scan Whole Screen' is on, it scans the whole screen; otherwise, it triggers snipping.")
        CTKTooltip(self.add_manual_btn, "Manually add keyboard keypresses or mouse click coordinates directly to the timeline.")
        CTKTooltip(self.snipe_click_icon_btn, "Snip a specific target icon on screen. The macro will wait for it to appear and click it.")
        CTKTooltip(self.snipe_wait_icon_btn, "Snip a specific target icon on screen. The macro will pause until it is detected on screen.")
        CTKTooltip(self.save_btn, "Export the current macro actions list and settings to a JSON file.")
        CTKTooltip(self.load_btn, "Import macro actions list and settings from a JSON file.")
        CTKTooltip(self.clear_timeline_btn, "Remove all actions from the current pipeline timeline.")
        CTKTooltip(self.obscured_autofix_switch, "Automatically detect icons when partially covered by badges (e.g. pencil, x2), text, or moving backgrounds.")

    def setup_layout_grid(self):
        # Configure layout with a top header and two main columns
        self.grid_rowconfigure(0, weight=0) # Header row
        self.grid_rowconfigure(1, weight=1) # Main workspace row
        self.grid_columnconfigure(0, weight=3, minsize=440) 
        self.grid_columnconfigure(1, weight=4, minsize=480) 

        # ── TOP BRANDING & STATUS HEADER ──────────────────────────────────────────
        header_frame = ctk.CTkFrame(self, fg_color=HEADER_BG, border_color=BORDER_COLOR, border_width=1, corner_radius=0, height=56)
        header_frame.grid(row=0, column=0, columnspan=2, sticky="ew")
        header_frame.pack_propagate(False)
        
        # Logo and Title
        brand_lbl = ctk.CTkLabel(header_frame, text="⚡ VISION MACRO PRO", font=ctk.CTkFont(family="Segoe UI", size=15, weight="bold"), text_color=ACCENT_PURPLE)
        brand_lbl.pack(side="left", padx=20)

        # Profile Manager Container in the Header
        self.header_profile_container = ctk.CTkFrame(header_frame, fg_color="transparent")
        self.header_profile_container.pack(side="left", padx=(10, 20), pady=14)
        
        # State capsule badge
        status_badge_frame = ctk.CTkFrame(header_frame, fg_color="#18181b", border_color=BORDER_COLOR, border_width=1, corner_radius=14, height=28)
        status_badge_frame.pack(side="right", padx=20, pady=14)
        status_badge_frame.pack_propagate(True)
        
        self.status_label = ctk.CTkLabel(status_badge_frame, text="● STABLE SYSTEM IDLE", font=ctk.CTkFont(family="Segoe UI", size=10, weight="bold"), text_color=TEXT_MUTED, padx=12, pady=4)
        self.status_label.pack()

        # ── PROPERTIES CONTROLS (LEFT PANEL - TABBED VIEW) ──────────────────────
        self.middle_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.middle_frame.grid(row=1, column=0, sticky="nsew", padx=10, pady=10)

        # Segmented Tab View
        self.tabview = ctk.CTkTabview(
            self.middle_frame, 
            fg_color=PANEL_BG, 
            border_color=BORDER_COLOR, 
            border_width=1, 
            corner_radius=10,
            segmented_button_fg_color=APP_BG,
            segmented_button_selected_color=ACCENT_PURPLE,
            segmented_button_selected_hover_color="#6d28d9",
            segmented_button_unselected_color=PANEL_BG,
            segmented_button_unselected_hover_color="#1a1a1e",
            text_color=TEXT_MAIN
        )
        self.tabview.pack(fill="both", expand=True, padx=2, pady=2)
        
        tab_desk = self.tabview.add("🎮 Action Desk")
        tab_drivers = self.tabview.add("⌨️ Drivers")

        # ── Tab 1: Action Desk Controls ──
        # Workspace action buttons
        self.act_card = ctk.CTkFrame(tab_desk, fg_color="transparent")
        self.act_card.pack(fill="x", pady=3, padx=6)

        # Anchor window configuration card
        self.anchor_card = ctk.CTkFrame(tab_desk, fg_color=PANEL_BG, border_color=BORDER_COLOR, border_width=1, corner_radius=8)
        self.anchor_card.pack(fill="x", pady=3, padx=6)
        self.anchor_status_lbl = ctk.CTkLabel(self.anchor_card, text="Anchor Window: Independent", font=ctk.CTkFont(size=11, family="Consolas"), text_color=ACCENT_BLUE, anchor="w")
        self.anchor_status_lbl.pack(side="left", padx=10, pady=6)

        # Global vision image trigger card
        img_trigger_card = ctk.CTkFrame(tab_desk, fg_color=PANEL_BG, border_color=BORDER_COLOR, border_width=1, corner_radius=8)
        img_trigger_card.pack(fill="x", pady=3, padx=6)
        
        self.trigger_header_container = ctk.CTkFrame(img_trigger_card, fg_color="transparent")
        self.trigger_header_container.pack(fill="x", padx=10, pady=2)
        
        self.trigger_status_title = ctk.CTkLabel(self.trigger_header_container, text="📸 GLOBAL SEQUENCE IMAGE TRIGGER", font=ctk.CTkFont(size=10, weight="bold"), text_color=TEXT_MAIN)
        self.trigger_status_title.pack(side="left", pady=2)
        
        self.img_trigger_switch_var = ctk.StringVar(value="off")
        self.img_trigger_switch = ctk.CTkSwitch(self.trigger_header_container, text="", variable=self.img_trigger_switch_var, onvalue="on", offvalue="off", width=36, command=self.toggle_image_trigger_view)
        self.img_trigger_switch.pack(side="right", padx=2)

        self.clear_img_trigger_btn = ctk.CTkButton(self.trigger_header_container, text="❌ Clear", width=50, height=16, fg_color="#2b2d31", hover_color=ACCENT_RED, text_color=TEXT_MUTED, font=ctk.CTkFont(size=9, weight="bold"), command=self.remove_global_trigger_image)
        
        self.btn_container = ctk.CTkFrame(img_trigger_card, fg_color="transparent")
        self.trigger_image_label = ctk.CTkLabel(img_trigger_card, text="No trigger image selected", font=ctk.CTkFont(size=10, weight="bold"), text_color=TEXT_MUTED)
        self.center_preview_label = ctk.CTkLabel(img_trigger_card, text="")

        # ── Action Desk Icon Detection Actions Creator Card ──
        icon_actions_card = ctk.CTkFrame(tab_desk, fg_color=PANEL_BG, border_color=BORDER_COLOR, border_width=1, corner_radius=8)
        icon_actions_card.pack(fill="x", pady=3, padx=6)
        
        ctk.CTkLabel(icon_actions_card, text="📸 SCREEN ICON DETECTION ACTIONS", font=ctk.CTkFont(size=10, weight="bold"), text_color=TEXT_MAIN).pack(anchor="w", padx=10, pady=(6, 2))
        
        icon_btn_frame = ctk.CTkFrame(icon_actions_card, fg_color="transparent")
        icon_btn_frame.pack(fill="x", padx=10, pady=(2, 6))
        
        self.snipe_click_icon_btn = ctk.CTkButton(icon_btn_frame, text="🎯 Snipe & Click Icon", fg_color=ACCENT_PURPLE, hover_color="#6d28d9", font=ctk.CTkFont(size=11, weight="bold"), height=30, command=lambda: self.trigger_screen_sniper_flow(click_on_match=True))
        self.snipe_click_icon_btn.pack(side="left", fill="x", expand=True, padx=2)
        
        self.snipe_wait_icon_btn = ctk.CTkButton(icon_btn_frame, text="👁️ Snipe & Wait Icon", fg_color=ACCENT_GREEN, hover_color="#059669", font=ctk.CTkFont(size=11, weight="bold"), height=30, command=lambda: self.trigger_screen_sniper_flow(click_on_match=False))
        self.snipe_wait_icon_btn.pack(side="left", fill="x", expand=True, padx=2)

        # ── Action Desk Vision Actions Creator Card ──
        vision_actions_card = ctk.CTkFrame(tab_desk, fg_color=PANEL_BG, border_color=BORDER_COLOR, border_width=1, corner_radius=8)
        vision_actions_card.pack(fill="x", pady=3, padx=6)
        
        self.text_trigger_header_container = ctk.CTkFrame(vision_actions_card, fg_color="transparent")
        self.text_trigger_header_container.pack(fill="x", padx=10, pady=2)
        
        self.text_trigger_status_title = ctk.CTkLabel(self.text_trigger_header_container, text="📝 GLOBAL SEQUENCE TEXT TRIGGER", font=ctk.CTkFont(size=10, weight="bold"), text_color=TEXT_MAIN)
        self.text_trigger_status_title.pack(side="left", pady=2)
        
        self.text_trigger_switch_var = ctk.StringVar(value="off")
        self.text_trigger_switch = ctk.CTkSwitch(self.text_trigger_header_container, text="", variable=self.text_trigger_switch_var, onvalue="on", offvalue="off", width=36, command=self.toggle_text_trigger_view)
        self.text_trigger_switch.pack(side="right", padx=2)
        
        self.clear_text_trigger_btn = ctk.CTkButton(self.text_trigger_header_container, text="❌ Clear", width=50, height=16, fg_color="#2b2d31", hover_color=ACCENT_RED, text_color=TEXT_MUTED, font=ctk.CTkFont(size=9, weight="bold"), command=self.remove_global_text_trigger)
        
        self.text_trigger_container = ctk.CTkFrame(vision_actions_card, fg_color="transparent")
        
        # Inline text query entry field
        self.vision_query_entry = ctk.CTkEntry(self.text_trigger_container, placeholder_text="Enter text to search or wait for...", fg_color=APP_BG, border_color=BORDER_COLOR, height=26)
        self.vision_query_entry.pack(fill="x", padx=10, pady=(2, 4))
        
        self.ocr_whole_screen_var = ctk.StringVar(value="on")
        self.ocr_whole_screen_switch = ctk.CTkSwitch(self.text_trigger_container, text="Scan Whole Screen", variable=self.ocr_whole_screen_var, onvalue="on", offvalue="off", font=ctk.CTkFont(size=11), command=self.update_ocr_text_label)
        self.ocr_whole_screen_switch.pack(anchor="w", padx=10, pady=2)
        
        v_btn_frame = ctk.CTkFrame(self.text_trigger_container, fg_color="transparent")
        v_btn_frame.pack(fill="x", padx=10, pady=(2, 6))
        
        self.add_ocr_click_btn = ctk.CTkButton(v_btn_frame, text="🔍 Wait & Click Text", fg_color=ACCENT_PURPLE, hover_color="#6d28d9", font=ctk.CTkFont(size=11, weight="bold"), height=30, command=self.trigger_ocr_click_flow)
        self.add_ocr_click_btn.pack(side="left", fill="x", expand=True, padx=2)
        
        self.add_ocr_wait_btn = ctk.CTkButton(v_btn_frame, text="📝 Wait for Text", fg_color=ACCENT_GREEN, hover_color="#059669", font=ctk.CTkFont(size=11, weight="bold"), height=30, command=self.trigger_ocr_wait_flow)
        self.add_ocr_wait_btn.pack(side="left", fill="x", expand=True, padx=2)

        self.ocr_text_label = ctk.CTkLabel(self.text_trigger_container, text="No text query active", font=ctk.CTkFont(size=10, weight="bold"), text_color=TEXT_MUTED)
        self.ocr_text_label.pack(pady=(1, 6))
        self.vision_query_entry.bind("<KeyRelease>", self.update_ocr_text_label)

        # ── Action Desk: Configurations & Humanization (Merged Settings) ──
        # Dynamic inputs packed when loop mode is clicked
        from tkinter import Frame
        self.dynamic_loop_inputs = Frame(tab_desk, bg=PANEL_BG, bd=0, highlightthickness=0)
        self.dynamic_loop_inputs.pack(fill="x", pady=2, padx=6)

        # Loop modes
        drv_card = ctk.CTkFrame(tab_desk, fg_color=PANEL_BG, border_color=BORDER_COLOR, border_width=1, corner_radius=8)
        drv_card.pack(fill="x", pady=3, padx=6)
        ctk.CTkLabel(drv_card, text="⏱️ INTERACTION CONFIGURATIONS", font=ctk.CTkFont(size=10, weight="bold"), text_color=TEXT_MAIN).pack(anchor="w", padx=10, pady=4)
        db = ctk.CTkFrame(drv_card, fg_color="transparent")
        db.pack(fill="x", padx=10, pady=4)
        ctk.CTkRadioButton(db, text="One Time Execution", variable=self.loop_var, value="One Time", font=ctk.CTkFont(size=11), command=self.change_loop_mode).pack(anchor="w", pady=1)
        ctk.CTkRadioButton(db, text="Infinite Processing Loops", variable=self.loop_var, value="Loop", font=ctk.CTkFont(size=11), command=self.change_loop_mode).pack(anchor="w", pady=1)
        ctk.CTkRadioButton(db, text="Custom Loop Count Iterations", variable=self.loop_var, value="Count", font=ctk.CTkFont(size=11), command=self.change_loop_mode).pack(anchor="w", pady=1)

        # Anti-Detection
        hb = ctk.CTkFrame(tab_desk, fg_color=PANEL_BG, border_color=BORDER_COLOR, border_width=1, corner_radius=8)
        hb.pack(fill="x", pady=3, padx=6)
        ctk.CTkLabel(hb, text="🛡️ ANTI-DETECTION HUMANIZATION", font=ctk.CTkFont(size=10, weight="bold"), text_color=ACCENT_GREEN).pack(anchor="w", padx=10, pady=4)
        hbb = ctk.CTkFrame(hb, fg_color="transparent")
        hbb.pack(fill="x", padx=10, pady=4)
        ctk.CTkSwitch(hbb, text="Enable Organic Bézier Curves", font=ctk.CTkFont(size=11), variable=self.bezier_switch_var, onvalue="on", offvalue="off").pack(anchor="w", pady=1)
        ctk.CTkSwitch(hbb, text="Randomize Target Jitter", font=ctk.CTkFont(size=11), variable=self.fuzz_switch_var, onvalue="on", offvalue="off").pack(anchor="w", pady=1)
        ctk.CTkSwitch(hbb, text="Instant Clicks (Non-Human Fast Click)", font=ctk.CTkFont(size=11), variable=self.fast_click_switch_var, onvalue="on", offvalue="off").pack(anchor="w", pady=1)
        ctk.CTkSwitch(hbb, text="Record Mouse Coordinates (X/Y)", font=ctk.CTkFont(size=11), variable=self.record_coords_switch_var, onvalue="on", offvalue="off").pack(anchor="w", pady=1)
        ctk.CTkSwitch(hbb, text="Turbo Scan Mode (Super Fast Icons/Text)", font=ctk.CTkFont(size=11), variable=self.turbo_scan_switch_var, onvalue="on", offvalue="off").pack(anchor="w", pady=1)
        self.obscured_autofix_switch = ctk.CTkSwitch(hbb, text="Obscured Icons Auto-Fix (Detect icons behind text/badges)", font=ctk.CTkFont(size=11), variable=self.obscured_autofix_switch_var, onvalue="on", offvalue="off")
        self.obscured_autofix_switch.pack(anchor="w", pady=1)

        # ── Tab 3: Shortcut Drivers & Controller ──
        # System Hotkeys bind box
        self.hk_card = ctk.CTkFrame(tab_drivers, fg_color=PANEL_BG, border_color=BORDER_COLOR, border_width=1, corner_radius=8)
        self.hk_card.pack(fill="x", pady=6, padx=8)
        ctk.CTkLabel(self.hk_card, text="⌨️  SYSTEM HOTKEY DRIVERS", font=ctk.CTkFont(size=11, weight="bold"), text_color=TEXT_MAIN).pack(anchor="w", padx=12, pady=6)
        
        self.hk_body = ctk.CTkFrame(self.hk_card, fg_color="transparent")
        self.hk_body.pack(fill="x", padx=14, pady=8)
        self.hk_body.grid_columnconfigure(0, weight=1)
        self.hk_body.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(self.hk_body, text="Record Shortcut Key:", text_color=TEXT_MUTED, font=ctk.CTkFont(size=12)).grid(row=0, column=0, padx=2, pady=5, sticky="w")
        ctk.CTkLabel(self.hk_body, text="Playback Shortcut Key:", text_color=TEXT_MUTED, font=ctk.CTkFont(size=12)).grid(row=1, column=0, padx=2, pady=5, sticky="w")

        # Gamepad status
        gp_card = ctk.CTkFrame(tab_drivers, fg_color=PANEL_BG, border_color=BORDER_COLOR, border_width=1, corner_radius=8)
        gp_card.pack(fill="x", pady=6, padx=8)
        ctk.CTkLabel(gp_card, text="🎮 GAMEPAD POLLING MATRIX", font=ctk.CTkFont(size=11, weight="bold"), text_color=ACCENT_PURPLE).pack(anchor="w", padx=12, pady=6)
        gp_body = ctk.CTkFrame(gp_card, fg_color="transparent")
        gp_body.pack(fill="x", padx=14, pady=8)
        gp_status_text = "Status: ACTIVE POLLING HOOKS" if HAS_PYGAME else "Status: PYGAME NOT INSTALLED"
        gp_color = ACCENT_GREEN if HAS_PYGAME else TEXT_MUTED
        ctk.CTkLabel(gp_body, text=gp_status_text, font=ctk.CTkFont(family="Consolas", size=11), text_color=gp_color).pack(anchor="w")

        # ── TIMELINE FLOW (RIGHT PANEL) ───────────────────────────────────────────
        self.right_frame = ctk.CTkFrame(self, fg_color=PANEL_BG, border_color=BORDER_COLOR, border_width=1, corner_radius=12)
        self.right_frame.grid(row=1, column=1, sticky="nsew", padx=20, pady=20)

        th = ctk.CTkFrame(self.right_frame, fg_color="transparent")
        th.pack(fill="x", pady=(16, 10), padx=16)
        ctk.CTkLabel(th, text="Macro Record", font=ctk.CTkFont(size=15, weight="bold"), text_color=TEXT_MAIN).pack(side="left")
        
        self.clear_timeline_btn = ctk.CTkButton(th, text="🗑️ Clear Timeline", fg_color=ACCENT_RED, hover_color="#b91c1c", font=ctk.CTkFont(size=11, weight="bold"), width=110, height=28, command=self.clear_macro)
        self.clear_timeline_btn.pack(side="right", padx=(4, 0))

        self.save_btn = ctk.CTkButton(th, text="📤 Export JSON", fg_color="#2b2d31", hover_color="#3d4047", font=ctk.CTkFont(size=11, weight="bold"), width=110, height=28, command=self.export_macro)
        self.save_btn.pack(side="right", padx=4)

        self.load_btn = ctk.CTkButton(th, text="📥 Load JSON", fg_color="#2b2d31", hover_color="#3d4047", font=ctk.CTkFont(size=11, weight="bold"), width=100, height=28, command=self.import_macro)
        self.load_btn.pack(side="right", padx=4)

        self.timeline_scroll = ctk.CTkScrollableFrame(self.right_frame, fg_color=APP_BG, border_color=BORDER_COLOR, border_width=1, corner_radius=8)
        self.timeline_scroll.pack(fill="both", expand=True, padx=16, pady=4)

        self.et_container = ctk.CTkFrame(self.right_frame, fg_color="transparent")
        self.et_container.pack(fill="x", pady=14, padx=16)

        # Soft Fade-In Start Animation
        self.attributes("-alpha", 0.0)
        def run_fade():
            alpha = 0.0
            def step():
                nonlocal alpha
                if alpha < 1.0:
                    alpha += 0.08
                    self.attributes("-alpha", min(1.0, alpha))
                    self.after(12, step)
            step()
        self.after(50, run_fade)

    def poll_controller_hardware_engine(self):
        while True:
            if not self.is_recording:
                time.sleep(0.5)
                continue

            if pygame.joystick.get_count() > 0 and not self.tracked_gamepad:
                self.tracked_gamepad = pygame.joystick.Joystick(0)
                self.tracked_gamepad.init()

            for event in pygame.event.get():
                if not self.is_recording:
                    continue

                d = time.time() - self.start_time
                self.start_time = time.time()

                if event.type == pygame.JOYBUTTONDOWN:
                    self.after(0, lambda ev=event, dt=d: self.add_single_action_to_live_ui({
                        'type': 'controller', 'action': 'button_down', 'index': ev.button, 'delay': dt
                    }))

                elif event.type == pygame.JOYBUTTONUP:
                    self.after(0, lambda ev=event, dt=d: self.add_single_action_to_live_ui({
                        'type': 'controller', 'action': 'button_up', 'index': ev.button, 'delay': dt
                    }))

                elif event.type == pygame.JOYHATMOTION:
                    h_x, h_y = event.value
                    hat_name = "D-Pad CENT"
                    if h_y == 1: hat_name = "D-Pad UP"
                    elif h_y == -1: hat_name = "D-Pad DOWN"
                    elif h_x == -1: hat_name = "D-Pad LEFT"
                    elif h_x == 1: hat_name = "D-Pad RIGHT"

                    self.after(0, lambda name=hat_name, dt=d: self.add_single_action_to_live_ui({
                        'type': 'controller', 'action': 'hat_move', 'name': name, 'delay': dt
                    }))

                elif event.type == pygame.JOYAXISMOTION:
                    if not self.tracked_gamepad:
                        continue
                    num_axes = self.tracked_gamepad.get_numaxes()
                    
                    lt_val = self.tracked_gamepad.get_axis(4) if num_axes > 4 else -1.0
                    rt_val = self.tracked_gamepad.get_axis(5) if num_axes > 5 else -1.0
                    
                    lt_pressed = lt_val > 0.0
                    rt_pressed = rt_val > 0.0

                    if lt_pressed != self.last_lt_pressed:
                        self.last_lt_pressed = lt_pressed
                        act_type = 'trigger_down' if lt_pressed else 'trigger_up'
                        self.after(0, lambda act=act_type, dt=d: self.add_single_action_to_live_ui({
                            'type': 'controller', 'action': act, 'name': 'LT (Left Trigger)', 'delay': dt
                        }))

                    if rt_pressed != self.last_rt_pressed:
                        self.last_rt_pressed = rt_pressed
                        act_type = 'trigger_down' if rt_pressed else 'trigger_up'
                        self.after(0, lambda act=act_type, dt=d: self.add_single_action_to_live_ui({
                            'type': 'controller', 'action': act, 'name': 'RT (Right Trigger)', 'delay': dt
                        }))

                    ls_x = self.tracked_gamepad.get_axis(0) if num_axes > 0 else 0.0
                    ls_y = self.tracked_gamepad.get_axis(1) if num_axes > 1 else 0.0
                    
                    current_ls_dir = "CENT"
                    if abs(ls_x) > 0.40 or abs(ls_y) > 0.40:
                        if abs(ls_x) > abs(ls_y):
                            current_ls_dir = "LS RIGHT" if ls_x > 0 else "LS LEFT"
                        else:
                            current_ls_dir = "LS DOWN" if ls_y > 0 else "LS UP"

                    if current_ls_dir != self.last_ls_dir:
                        self.last_ls_dir = current_ls_dir
                        self.after(0, lambda name=current_ls_dir, dt=d: self.add_single_action_to_live_ui({
                            'type': 'controller', 'action': 'stick_move', 'name': name, 'delay': dt
                        }))

                    rs_x = self.tracked_gamepad.get_axis(2) if num_axes > 2 else 0.0
                    rs_y = self.tracked_gamepad.get_axis(3) if num_axes > 3 else 0.0
                    
                    current_rs_dir = "CENT"
                    if abs(rs_x) > 0.40 or abs(rs_y) > 0.40:
                        if abs(rs_x) > abs(rs_y):
                            current_rs_dir = "RS RIGHT" if rs_x > 0 else "RS LEFT"
                        else:
                            current_rs_dir = "RS DOWN" if rs_y > 0 else "RS UP"

                    if current_rs_dir != self.last_rs_dir:
                        self.last_rs_dir = current_rs_dir
                        self.after(0, lambda name=current_rs_dir, dt=d: self.add_single_action_to_live_ui({
                            'type': 'controller', 'action': 'stick_move', 'name': name, 'delay': dt
                        }))

            time.sleep(0.016)

    def reset_anchor_window(self):
        self.recorded_target_hwnd = None
        self.recorded_target_exe = "Unknown Window"
        self.anchor_status_lbl.configure(text="Anchor Window: Independent")


    def toggle_image_trigger_view(self):
        if self.img_trigger_switch_var.get() == "on":
            self.btn_container.pack(fill="x", padx=10, pady=(2, 10))
            self.trigger_image_label.pack(pady=(2, 10))
            if self.global_trigger_image_path and os.path.exists(self.global_trigger_image_path):
                self.clear_img_trigger_btn.pack(side="right", padx=6, pady=2)
                self.render_center_panel_preview(self.global_trigger_image_path)
        else:
            self.btn_container.pack_forget()
            self.trigger_image_label.pack_forget()
            self.clear_img_trigger_btn.pack_forget()
            self.render_center_panel_preview(None)

    def render_center_panel_preview(self, path):
        try:
            if path and os.path.exists(path):
                img = Image.open(path)
                img.thumbnail((200, 100))
                ctk_img = ctk.CTkImage(light_image=img, dark_image=img, size=(img.width, img.height))
                self.center_preview_label.configure(image=ctk_img, text="")
                self.center_preview_label.image = ctk_img  # Reference to avoid GC
                self.center_preview_label.pack(pady=(5, 10))
            else:
                self.center_preview_label.configure(image="", text="")
                self.center_preview_label.pack_forget()
        except Exception as e:
            print(f"Preview Error: {e}")

    def toggle_text_trigger_view(self):
        if self.text_trigger_switch_var.get() == "on":
            self.text_trigger_container.pack(fill="x", pady=2)
            if self.global_text_trigger_text:
                self.clear_text_trigger_btn.pack(side="right", padx=6, pady=2)
        else:
            self.text_trigger_container.pack_forget()
            self.clear_text_trigger_btn.pack_forget()

    def remove_global_text_trigger(self):
        self.global_text_trigger_text = ""
        self.global_text_trigger_region = None
        self.ocr_text_label.configure(text="No text query active", text_color=TEXT_MUTED)
        self.clear_text_trigger_btn.pack_forget()

    def set_global_center_trigger_image(self):
        fp = filedialog.askopenfilename(title="Select Trigger Image Snippet", filetypes=[("Images", "*.png *.jpg *.jpeg")])
        if fp:
            self.global_trigger_image_path = fp
            fn = os.path.basename(fp)
            self.trigger_status_title.configure(text=f"📷 TRIGGER IMAGE BOUND: {fn.upper()}", text_color=ACCENT_GREEN)
            self.clear_img_trigger_btn.pack(side="right", padx=6, pady=2)
            self.trigger_image_label.configure(text=f"Trigger Image: {fn}", text_color=ACCENT_GREEN)
            self.render_center_panel_preview(fp)

    def trigger_global_center_screen_sniper(self):
        if self.is_playing or self.is_recording: return
        self.withdraw()
        time.sleep(0.2)
        ScreenSnipper(self, self.process_center_panel_sniped_trigger)

    def process_center_panel_sniped_trigger(self, x, y, w, h):
        captured_matrix = win32_screenshot((x, y, w, h))
        self.deiconify()
        os.makedirs("./assets", exist_ok=True)
        assigned_path = f"./assets/global_trigger_active.png"
        captured_matrix.save(assigned_path)
        
        self.global_trigger_image_path = assigned_path
        self.trigger_status_title.configure(text="📷 TRIGGER SNIP BOUND SUCCESSFUL", text_color=ACCENT_GREEN)
        self.clear_img_trigger_btn.pack(side="right", padx=6, pady=2)
        self.trigger_image_label.configure(text="Trigger Image: global_trigger_active.png (Sniped)", text_color=ACCENT_GREEN)
        self.render_center_panel_preview(assigned_path)

    def remove_global_trigger_image(self):
        self.global_trigger_image_path = None
        self.trigger_status_title.configure(text="📸 GLOBAL SEQUENCE IMAGE TRIGGER", text_color=TEXT_MAIN)
        self.clear_img_trigger_btn.pack_forget()
        self.render_center_panel_preview(None)
        self.trigger_image_label.configure(text="No trigger image selected", text_color=TEXT_MUTED)

    def clear_macro(self):
        if self.is_playing or self.is_recording: return
        self.macro_actions.clear()
        self.selected_action_index = None
        self.refresh_timeline_ui()

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

    def delete_profile_entry(self, name):
        if name == "Default Profile":
            return
        if name in self.profiles_db:
            del self.profiles_db[name]
        
        if self.active_profile_name == name:
            self.active_profile_name = "Default Profile"
            self.macro_actions = list(self.profiles_db.get("Default Profile", []))
            
        self.refresh_profile_catalog_ui()
        self.refresh_timeline_ui()

    def refresh_profile_catalog_ui(self):
        for widget in self.header_profile_container.winfo_children(): widget.destroy()
        if not self.profiles_db: self.profiles_db["Default Profile"] = []
        for p_name in list(self.profiles_db.keys()):
            is_active = (p_name == self.active_profile_name)
            bg = ACCENT_PURPLE if is_active else "#2b2d31"
            hover = "#7c3aed" if is_active else "#3d4047"
            
            p_frame = ctk.CTkFrame(self.header_profile_container, fg_color="transparent")
            p_frame.pack(side="left", padx=4)
            
            btn = ctk.CTkButton(
                p_frame, 
                text=p_name, 
                font=ctk.CTkFont(size=11, weight="bold" if is_active else "normal"), 
                fg_color=bg, 
                hover_color=hover,
                text_color=TEXT_MAIN, 
                width=80, 
                height=26, 
                command=lambda name=p_name: self.select_profile_catalog_node(name)
            )
            btn.pack(side="left")
            
            del_btn = ctk.CTkButton(
                p_frame,
                text="✕",
                font=ctk.CTkFont(size=10, weight="bold"),
                fg_color="transparent",
                hover_color=ACCENT_RED,
                text_color=ACCENT_RED,
                width=16,
                height=22,
                corner_radius=4,
                command=lambda name=p_name: self.delete_profile_entry(name)
            )
            
            # Hover detection
            def make_hover_handlers(d_btn, name_val):
                return lambda e: d_btn.pack(side="left", padx=(2, 0)) if name_val != "Default Profile" else None, \
                       lambda e: d_btn.pack_forget()
            
            on_enter, on_leave = make_hover_handlers(del_btn, p_name)
            
            btn.bind("<Enter>", on_enter)
            btn.bind("<Leave>", on_leave)
            p_frame.bind("<Enter>", on_enter)
            p_frame.bind("<Leave>", on_leave)
            del_btn.bind("<Enter>", on_enter)
            del_btn.bind("<Leave>", on_leave)

        self.create_profile_btn = ctk.CTkButton(
            self.header_profile_container,
            text="+",
            font=ctk.CTkFont(size=14, weight="bold"),
            fg_color="#2b2d31",
            hover_color="#3d4047",
            text_color=TEXT_MAIN,
            width=26,
            height=26,
            command=self.create_new_profile_entry
        )
        self.create_profile_btn.pack(side="left", padx=4)
        CTKTooltip(self.create_profile_btn, "Create a new empty macro profile vector in your profile database.")

    def trigger_screen_sniper_flow(self, click_on_match=False):
        if self.is_playing or self.is_recording: return
        self.last_snipe_click_default = click_on_match
        self.withdraw() 
        time.sleep(0.2)
        ScreenSnipper(self, self.process_sniped_bounding_box_assets)

    def process_sniped_bounding_box_assets(self, x, y, w, h):
        sniped_img = win32_screenshot((x, y, w, h))
        self.deiconify()
        os.makedirs("./assets", exist_ok=True)
        asset_path = f"./assets/snippet_{int(time.time())}.png"
        sniped_img.save(asset_path)
        
        click_val = getattr(self, 'last_snipe_click_default', False)
        
        default_conf = 0.60 if self.obscured_autofix_switch_var.get() == "on" else 0.85
        default_engine = "circle_mask" if self.obscured_autofix_switch_var.get() == "on" else "standard"
        
        if click_val:
            def on_behavior_selected(res):
                if isinstance(res, str):
                    choice = res
                    conf = default_conf
                    engine = default_engine
                else:
                    choice = res.get('behavior', 'click')
                    conf = res.get('confidence', default_conf)
                    engine = res.get('match_engine', default_engine)
                    
                key_to_press = None
                match_behavior = choice
                
                if choice == 'press_key':
                    dialog = ctk.CTkInputDialog(
                        text="Enter the keyboard key to press on match (e.g. E, Space):",
                        title="Key Press on Match"
                    )
                    input_key = dialog.get_input()
                    if input_key and input_key.strip():
                        key_to_press = input_key.strip().upper()
                    else:
                        match_behavior = "click"
                        
                self.add_single_action_to_live_ui({
                    'type': 'image_match_wait',
                    'image_path': asset_path,
                    'confidence': conf,
                    'match_engine': engine,
                    'click_on_match': True,
                    'match_behavior': match_behavior,
                    'key_to_press': key_to_press,
                    'delay': 0.5
                })
            
            IconActionChoiceModal(self, on_behavior_selected, image_path=asset_path)
        else:
            self.add_single_action_to_live_ui({
                'type': 'image_match_wait',
                'image_path': asset_path,
                'confidence': default_conf,
                'match_engine': default_engine,
                'click_on_match': False,
                'match_behavior': 'wait',
                'key_to_press': None,
                'delay': 0.5
            })

    def trigger_ocr_wait_flow(self):
        if self.is_playing or self.is_recording: return
        if self.ocr_whole_screen_var.get() == "on":
            text_query = self.vision_query_entry.get().strip()
            if not text_query:
                dialog = ctk.CTkInputDialog(text="Enter the text query to wait for:", title="OCR Text Query")
                text_query = dialog.get_input()
            if text_query:
                self.global_text_trigger_region = None
                self.global_text_trigger_text = text_query
                self.global_text_trigger_mode = "wait"
                self.text_trigger_switch_var.set("on")
                self.toggle_text_trigger_view()
                self.ocr_text_label.configure(
                    text=f"Trigger Text (WAIT): \"{text_query}\" on Whole Screen",
                    text_color=ACCENT_GREEN
                )
                self.vision_query_entry.delete(0, 'end')
                self.vision_query_entry.insert(0, text_query)
        else:
            self.withdraw()
            time.sleep(0.2)
            ScreenSnipper(self, self.process_ocr_wait_region)
        
    def process_ocr_wait_region(self, x, y, w, h):
        self.deiconify()
        text_query = self.vision_query_entry.get().strip()
        if not text_query:
            dialog = ctk.CTkInputDialog(text="Enter the text query to wait for:", title="OCR Text Query")
            text_query = dialog.get_input()
        if text_query:
            # Convert region relative to anchor window if active
            rel_x, rel_y = x, y
            if self.recorded_target_hwnd:
                rect = RECT()
                if GetWindowRect(self.recorded_target_hwnd, ctypes.byref(rect)):
                    rel_x = x - rect.left
                    rel_y = y - rect.top
                    
            self.global_text_trigger_region = (rel_x, rel_y, w, h)
            self.global_text_trigger_text = text_query
            self.global_text_trigger_mode = "wait"
            self.text_trigger_switch_var.set("on")
            self.toggle_text_trigger_view()
            self.ocr_text_label.configure(
                text=f"Trigger Text (WAIT): \"{text_query}\" in Region ({rel_x}, {rel_y}, {w}, {h})",
                text_color=ACCENT_GREEN
            )
            self.vision_query_entry.delete(0, 'end')
            self.vision_query_entry.insert(0, text_query)

    def trigger_ocr_click_flow(self):
        if self.is_playing or self.is_recording: return
        if self.ocr_whole_screen_var.get() == "on":
            text_query = self.vision_query_entry.get().strip()
            if not text_query:
                dialog = ctk.CTkInputDialog(text="Enter the text query to search and click on:", title="OCR Click Text Query")
                text_query = dialog.get_input()
            if text_query:
                self.global_text_trigger_region = None
                self.global_text_trigger_text = text_query
                self.global_text_trigger_mode = "click"
                self.text_trigger_switch_var.set("on")
                self.toggle_text_trigger_view()
                self.ocr_text_label.configure(
                    text=f"Trigger Text (CLICK): \"{text_query}\" on Whole Screen",
                    text_color=ACCENT_GREEN
                )
                self.vision_query_entry.delete(0, 'end')
                self.vision_query_entry.insert(0, text_query)
        else:
            self.withdraw()
            time.sleep(0.2)
            ScreenSnipper(self, self.process_ocr_click_region)

    def process_ocr_click_region(self, x, y, w, h):
        self.deiconify()
        text_query = self.vision_query_entry.get().strip()
        if not text_query:
            dialog = ctk.CTkInputDialog(text="Enter the text query to search and click on:", title="OCR Click Text Query")
            text_query = dialog.get_input()
        if text_query:
            # Convert region relative to anchor window if active
            rel_x, rel_y = x, y
            if self.recorded_target_hwnd:
                rect = RECT()
                if GetWindowRect(self.recorded_target_hwnd, ctypes.byref(rect)):
                    rel_x = x - rect.left
                    rel_y = y - rect.top
                    
            self.global_text_trigger_region = (rel_x, rel_y, w, h)
            self.global_text_trigger_text = text_query
            self.global_text_trigger_mode = "click"
            self.text_trigger_switch_var.set("on")
            self.toggle_text_trigger_view()
            self.ocr_text_label.configure(
                text=f"Trigger Text (CLICK): \"{text_query}\" in Region ({rel_x}, {rel_y}, {w}, {h})",
                text_color=ACCENT_GREEN
            )
            self.vision_query_entry.delete(0, 'end')
            self.vision_query_entry.insert(0, text_query)

    def perform_ocr_on_file(self, path):
        import asyncio
        async def run():
            from winsdk.windows.media.ocr import OcrEngine
            from winsdk.windows.graphics.imaging import BitmapDecoder
            from winsdk.windows.storage import StorageFile, FileAccessMode
            try:
                file = await StorageFile.get_file_from_path_async(path)
                stream = await file.open_async(FileAccessMode.READ)
                decoder = await BitmapDecoder.create_async(stream)
                bitmap = await decoder.get_software_bitmap_async()
                engine = OcrEngine.try_create_from_user_profile_languages()
                if engine:
                    res = await engine.recognize_async(bitmap)
                    return res.text
            except Exception as e:
                print(f"OCR Error: {e}")
            return ""
        return asyncio.run(run())

    def find_text_coordinates_in_file(self, path, query):
        import asyncio
        async def run():
            from winsdk.windows.media.ocr import OcrEngine
            from winsdk.windows.graphics.imaging import BitmapDecoder
            from winsdk.windows.storage import StorageFile, FileAccessMode
            try:
                file = await StorageFile.get_file_from_path_async(path)
                stream = await file.open_async(FileAccessMode.READ)
                decoder = await BitmapDecoder.create_async(stream)
                bitmap = await decoder.get_software_bitmap_async()
                engine = OcrEngine.try_create_from_user_profile_languages()
                if engine:
                    res = await engine.recognize_async(bitmap)
                    clean_query = "".join(c for c in query.lower() if c.isalnum())
                    if not clean_query:
                        return None
                    for line in res.lines:
                        words = list(line.words)
                        n = len(words)
                        best_slice = None
                        for length in range(1, n + 1):
                            for start in range(n - length + 1):
                                end = start + length
                                slice_text = " ".join([words[k].text for k in range(start, end)])
                                clean_slice = "".join(c for c in slice_text.lower() if c.isalnum())
                                if clean_query in clean_slice:
                                    best_slice = words[start:end]
                                    break
                            if best_slice:
                                break
                        if best_slice:
                            min_x = min(w.bounding_rect.x for w in best_slice)
                            min_y = min(w.bounding_rect.y for w in best_slice)
                            max_x = max(w.bounding_rect.x + w.bounding_rect.width for w in best_slice)
                            max_y = max(w.bounding_rect.y + w.bounding_rect.height for w in best_slice)
                            return (min_x + (max_x - min_x) / 2, min_y + (max_y - min_y) / 2)
            except Exception as e:
                print(f"OCR Coordinates Error: {e}")
            return None
        return asyncio.run(run())

    def open_action_editor_modal(self, index):
        if self.is_playing or self.is_recording: return
        if index < len(self.macro_actions):
            action = self.macro_actions[index]
            ActionEditorModal(self, index, action, self.refresh_timeline_ui)

    def on_row_drag_start(self, event, index):
        self.dragged_index = index
        self.drag_y_start = event.y_root
        self.select_timeline_item(index)

    def on_row_drag_motion(self, event, index):
        if self.dragged_index is None: return
        delta_y = event.y_root - self.drag_y_start
        
        if delta_y > 34 and self.dragged_index < len(self.macro_actions) - 1:
            idx = self.dragged_index
            self.macro_actions[idx], self.macro_actions[idx+1] = self.macro_actions[idx+1], self.macro_actions[idx]
            
            row1 = self.action_ui_rows[idx]
            row2 = self.action_ui_rows[idx+1]
            self.action_ui_rows[idx], self.action_ui_rows[idx+1] = row2, row1
            
            row1.pack_forget()
            row1.pack(after=row2, fill="x", pady=3, padx=5)
            
            self.dragged_index = idx + 1
            self.drag_y_start = event.y_root
            self.update_row_indices_display_text_only()
            self.select_timeline_item(idx + 1)
            
        elif delta_y < -34 and self.dragged_index > 0:
            idx = self.dragged_index
            self.macro_actions[idx], self.macro_actions[idx-1] = self.macro_actions[idx-1], self.macro_actions[idx]
            
            row1 = self.action_ui_rows[idx]
            row2 = self.action_ui_rows[idx-1]
            self.action_ui_rows[idx], self.action_ui_rows[idx-1] = row2, row1
            
            row1.pack_forget()
            row1.pack(before=row2, fill="x", pady=3, padx=5)
            
            self.dragged_index = idx - 1
            self.drag_y_start = event.y_root
            self.update_row_indices_display_text_only()
            self.select_timeline_item(idx - 1)

    def on_row_drag_release(self, event, index):
        self.dragged_index = None
        self.profiles_db[self.active_profile_name] = list(self.macro_actions)
        self.reindex_timeline_rows()

    def update_row_indices_display_text_only(self):
        for i, row in enumerate(self.action_ui_rows):
            action = self.macro_actions[i]
            for child in row.winfo_children():
                if isinstance(child, ctk.CTkButton) and child.cget("text").startswith(" ["):
                    child.configure(text=self._action_text(i, action))
                    break

    def play_macro(self):
        import cv2
        import pyautogui
        import numpy as np
        mouse_ctl = mouse.Controller()
        # Keep full actions list for direct 1-to-1 timeline index mapping
        actions = list(self.macro_actions)
        if not actions and self.img_trigger_switch_var.get() == "off" and self.text_trigger_switch_var.get() == "off":
            self.ui_queue.put("STOP_PLAYBACK")
            return

        current_loop_mode = self.loop_var.get()
        max_loops = math.inf if current_loop_mode == "Loop" else (int(self.count_entry.get()) if current_loop_mode == "Count" else 1)
        loop_delay = max(0.0, float(self.loop_delay_entry.get())) if current_loop_mode in ("Loop", "Count") else 0.1
        
        loop_count = 0
        is_bg = False
        hwnd = None
        
        is_turbo = (self.turbo_scan_switch_var.get() == "on")
        if is_turbo:
            get_screen = lambda reg=None: cv2.cvtColor(np.array(win32_screenshot(reg)), cv2.COLOR_RGB2BGR)
            get_shot = lambda reg: win32_screenshot(reg)
            img_sleep = 0.01
            text_sleep = 0.05
            pixel_sleep = 0.005
        else:
            get_screen = lambda reg=None: cv2.cvtColor(np.array(pyautogui.screenshot(region=reg) if reg else pyautogui.screenshot()), cv2.COLOR_RGB2BGR)
            get_shot = lambda reg: pyautogui.screenshot(region=reg)
            img_sleep = 0.1
            text_sleep = 0.2
            pixel_sleep = 0.05

        self.hud_window = LiveHUD(self, "running", stop_callback=self.toggle_playback)

        while self.is_playing and (max_loops == math.inf or loop_count < max_loops):
            self.after(0, lambda lc=loop_count: self.hud_window.set_loops(lc))

            # 1. Global Image Trigger
            if self.img_trigger_switch_var.get() == "on" and self.global_trigger_image_path and os.path.exists(self.global_trigger_image_path):
                global_matched = False
                template = cv2.imread(self.global_trigger_image_path, cv2.IMREAD_COLOR)
                while self.is_playing and not global_matched:
                    screen = get_screen()
                    res = cv2.matchTemplate(screen, template, cv2.TM_CCOEFF_NORMED)
                    if cv2.minMaxLoc(res)[1] >= 0.85:
                        global_matched = True
                    else:
                        time.sleep(img_sleep)

            # 2. Global Text Trigger
            if self.text_trigger_switch_var.get() == "on" and self.global_text_trigger_text:
                text_matched = False
                while self.is_playing and not text_matched:
                    matched, cx, cy = self.check_global_text_trigger_match()
                    if matched:
                        text_matched = True
                        if self.global_text_trigger_mode == "click" and cx is not None and cy is not None:
                            if self.fuzz_switch_var.get() == "on":
                                cx += random.randint(-2, 2)
                                cy += random.randint(-2, 2)
                            if self.bezier_switch_var.get() == "on":
                                sp = mouse_ctl.position
                                human_mouse_move(mouse_ctl, sp[0], sp[1], cx, cy)
                            else:
                                send_hardware_mouse_move(cx, cy)
                            time.sleep(random.uniform(0.05, 0.1))
                            send_hardware_mouse_click("left", is_release=False)
                            time.sleep(random.uniform(0.04, 0.07))
                            send_hardware_mouse_click("left", is_release=True)
                    else:
                        time.sleep(0.2)

            i = 0
            while i < len(actions) and self.is_playing:
                action = actions[i]
                
                desc = self._action_text(i, action)
                if "]" in desc:
                    desc = desc.split("]", 1)[1].strip()
                self.after(0, lambda d=desc: self.hud_window.set_active_action(d))
                
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

                next_i = i + 1

                if action['type'] == 'image_match_wait':
                    template = cv2.imread(action['image_path'], cv2.IMREAD_COLOR)
                    matched = False
                    is_cond = action.get('is_conditional', False)
                    conf = action.get('confidence', 0.85)
                    engine = action.get('match_engine', 'standard')
                    auto_fallback = (self.obscured_autofix_switch_var.get() == "on")
                    
                    max_loc = (0, 0)
                    if is_cond:
                        screen = get_screen()
                        is_found, max_val, max_loc = match_template_enhanced(screen, template, conf, engine, auto_fallback)
                        if is_found:
                            matched = True
                    else:
                        while self.is_playing and not matched:
                            screen = get_screen()
                            is_found, max_val, max_loc = match_template_enhanced(screen, template, conf, engine, auto_fallback)
                            if is_found:
                                matched = True
                            else:
                                time.sleep(img_sleep)
                            
                    if is_cond:
                        goto_idx = action.get('goto_true') if matched else action.get('goto_false')
                        if goto_idx is not None and 1 <= goto_idx <= len(actions):
                            next_i = goto_idx - 1
                            
                    behavior = action.get('match_behavior')
                    if not behavior:
                        if action.get('click_on_match', False):
                            behavior = "press_key" if action.get('key_to_press') else "click"
                        else:
                            behavior = "wait"

                    if matched and behavior != "wait":
                        h, w = template.shape[0], template.shape[1]
                        pos_type = action.get('click_position', 'Center')
                        if pos_type == 'Top-Left':
                            tx = max_loc[0] + int(w * 0.15)
                            ty = max_loc[1] + int(h * 0.15)
                        elif pos_type == 'Top-Right':
                            tx = max_loc[0] + int(w * 0.85)
                            ty = max_loc[1] + int(h * 0.15)
                        elif pos_type == 'Bottom-Left':
                            tx = max_loc[0] + int(w * 0.15)
                            ty = max_loc[1] + int(h * 0.85)
                        elif pos_type == 'Bottom-Right':
                            tx = max_loc[0] + int(w * 0.85)
                            ty = max_loc[1] + int(h * 0.85)
                        elif pos_type == 'Random Corner':
                            corner = random.choice(['Top-Left', 'Top-Right', 'Bottom-Left', 'Bottom-Right'])
                            if corner == 'Top-Left':
                                tx = max_loc[0] + int(w * 0.15)
                                ty = max_loc[1] + int(h * 0.15)
                            elif corner == 'Top-Right':
                                tx = max_loc[0] + int(w * 0.85)
                                ty = max_loc[1] + int(h * 0.15)
                            elif corner == 'Bottom-Left':
                                tx = max_loc[0] + int(w * 0.15)
                                ty = max_loc[1] + int(h * 0.85)
                            else:
                                tx = max_loc[0] + int(w * 0.85)
                                ty = max_loc[1] + int(h * 0.85)
                        else:  # Center
                            tx = max_loc[0] + w // 2
                            ty = max_loc[1] + h // 2
                        if self.fuzz_switch_var.get() == "on":
                            tx += random.randint(-2, 2)
                            ty += random.randint(-2, 2)
                        if is_bg:
                            is_focus_restore = (self.bg_method_var.get() == "Active Focus Restore (Roblox)")
                            if is_focus_restore:
                                def do_bg_match():
                                    user32 = ctypes.windll.user32
                                    rect = RECT()
                                    user32.GetWindowRect(hwnd, ctypes.byref(rect))
                                    screen_x = rect.left + int(tx)
                                    screen_y = rect.top + int(ty)
                                    send_hardware_mouse_move(screen_x, screen_y)
                                    if behavior == "click":
                                        send_hardware_mouse_click("left", is_release=False)
                                        if self.fast_click_switch_var.get() != "on":
                                            time.sleep(random.uniform(0.04, 0.07))
                                        send_hardware_mouse_click("left", is_release=True)
                                    elif behavior == "press_key":
                                        kp = action.get('key_to_press')
                                        if kp:
                                            vk = get_vk_from_key_name(kp)
                                            if vk is not None:
                                                send_hardware_input(vk, is_release=False)
                                                if self.fast_click_switch_var.get() != "on":
                                                    time.sleep(random.uniform(0.04, 0.07))
                                                send_hardware_input(vk, is_release=True)
                                execute_background_input_with_focus(hwnd, do_bg_match)
                            else:
                                send_background_mouse_move(hwnd, tx, ty)
                                if behavior == "click":
                                    send_background_mouse_click(hwnd, "left", tx, ty, is_release=False)
                                    if self.fast_click_switch_var.get() != "on":
                                        time.sleep(random.uniform(0.04, 0.07))
                                    send_background_mouse_click(hwnd, "left", tx, ty, is_release=True)
                                elif behavior == "press_key":
                                    kp = action.get('key_to_press')
                                    if kp:
                                        vk = get_vk_from_key_name(kp)
                                        if vk is not None:
                                            send_background_key(hwnd, vk, is_release=False)
                                            if self.fast_click_switch_var.get() != "on":
                                                time.sleep(random.uniform(0.04, 0.07))
                                            send_background_key(hwnd, vk, is_release=True)
                        else:
                            if self.bezier_switch_var.get() == "on":
                                sp = mouse_ctl.position
                                human_mouse_move(mouse_ctl, sp[0], sp[1], tx, ty)
                            else:
                                send_hardware_mouse_move(tx, ty)
                            
                            if behavior == "hover":
                                pass  # Hover only, no click or keypress!
                            elif behavior == "press_key":
                                kp = action.get('key_to_press')
                                if kp:
                                    vk = get_vk_from_key_name(kp)
                                    if self.fast_click_switch_var.get() == "on":
                                        if vk is not None:
                                            send_hardware_input(vk, is_release=False)
                                            send_hardware_input(vk, is_release=True)
                                        else:
                                            try:
                                                kb_ctl = keyboard.Controller()
                                                kb_ctl.press(kp.lower())
                                                kb_ctl.release(kp.lower())
                                            except:
                                                pass
                                    else:
                                        time.sleep(random.uniform(0.08, 0.12))
                                        if vk is not None:
                                            send_hardware_input(vk, is_release=False)
                                            time.sleep(random.uniform(0.04, 0.07))
                                            send_hardware_input(vk, is_release=True)
                                        else:
                                            try:
                                                kb_ctl = keyboard.Controller()
                                                kb_ctl.press(kp.lower())
                                                time.sleep(random.uniform(0.04, 0.07))
                                                kb_ctl.release(kp.lower())
                                            except Exception as e:
                                                print("Keyboard controller fallback error:", e)
                            elif behavior == "click":
                                if self.fast_click_switch_var.get() == "on":
                                    send_hardware_mouse_click("left", is_release=False)
                                    send_hardware_mouse_click("left", is_release=True)
                                else:
                                    time.sleep(random.uniform(0.08, 0.12))
                                    send_hardware_mouse_click("left", is_release=False)
                                    time.sleep(random.uniform(0.04, 0.07))
                                    send_hardware_mouse_click("left", is_release=True)

                elif action['type'] == 'pixel_wait':
                    if is_bg:
                        px, py = action['rel_x'], action['rel_y']
                        get_pixel = lambda x, y: get_window_pixel_color(hwnd, x, y)
                    else:
                        px, py = base_x + action['rel_x'], base_y + action['rel_y']
                        get_pixel = lambda x, y: get_screen_pixel_color(x, y)
                    target_color = action['color'].upper()
                    matched = False
                    is_cond = action.get('is_conditional', False)
                    
                    if is_cond:
                        if get_pixel(px, py) == target_color:
                            matched = True
                    else:
                        while self.is_playing and get_pixel(px, py) != target_color:
                            time.sleep(pixel_sleep)
                        matched = True
                        
                    if is_cond:
                        goto_idx = action.get('goto_true') if matched else action.get('goto_false')
                        if goto_idx is not None and 1 <= goto_idx <= len(actions):
                            next_i = goto_idx - 1

                elif action['type'] == 'ocr_wait':
                    rx, ry, rw, rh = action['region']
                    if is_bg:
                        tx = rx
                        ty = ry
                    else:
                        tx = base_x + rx
                        ty = base_y + ry
                    text_query = action.get('text_query', '').strip().lower()
                    matched = False
                    is_cond = action.get('is_conditional', False)
                    
                    os.makedirs("./assets", exist_ok=True)
                    temp_ocr_path = os.path.abspath("./assets/temp_ocr.png")
                    
                    if is_cond:
                        shot = get_shot((tx, ty, rw, rh))
                        shot.save(temp_ocr_path)
                        recognized_text = self.perform_ocr_on_file(temp_ocr_path)
                        if text_query in recognized_text.lower():
                            matched = True
                    else:
                        while self.is_playing and not matched:
                            shot = get_shot((tx, ty, rw, rh))
                            shot.save(temp_ocr_path)
                            recognized_text = self.perform_ocr_on_file(temp_ocr_path)
                            if text_query in recognized_text.lower():
                                matched = True
                            else:
                                time.sleep(text_sleep)
                                
                    if os.path.exists(temp_ocr_path):
                        try: os.remove(temp_ocr_path)
                        except: pass
                        
                    if is_cond:
                        goto_idx = action.get('goto_true') if matched else action.get('goto_false')
                        if goto_idx is not None and 1 <= goto_idx <= len(actions):
                            next_i = goto_idx - 1

                elif action['type'] == 'ocr_click':
                    rx, ry, rw, rh = action['region']
                    if is_bg:
                        tx = rx
                        ty = ry
                    else:
                        tx = base_x + rx
                        ty = base_y + ry
                    text_query = action.get('text_query', '').strip()
                    matched = False
                    is_cond = action.get('is_conditional', False)
                    
                    os.makedirs("./assets", exist_ok=True)
                    temp_ocr_path = os.path.abspath("./assets/temp_ocr_click.png")
                    click_coords = None
                    
                    if is_cond:
                        shot = get_shot((tx, ty, rw, rh))
                        shot.save(temp_ocr_path)
                        click_coords = self.find_text_coordinates_in_file(temp_ocr_path, text_query)
                        if click_coords is not None:
                            matched = True
                    else:
                        while self.is_playing and not matched:
                            shot = get_shot((tx, ty, rw, rh))
                            shot.save(temp_ocr_path)
                            click_coords = self.find_text_coordinates_in_file(temp_ocr_path, text_query)
                            if click_coords is not None:
                                matched = True
                            else:
                                time.sleep(text_sleep)
                                
                    if os.path.exists(temp_ocr_path):
                        try: os.remove(temp_ocr_path)
                        except: pass
                        
                    if matched and click_coords is not None:
                        cx, cy = click_coords
                        click_x = tx + int(cx)
                        click_y = ty + int(cy)
                        if self.fuzz_switch_var.get() == "on":
                            click_x += random.randint(-2, 2)
                            click_y += random.randint(-2, 2)
                        if is_bg:
                            is_focus_restore = (self.bg_method_var.get() == "Active Focus Restore (Roblox)")
                            if is_focus_restore:
                                def do_bg_ocr_click():
                                    user32 = ctypes.windll.user32
                                    rect = RECT()
                                    user32.GetWindowRect(hwnd, ctypes.byref(rect))
                                    screen_x = rect.left + int(click_x)
                                    screen_y = rect.top + int(click_y)
                                    send_hardware_mouse_move(screen_x, screen_y)
                                    send_hardware_mouse_click("left", is_release=False)
                                    if self.fast_click_switch_var.get() != "on":
                                        time.sleep(random.uniform(0.04, 0.07))
                                    send_hardware_mouse_click("left", is_release=True)
                                execute_background_input_with_focus(hwnd, do_bg_ocr_click)
                            else:
                                send_background_mouse_move(hwnd, click_x, click_y)
                                send_background_mouse_click(hwnd, "left", click_x, click_y, is_release=False)
                                if self.fast_click_switch_var.get() != "on":
                                    time.sleep(random.uniform(0.04, 0.07))
                                send_background_mouse_click(hwnd, "left", click_x, click_y, is_release=True)
                        else:
                            if self.bezier_switch_var.get() == "on":
                                sp = mouse_ctl.position
                                human_mouse_move(mouse_ctl, sp[0], sp[1], click_x, click_y)
                            else:
                                send_hardware_mouse_move(click_x, click_y)
                            if self.fast_click_switch_var.get() == "on":
                                send_hardware_mouse_click("left", is_release=False)
                                send_hardware_mouse_click("left", is_release=True)
                            else:
                                time.sleep(random.uniform(0.08, 0.12))
                                send_hardware_mouse_click("left", is_release=False)
                                time.sleep(random.uniform(0.04, 0.07))
                                send_hardware_mouse_click("left", is_release=True)
                        
                    if is_cond:
                        goto_idx = action.get('goto_true') if matched else action.get('goto_false')
                        if goto_idx is not None and 1 <= goto_idx <= len(actions):
                            next_i = goto_idx - 1

                elif action['type'] == 'mouse':
                    use_coords = action.get('use_coords', True)
                    tx, ty = None, None
                    if use_coords and action.get('rel_x') is not None:
                        if is_bg:
                            tx, ty = action['rel_x'], action['rel_y']
                        else:
                            tx, ty = base_x + action['rel_x'], base_y + action['rel_y']
                        if self.fuzz_switch_var.get() == "on":
                            tx += random.randint(-2, 2)
                            ty += random.randint(-2, 2)
                            
                    btn_val = action['details'][2]
                    btn_name = "left"
                    if isinstance(btn_val, str):
                        if 'right' in btn_val.lower():
                            btn_name = "right"
                        elif 'middle' in btn_val.lower():
                            btn_name = "middle"
                            
                    if is_bg:
                        is_focus_restore = (self.bg_method_var.get() == "Active Focus Restore (Roblox)")
                        if is_focus_restore:
                            def do_bg_mouse():
                                user32 = ctypes.windll.user32
                                if tx is not None and ty is not None:
                                    rect = RECT()
                                    user32.GetWindowRect(hwnd, ctypes.byref(rect))
                                    screen_x = rect.left + int(tx)
                                    screen_y = rect.top + int(ty)
                                    send_hardware_mouse_move(screen_x, screen_y)
                                send_hardware_mouse_click(btn_name, is_release=False)
                                if self.fast_click_switch_var.get() != "on":
                                    time.sleep(random.uniform(0.04, 0.07))
                                send_hardware_mouse_click(btn_name, is_release=True)
                            execute_background_input_with_focus(hwnd, do_bg_mouse)
                        else:
                            if tx is not None and ty is not None:
                                send_background_mouse_move(hwnd, tx, ty)
                            send_background_mouse_click(hwnd, btn_name, tx or 0, ty or 0, is_release=False)
                            if self.fast_click_switch_var.get() != "on":
                                time.sleep(random.uniform(0.04, 0.07))
                            send_background_mouse_click(hwnd, btn_name, tx or 0, ty or 0, is_release=True)
                    else:
                        if tx is not None and ty is not None:
                            if self.bezier_switch_var.get() == "on":
                                sp = mouse_ctl.position
                                human_mouse_move(mouse_ctl, sp[0], sp[1], tx, ty)
                            else:
                                send_hardware_mouse_move(tx, ty)
                        if self.fast_click_switch_var.get() == "on":
                            send_hardware_mouse_click(btn_name, is_release=False)
                            send_hardware_mouse_click(btn_name, is_release=True)
                        else:
                            time.sleep(random.uniform(0.08, 0.12))
                            send_hardware_mouse_click(btn_name, is_release=False)
                            time.sleep(random.uniform(0.04, 0.07))
                            send_hardware_mouse_click(btn_name, is_release=True)

                elif action['type'] == 'keyboard':
                    vk, rel = action.get('vk'), action.get('is_release', False)
                    if vk is not None:
                        repeats = action.get('repeat_count', 1)
                        if is_bg:
                            is_focus_restore = (self.bg_method_var.get() == "Active Focus Restore (Roblox)")
                            if is_focus_restore:
                                def do_bg_key():
                                    if not rel and repeats > 1:
                                        for _ in range(repeats):
                                            if not self.is_playing: break
                                            send_hardware_input(vk, is_release=False)
                                            time.sleep(0.02)
                                    else:
                                        send_hardware_input(vk, is_release=rel)
                                execute_background_input_with_focus(hwnd, do_bg_key)
                            else:
                                if not rel and repeats > 1:
                                    for _ in range(repeats):
                                        if not self.is_playing: break
                                        send_background_key(hwnd, vk, is_release=False)
                                        time.sleep(0.02)
                                else:
                                    send_background_key(hwnd, vk, is_release=rel)
                        else:
                            if not rel and repeats > 1:
                                for _ in range(repeats):
                                    if not self.is_playing: break
                                    send_hardware_input(vk, is_release=False)
                                    time.sleep(0.02)
                            else:
                                send_hardware_input(vk, is_release=rel)

                elif action['type'] == 'controller':
                    pass 

                i = next_i

            loop_count += 1
            if self.is_playing and (max_loops == math.inf or loop_count < max_loops):
                rem_delay = loop_delay
                while rem_delay > 0 and self.is_playing:
                    s_step = min(0.02, rem_delay)
                    time.sleep(s_step)
                    rem_delay -= s_step

        self.ui_queue.put("STOP_PLAYBACK")

    def toggle_playback(self):
        if self.is_recording or not self.macro_actions: return
        if not self.is_playing:
            self.is_playing = True
            self.play_btn.configure(text=f"■ Stop Run ({self.selected_play_hotkey})", fg_color=ACCENT_RED)
            self.status_label.configure(text="● PLAYBACK ACTIVE", text_color=ACCENT_GREEN)
            threading.Thread(target=self.play_macro, daemon=True).start()
        else:
            self.stop_playback_ui_reset()

    def stop_playback_ui_reset(self):
        self.is_playing = False
        self.play_btn.configure(text=f"▶ Run Sequence ({self.selected_play_hotkey})", fg_color=ACCENT_GREEN)
        self.status_label.configure(text="● STABLE SYSTEM IDLE", text_color=TEXT_MUTED)
        if hasattr(self, 'hud_window') and self.hud_window:
            try:
                self.hud_window.destroy()
            except Exception:
                pass
            self.hud_window = None

    def toggle_recording(self):
        if self.is_playing: return
        if not self.is_recording:
            hwnd, exe = get_active_window_hwnd_and_exe()
            if hwnd and exe not in ("python.exe", "pythonw.exe", "macro_app.exe"):
                self.recorded_target_hwnd, self.recorded_target_exe = hwnd, exe
                self.anchor_status_lbl.configure(text=f"Anchor Window: {exe}")
            else:
                self.recorded_target_hwnd = None
                self.recorded_target_exe = "Unknown Window"
                self.anchor_status_lbl.configure(text="Anchor Window: Independent")
            
            self.is_recording = True
            self.record_btn.configure(text="■ Stop Capture", fg_color="#1e293b")
            self.status_label.configure(text="● RECORDING ACTIVE", text_color=ACCENT_RED)
            self.refresh_timeline_ui()
            self.start_time = time.time()
            self.record_hud = LiveHUD(self, "recording", stop_callback=self.toggle_recording)
            self.mouse_listener, self.keyboard_listener = mouse.Listener(on_click=self.on_click), keyboard.Listener(on_press=self.on_press, on_release=self.on_release)
            self.mouse_listener.start()
            self.keyboard_listener.start()
        else:
            self.is_recording = False
            self.record_btn.configure(text=f"🔴 Capture Sequence ({self.selected_record_hotkey})", fg_color=ACCENT_RED)
            self.status_label.configure(text="● STABLE SYSTEM IDLE", text_color=TEXT_MUTED)
            self.mouse_listener.stop()
            self.keyboard_listener.stop()
            if hasattr(self, 'record_hud') and self.record_hud:
                try:
                    self.record_hud.destroy()
                except Exception:
                    pass
                self.record_hud = None

    def on_click(self, x, y, button, pressed):
        if not self.is_recording:
            return
        if pressed:
            # Avoid recording clicks that happen inside the macro app window
            try:
                ax, ay = self.winfo_rootx(), self.winfo_rooty()
                aw, ah = self.winfo_width(), self.winfo_height()
                if ax <= x <= ax + aw and ay <= y <= ay + ah:
                    return
            except Exception:
                pass

            use_coords = (self.record_coords_switch_var.get() == "on")
            
            # Calculate relative coordinates if anchor is set
            rel_x, rel_y = None, None
            if use_coords:
                rel_x, rel_y = x, y
                if self.recorded_target_hwnd:
                    rect = RECT()
                    if GetWindowRect(self.recorded_target_hwnd, ctypes.byref(rect)):
                        rel_x = x - rect.left
                        rel_y = y - rect.top

            d = time.time() - self.start_time
            self.start_time = time.time()
            
            self.after(0, lambda: self.add_single_action_to_live_ui({
                'type': 'mouse',
                'rel_x': rel_x,
                'rel_y': rel_y,
                'use_coords': use_coords,
                'details': (x, y, str(button)),
                'delay': d
            }))

    def on_press(self, key):
        if not self.is_recording:
            return
        vk, name = self._extract_key_info(key)
        if vk is not None:
            if name == self.selected_record_hotkey.upper() or name == self.selected_play_hotkey.upper():
                return
            d = time.time() - self.start_time
            self.start_time = time.time()
            self.after(0, lambda: self.add_single_action_to_live_ui({
                'type': 'keyboard',
                'vk': vk,
                'name': name,
                'is_release': False,
                'delay': d
            }))

    def on_release(self, key):
        if not self.is_recording:
            return
        vk, name = self._extract_key_info(key)
        if vk is not None:
            if name == self.selected_record_hotkey.upper() or name == self.selected_play_hotkey.upper():
                return
            d = time.time() - self.start_time
            self.start_time = time.time()
            self.after(0, lambda: self.add_single_action_to_live_ui({
                'type': 'keyboard',
                'vk': vk,
                'name': name,
                'is_release': True,
                'delay': d
            }))

    def _extract_key_info(self, key):
        vk = None
        name = None
        if hasattr(key, 'vk') and key.vk is not None:
            vk = key.vk
        elif hasattr(key, 'value') and hasattr(key.value, 'vk') and key.value.vk is not None:
            vk = key.value.vk
            
        if hasattr(key, 'char') and key.char is not None:
            name = key.char.upper()
        elif hasattr(key, 'name') and key.name is not None:
            name = key.name.upper()
        elif hasattr(key, 'value') and hasattr(key.value, 'char') and key.value.char is not None:
            name = key.value.char.upper()
            
        if not name and vk is not None:
            for k in keyboard.Key:
                if hasattr(k, 'value') and hasattr(k.value, 'vk') and k.value.vk == vk:
                    name = k.name.upper()
                    break
            if not name:
                name = f"VK_{vk}"
        return vk, name

    def trigger_manual_action_choice_flow(self):
        if self.is_playing or self.is_recording: return
        if getattr(self, 'is_listening_manual_action', False):
            self.stop_manual_action_listener()
            return
            
        self.is_listening_manual_action = True
        self.add_manual_btn.configure(text="🔴 Click/Key anywhere...", fg_color="#ef4444")
        
        from pynput import mouse, keyboard
        self.manual_mouse_listener = None
        self.manual_key_listener = None
        
        def on_click(x, y, button, pressed):
            if pressed:
                app_x = self.winfo_rootx()
                app_y = self.winfo_rooty()
                app_w = self.winfo_width()
                app_h = self.winfo_height()
                if app_x <= x <= app_x + app_w and app_y <= y <= app_y + app_h:
                    return True
                
                self.after(0, lambda: self.handle_manual_overlay_callback('mouse', {'x': x, 'y': y}))
                self.after(0, self.stop_manual_action_listener)
                return False
                
        def on_press(key):
            vk = None
            name = None
            if hasattr(key, 'vk'):
                vk = key.vk
            elif hasattr(key, 'value') and hasattr(key.value, 'vk'):
                vk = key.value.vk
            
            if hasattr(key, 'name'):
                name = key.name.upper()
            else:
                try:
                    name = key.char.upper()
                except:
                    name = str(key).upper()
                    
            if name == "ESC" or name == "ESCAPE":
                self.after(0, self.stop_manual_action_listener)
                return False
                
            sym_map = {
                "RETURN": "ENTER",
                "SPACE": "SPACE",
                "ESCAPE": "ESC",
                "TAB": "TAB",
                "BACKSPACE": "BACKSPACE"
            }
            name = sym_map.get(name, name)
            
            if vk is None:
                vk = get_vk_from_key_name(name)
                
            final_vk = vk
            final_name = name
            
            self.after(0, lambda: self.handle_manual_overlay_callback('keyboard', {'vk': final_vk, 'name': final_name}))
            self.after(0, self.stop_manual_action_listener)
            return False

        self.manual_mouse_listener = mouse.Listener(on_click=on_click)
        self.manual_key_listener = keyboard.Listener(on_press=on_press)
        
        self.manual_mouse_listener.start()
        self.manual_key_listener.start()

    def stop_manual_action_listener(self):
        self.is_listening_manual_action = False
        self.add_manual_btn.configure(text="➕ Add Action", fg_color=ACCENT_BLUE)
        if hasattr(self, 'manual_mouse_listener') and self.manual_mouse_listener:
            try: self.manual_mouse_listener.stop()
            except: pass
            self.manual_mouse_listener = None
        if hasattr(self, 'manual_key_listener') and self.manual_key_listener:
            try: self.manual_key_listener.stop()
            except: pass
            self.manual_key_listener = None

    def handle_manual_overlay_callback(self, action_type, data):
        if action_type == 'mouse':
            x, y = data['x'], data['y']
            use_coords = (self.record_coords_switch_var.get() == "on")
            rel_x, rel_y = None, None
            if use_coords:
                rel_x, rel_y = x, y
                if self.recorded_target_hwnd:
                    rect = RECT()
                    if GetWindowRect(self.recorded_target_hwnd, ctypes.byref(rect)):
                        rel_x = x - rect.left
                        rel_y = y - rect.top
            self.add_single_action_to_live_ui({
                'type': 'mouse',
                'rel_x': rel_x,
                'rel_y': rel_y,
                'use_coords': use_coords,
                'details': (x, y, "Button.left"),
                'delay': 1.0
            })
        elif action_type == 'keyboard':
            vk, name = data['vk'], data['name']
            self.add_single_action_to_live_ui({'type': 'keyboard', 'vk': vk, 'name': name, 'is_release': False, 'delay': 1.0})
            self.add_single_action_to_live_ui({'type': 'keyboard', 'vk': vk, 'name': name, 'is_release': True, 'delay': 0.05})

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
        row = ctk.CTkFrame(self.timeline_scroll, fg_color=PANEL_BG, border_color=BORDER_COLOR, border_width=1, corner_radius=6, height=40)
        row.pack(fill="x", pady=3, padx=5)
        row.pack_propagate(False)
        
        # Show image preview thumbnail next to action description
        if action['type'] == 'image_match_wait' and 'image_path' in action and os.path.exists(action['image_path']):
            try:
                from PIL import Image, ImageTk
                img = Image.open(action['image_path'])
                img.thumbnail((24, 24))
                photo = ImageTk.PhotoImage(img)
                row._thumbnail = photo # Keep reference
                thumb_label = ctk.CTkLabel(row, image=photo, text="")
                thumb_label.pack(side="left", padx=(6, 2))
            except Exception as e:
                pass

        lbl = ctk.CTkButton(row, text=self._action_text(idx, action), anchor="w", fg_color="transparent", font=ctk.CTkFont(family="Consolas", size=11), corner_radius=0, command=lambda i=idx: self.select_timeline_item(i))
        lbl.pack(side="left", fill="both", expand=True)
        
        lbl.bind("<ButtonPress-1>", lambda e, i=idx: self.on_row_drag_start(e, i), add="+")
        lbl.bind("<B1-Motion>", lambda e, i=idx: self.on_row_drag_motion(e, i))
        lbl.bind("<ButtonRelease-1>", lambda e, i=idx: self.on_row_drag_release(e, i))
        lbl.bind("<Double-Button-1>", lambda e, i=idx: self.open_action_editor_modal(i))
        row.bind("<Double-Button-1>", lambda e, i=idx: self.open_action_editor_modal(i))

        def_ = ctk.CTkFrame(row, fg_color="transparent")
        def_.pack(side="right", padx=4, fill="y")
        
        ent = ctk.CTkEntry(def_, width=48, height=24, font=ctk.CTkFont(family="Consolas", size=11), fg_color=APP_BG, border_color=BORDER_COLOR)
        ent.insert(0, f"{action['delay']:.2f}")
        ent.pack(side="left", padx=2)
        ent.bind("<FocusOut>", lambda e, i=idx, en=ent: self.update_action_delay(i, en.get()))
        
        del_btn = ctk.CTkButton(def_, text="✕", width=22, height=24, fg_color="transparent", text_color=TEXT_MUTED, hover_color=ACCENT_RED, font=ctk.CTkFont(size=11, weight="bold"), command=lambda i=idx: self.delete_specific_action_node(i))
        del_btn.pack(side="right", padx=2)
        
        if hasattr(self, 'record_hud') and self.record_hud:
            self.record_hud.set_captured_count(len(self.macro_actions))
            desc = self._action_text(idx, action)
            if "]" in desc:
                desc = desc.split("]", 1)[1].strip()
            self.record_hud.set_active_action(desc)

        self.action_ui_rows.append(row)

    def delete_specific_action_node(self, target_index):
        if self.is_playing or self.is_recording: return
        if target_index < len(self.macro_actions):
            self.macro_actions.pop(target_index)
            self.profiles_db[self.active_profile_name] = list(self.macro_actions)
            
            row_to_destroy = self.action_ui_rows[target_index]
            self.action_ui_rows.pop(target_index)
            row_to_destroy.destroy()
            
            self.reindex_timeline_rows()
            self.selected_action_index = None

    def reindex_timeline_rows(self):
        for idx, row in enumerate(self.action_ui_rows):
            action = self.macro_actions[idx]
            row.bind("<Double-Button-1>", lambda e, i=idx: self.open_action_editor_modal(i))
            for child in row.winfo_children():
                if isinstance(child, ctk.CTkButton):
                    child.configure(text=self._action_text(idx, action), command=lambda i=idx: self.select_timeline_item(i))
                    child.bind("<ButtonPress-1>", lambda e, i=idx: self.on_row_drag_start(e, i), add="+")
                    child.bind("<B1-Motion>", lambda e, i=idx: self.on_row_drag_motion(e, i))
                    child.bind("<ButtonRelease-1>", lambda e, i=idx: self.on_row_drag_release(e, i))
                    child.bind("<Double-Button-1>", lambda e, i=idx: self.open_action_editor_modal(i))
                elif isinstance(child, ctk.CTkFrame):
                    for sub_child in child.winfo_children():
                        if isinstance(sub_child, ctk.CTkEntry):
                            sub_child.bind("<FocusOut>", lambda e, i=idx, en=sub_child: self.update_action_delay(i, en.get()))
                        elif isinstance(sub_child, ctk.CTkButton) and sub_child.cget("text") == "✕":
                            sub_child.configure(command=lambda i=idx: self.delete_specific_action_node(i))

    def refresh_timeline_ui(self):
        for r in self.action_ui_rows: r.destroy()
        self.action_ui_rows.clear()
        acts = list(self.macro_actions); self.macro_actions = []
        for a in acts: self.add_single_action_to_live_ui(a)

    def select_timeline_item(self, index):
        if index < 0 or index >= len(self.macro_actions): return
        old = self.selected_action_index; self.selected_action_index = index
        if old is not None and old < len(self.action_ui_rows): self.action_ui_rows[old].configure(fg_color=PANEL_BG)
        if index < len(self.action_ui_rows): self.action_ui_rows[index].configure(fg_color="#1e1b4b")
        action = self.macro_actions[index]
        if action['type'] in ('ocr_wait', 'ocr_click'):
            query = action.get('text_query', '')
            self.ocr_text_label.configure(text=f"Active OCR Text: \"{query}\"", text_color=ACCENT_PURPLE)
            self.vision_query_entry.delete(0, 'end')
            self.vision_query_entry.insert(0, query)
        else:
            self.ocr_text_label.configure(text="No text query active", text_color=TEXT_MUTED)

    def update_ocr_text_label(self, event=None):
        query = self.vision_query_entry.get().strip()
        if query:
            self.ocr_text_label.configure(text=f"Active OCR Text: \"{query}\"", text_color=ACCENT_PURPLE)
        else:
            self.ocr_text_label.configure(text="No text query active", text_color=TEXT_MUTED)

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
                self.count_entry = ctk.CTkEntry(rf, width=45, height=24, fg_color=APP_BG, border_color=BORDER_COLOR)
                self.count_entry.insert(0, "5")
                self.count_entry.pack(side="left", padx=4)
            ctk.CTkLabel(rf, text="Pause:", font=ctk.CTkFont(size=12)).pack(side="left", padx=8)
            self.loop_delay_entry = ctk.CTkEntry(rf, width=45, height=24, fg_color=APP_BG, border_color=BORDER_COLOR)
            self.loop_delay_entry.insert(0, "0.1")
            self.loop_delay_entry.pack(side="left", padx=4)

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
                    self.after(0, self.stop_playback_ui_reset)
                    return
                
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

    def check_global_text_trigger_match(self):
        import pyautogui
        is_bg = False
        hwnd = None

        if self.global_text_trigger_region:
            rx, ry, rw, rh = self.global_text_trigger_region
            base_x, base_y = 0, 0
            if self.recorded_target_exe and self.recorded_target_exe != "Unknown Window":
                for win_info in get_all_visible_windows_info():
                    if win_info[1] == self.recorded_target_exe:
                        rect = RECT()
                        if GetWindowRect(win_info[0], ctypes.byref(rect)):
                            base_x, base_y = rect.left, rect.top
                        break
            tx = base_x + rx
            ty = base_y + ry
            if self.turbo_scan_switch_var.get() == "on":
                shot = win32_screenshot((tx, ty, rw, rh))
            else:
                shot = pyautogui.screenshot(region=(tx, ty, rw, rh))
        else:
            if self.turbo_scan_switch_var.get() == "on":
                shot = win32_screenshot()
            else:
                shot = pyautogui.screenshot()
            tx, ty = 0, 0
            
        os.makedirs("./assets", exist_ok=True)
        temp_ocr_path = os.path.abspath("./assets/temp_global_ocr.png")
        shot.save(temp_ocr_path)
        
        matched = False
        click_x, click_y = None, None
        
        try:
            if self.global_text_trigger_mode == "click":
                coords = self.find_text_coordinates_in_file(temp_ocr_path, self.global_text_trigger_text)
                if coords is not None:
                    matched = True
                    click_x = tx + int(coords[0])
                    click_y = ty + int(coords[1])
            else:
                recognized_text = self.perform_ocr_on_file(temp_ocr_path)
                if self.global_text_trigger_text.strip().lower() in recognized_text.lower():
                    matched = True
        except Exception as e:
            print(f"Global OCR Trigger error: {e}")
            
        if os.path.exists(temp_ocr_path):
            try: os.remove(temp_ocr_path)
            except: pass
            
        return matched, click_x, click_y

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
                'actions': self.macro_actions,
                'global_text_trigger_enabled': (self.text_trigger_switch_var.get() == "on"),
                'global_text_trigger_text': self.global_text_trigger_text,
                'global_text_trigger_mode': self.global_text_trigger_mode,
                'global_text_trigger_region': self.global_text_trigger_region,
                'global_text_trigger_whole_screen': (self.ocr_whole_screen_var.get() == "on")
            }
            with open(fp, 'w') as f: 
                json.dump(payload, f, indent=4)
            messagebox.showinfo("Export Successful", "Macro profile saved successfully!")

    def import_macro(self):
        fp = filedialog.askopenfilename(filetypes=[("JSON Profile", "*.json")])
        if fp:
            try:
                with open(fp, 'r') as f: 
                    data = json.load(f)
                
                self.recorded_target_exe = data.get('target', 'Unknown Window')
                raw_actions = data.get('actions', [])
                
                encoded_image = data.get('embedded_trigger_image')
                if encoded_image:
                    os.makedirs("./assets", exist_ok=True)
                    reconstructed_path = f"./assets/global_trigger_active.png"
                    
                    with open(reconstructed_path, "wb") as image_out:
                        image_out.write(base64.b64decode(encoded_image))
                        
                    self.global_trigger_image_path = reconstructed_path
                    self.trigger_status_title.configure(text=f"📷 TRIGGER IMAGE BOUND: TRIGGER_ACTIVE.PNG", text_color=ACCENT_GREEN)
                    
                    self.img_trigger_switch_var.set("on")
                    self.toggle_image_trigger_view()
                    self.trigger_image_label.configure(text="Trigger Image: global_trigger_active.png (Loaded)", text_color=ACCENT_GREEN)
                    self.render_center_panel_preview(reconstructed_path)
                    
                    for action in raw_actions:
                        if action.get('type') == 'image_match_wait':
                            action['image_path'] = reconstructed_path
                else:
                    self.remove_global_trigger_image()

                self.global_text_trigger_text = data.get('global_text_trigger_text', '')
                self.global_text_trigger_mode = data.get('global_text_trigger_mode', 'wait')
                self.global_text_trigger_region = data.get('global_text_trigger_region', None)
                
                ws_val = "on" if data.get('global_text_trigger_whole_screen', True) else "off"
                self.ocr_whole_screen_var.set(ws_val)
                
                enabled_text = data.get('global_text_trigger_enabled', False)
                if enabled_text and self.global_text_trigger_text:
                    self.text_trigger_switch_var.set("on")
                    self.toggle_text_trigger_view()
                    region_str = "Whole Screen" if not self.global_text_trigger_region else f"Region {self.global_text_trigger_region}"
                    self.ocr_text_label.configure(
                        text=f"Trigger Text ({self.global_text_trigger_mode.upper()}): \"{self.global_text_trigger_text}\" on {region_str}",
                        text_color=ACCENT_GREEN
                    )
                else:
                    self.text_trigger_switch_var.set("off")
                    self.toggle_text_trigger_view()

                self.macro_actions = raw_actions
                self.refresh_timeline_ui()
            except Exception as error:
                messagebox.showerror("Import Error", f"Failed to open macro file: {str(error)}")

    def _action_text(self, idx, action):
        if action['type'] == 'mouse':
            use_coords = action.get('use_coords', True)
            if use_coords and action.get('rel_x') is not None:
                return f"🎯 [{idx+1:02d}] Click ➔ [X:{action['rel_x']}, Y:{action['rel_y']}]"
            else:
                return f"🎯 [{idx+1:02d}] Click ➔ [Current Position]"
        if action['type'] == 'pixel_wait': return f"🎨 [{idx+1:02d}] Pixel Match ➔ {action['color']}"
        if action['type'] == 'image_match_wait':
            kp = action.get('key_to_press')
            if kp:
                click_flag = f"Press [{kp.upper()}]"
            else:
                click_flag = "Click" if action.get('click_on_match', False) else "Wait"
            
            pos = action.get('click_position', 'Center')
            pos_suffix = f" ({pos})" if pos != 'Center' else ""
            
            conf = action.get('confidence', 0.85)
            conf_str = f" [Obscured {int(conf*100)}%]" if conf < 0.80 else ""
            engine = action.get('match_engine', 'standard')
            engine_str = f" [{engine}]" if engine != 'standard' else ""
            
            cond_flag = f" (Branch T➔{action.get('goto_true')} F➔{action.get('goto_false')})" if action.get('is_conditional', False) else ""
            return f"📸 [{idx+1:02d}] Icon Match ➔ {click_flag}{pos_suffix} {os.path.basename(action['image_path'])}{conf_str}{engine_str}{cond_flag}"
        if action['type'] == 'ocr_wait': return f"📝 [{idx+1:02d}] Wait for Text ➔ \"{action['text_query']}\""
        if action['type'] == 'ocr_click': return f"🔍 [{idx+1:02d}] OCR Click ➔ \"{action['text_query']}\""
        
        if action['type'] == 'controller':
            if 'trigger' in action['action'] or 'stick' in action['action']:
                return f"🎮 [{idx+1:02d}] Gamepad ➔ {action['action'].replace('_',' ').upper()}: [{action['name']}]"
            if 'button' in action['action']:
                return f"🎮 [{idx+1:02d}] Gamepad ➔ {action['action'].replace('_',' ').upper()}: [{action['index']}]"
            return f"🎮 [{idx+1:02d}] Gamepad ➔ Directional: [{action['name']}]"

        repeats = action.get('repeat_count', 1)
        hold_suffix = f" (Held down x{repeats})" if (not action.get('is_release') and repeats > 1) else ""
        return f"⌨️ [{idx+1:02d}] Key { 'UP' if action.get('is_release') else 'DOWN' } ➔ [{action.get('name','?')}] {hold_suffix}"


if __name__ == "__main__":
    app = MacroApp()
    app.mainloop()