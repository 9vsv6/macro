# Macro by AI

A premium, state-of-the-art Windows macro automation suite featuring advanced vision triggers, optical character recognition (OCR), humanized input execution, and a sleek glassmorphic HUD.

---

## 🌟 Key Features

*   **📸 Global Sequence Image Trigger**: Block macro execution until a specific template image appears on the screen (includes real-time template preview rendering).
*   **📝 Global Sequence Text Trigger**: Wait for text occurrences or center mouse click coordinates using Windows Native OCR API. Supports both screen region snipping and full-screen scans.
*   **🛡️ Anti-Detection Humanization**:
    *   **Organic Bézier Curves**: Smooth, human-like mouse paths instead of straight lines.
    *   **Target Cursor Jitter**: Adds randomized micro-offsets on clicks.
*   **🖥️ Draggable Game HUD Overlay**: Draggable on-screen display (OSD) showing loop count, elapsed runtime, active action description, and quick stop button.
*   **⌨️ Real-time Capture & Timeline**: Record key presses and mouse clicks in real-time, modify action delays, and double-click actions to edit coordinates/keys in-place.
*   **🎮 Controller Hardware Hook**: Poll gamepad triggers, hats, and analog stick movements.
*   **💾 Profiles Manager**: Easily export/import actions, window anchors, and triggers to/from JSON files.

---

## 🚀 Getting Started

### Prerequisites

*   **OS**: Windows 10/11 (required for Windows Native Winsdk OCR Engine).
*   **Python**: Python 3.10+ is recommended.

### Installation

1. Clone the repository:
   ```bash
   git clone https://github.com/9vsv6/macro.git
   cd macro
   ```

2. Install the dependencies:
   ```bash
   pip install -r requirements.txt
   ```
   *(Ensure you have `customtkinter`, `pynput`, `pyautogui`, `opencv-python`, `numpy`, `pillow`, and `winsdk` installed).*

### Usage

Run the main application file:
```bash
python macro_app.py
```

---

## 📦 Building Executable

To compile the application into a standalone Windows `.exe` executable:
```bash
pip install pyinstaller
pyinstaller macro_app.spec
```
The compiled output will be available under the `dist/` directory.
