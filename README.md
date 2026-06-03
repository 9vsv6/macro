# Vision Macro Suite Pro made by AI

A powerful, high-performance desktop automation platform built with Python and CustomTkinter. Unlike standard macro recorders that rely blindly on static timers, **Vision Macro Suite Pro** utilizes low-level Windows APIs and advanced computer vision algorithms to create intelligent, context-aware, and humanized automation workflows.

<img width="1276" height="905" alt="image" src="https://github.com/user-attachments/assets/0528ec0c-2783-46d7-a87e-90500a07c215" />


## ✨ Key Features

### ⚓ Window-Relative Smart Anchoring
* Coordinates are calculated dynamically based on the target application's window frame (`GetWindowRect`), not absolute screen space.
* Drag, resize, or move your target application across different monitors—the macro adapts and clicks perfectly every time.

### 📸 Intelligent Vision Triggers
* **Global Image Activation:** Set a master startup image via the center control panel. The sequence stays paused until that exact graphic is found on your desktop.
* **On-Screen Snipping Tool:** Freeze your display behind a live mask and slice custom target templates natively without needing third-party crop tools.
* **OpenCV Pattern Matching:** Uses optimized template-matching matrix scaling for rapid visual asset recognition with adjustable confidence criteria.

### 🛡️ Low-Level Input & Anti-Detection Humanization
* **Bézier Trajectory Curves:** Mouse actions simulate authentic human velocity changes (acceleration/deceleration paths) instead of robotic linear jumps.
* **Target Jitter Randomization:** Click positions introduce minor algorithmic coordinate variations to bypass standard automated bot-pattern detection algorithms.
* **Direct Hardware Emulation:** Leverages the Windows native `SendInput` API structurally to write keystrokes directly into low-level window hook managers.

### 🗃️ Advanced Workflow & Profile Management
* **Held Key Compression:** Automatically compresses rapid, repeating keyboard inputs into a single row block with an embedded `repeat_count` property.
* **Visual Pipeline Timeline:** Reorder action nodes dynamically using responsive left-click drag-and-drop mechanics.
* **Single-File portability:** Profiles encode graphic assets natively into standard Base64 text arrays, allowing complete actions + image triggers to export into one portable `.json` profile.
* **Collapsible Catalog Sidebar:** Categorize, manage, and instantly swap between distinct automated profile setups with a single click.

---

## 🚀 Installation & Prerequisites

This application requires **Python 3.8+** and a **64-bit Windows Environment** due to direct dependency calls on the `ctypes` User32 and GDI32 system libraries.

1. Clone the repository:
   ```bash
   git clone [https://github.com/9vsv6/macro.git](https://github.com/9vsv6/macro.git)
   cd macro
2. pip install pyinstaller
3. pip install customtkinter
4. pip install pillow
5. pip install opencv-python pyautogui
6. pyinstaller macro_app.spec
