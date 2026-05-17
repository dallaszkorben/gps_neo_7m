"""CAM view — live MJPEG streams from ESP32 cameras with auto-discovery.

Display modes:
- GRID mode: all cameras shown in an auto-sized grid layout
- FOCUS mode: single selected camera shown fullscreen

Tap a camera in grid mode to enter focus mode.
Press CAM button to return to grid mode.
Switching to another view resets to grid mode.
"""

import tkinter as tk
import threading
import io
import math
from PIL import Image, ImageTk, ImageDraw, ImageFont
from cam_discovery import get_cameras, reset as reset_cam_discovery
import urllib.request as cam_urllib
import time as _time


# Stream state
_streams = {}   # {url: {"running": bool, "frame": bytes|None, "last_frame_time": float}}
_known_urls = set()
_NO_SIGNAL_TIMEOUT = 3

# Display mode: "grid" (all cameras) or "focus" (single camera fullscreen)
_mode = "grid"
# In focus mode, the URL of the focused camera
_focus_url = None
# Grid layout info for click detection
_grid_info = {"cols": 0, "rows": 0, "cell_w": 0, "cell_h": 0, "n": 0}


def _is_stale(state):
    """Check if a camera stream has not received frames for too long."""
    return (_time.time() - state.get("last_frame_time", 0)) > _NO_SIGNAL_TIMEOUT


def _draw_no_signal(img, color="red"):
    """Draw 'No Signal' text centered on an image."""
    draw = ImageDraw.Draw(img)
    text = "No Signal"
    try:
        font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 48)
    except Exception:
        font = ImageFont.load_default()
    bbox = draw.textbbox((0, 0), text, font=font)
    tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
    iw, ih = img.size
    x = (iw - tw) // 2
    y = (ih - th) // 2
    draw.text((x, y), text, fill=color, font=font)
    return img


def create(parent, fonts):
    """Create the CAM view frame and label widget.

    Returns (frame, label) — the label is used for all camera display,
    updated every 50ms with the latest composite image.
    """
    frame = tk.Frame(parent, bg='black')
    label = tk.Label(frame, text="Searching for cameras...",
                     font=fonts["FONT_STATUS"], fg="white", bg="black")
    label.pack(fill="both", expand=True)

    # Tap on camera display: in grid mode selects a camera (enters focus mode)
    label.bind("<Button-1>", _on_click)

    return frame, label


def _on_click(event):
    """Handle tap on camera display."""
    global _mode, _focus_url

    if _mode == "focus":
        # Tap in focus mode returns to grid mode
        _mode = "grid"
        _focus_url = None
        return

    # Grid mode: determine which camera was tapped
    urls = list(_streams.keys())
    n = _grid_info["n"]

    if n <= 1:
        # Single camera in grid — tap enters focus mode for it
        if n == 1:
            _mode = "focus"
            _focus_url = urls[0]
        return

    # Multi-camera grid: calculate which cell was tapped
    cols = _grid_info["cols"]
    cell_w = _grid_info["cell_w"]
    cell_h = _grid_info["cell_h"]

    if cell_w <= 0 or cell_h <= 0:
        return

    col = event.x // cell_w
    row = event.y // cell_h
    index = row * cols + col

    if index < n:
        _mode = "focus"
        _focus_url = urls[index]


def stop_all():
    """Stop all camera streams and clear state.

    Called every time the user leaves CAM view.
    """
    global _streams, _known_urls, _mode, _focus_url
    for s in _streams.values():
        s["running"] = False
    _streams = {}
    _known_urls = set()
    _mode = "grid"
    _focus_url = None


def on_show(root, rebuild_delay=2000):
    """Called when switching to CAM view — reset to grid mode and rediscover.

    Pressing CAM button always returns to grid mode with fresh discovery.
    """
    global _mode, _focus_url
    _mode = "grid"
    _focus_url = None
    reset_cam_discovery()
    root.after(rebuild_delay, _start_new_cameras)


def _start_new_cameras():
    """Start streams for newly discovered cameras without stopping existing ones."""
    global _known_urls
    cameras = get_cameras()
    new_urls = {url for url in cameras.values()} - _known_urls
    for url in new_urls:
        state = {"running": True, "frame": None, "last_frame_time": _time.time()}
        t = threading.Thread(target=_reader, args=(url, state), daemon=True)
        t.start()
        _streams[url] = state
        _known_urls.add(url)


def _reader(url, state):
    """Background thread: reads MJPEG stream, extracts JPEG frames."""
    MAX_BUF = 200000
    while state["running"]:
        try:
            stream = cam_urllib.urlopen(url, timeout=5)
            stream.fp.raw._sock.settimeout(10)
            buf = b""
            while state["running"]:
                chunk = stream.read(4096)
                if not chunk:
                    break
                buf += chunk
                if len(buf) > MAX_BUF:
                    buf = buf[-MAX_BUF:]
                while True:
                    s = buf.find(b"\xff\xd8")
                    e = buf.find(b"\xff\xd9", s + 2) if s != -1 else -1
                    if s != -1 and e != -1:
                        state["frame"] = buf[s:e + 2]
                        state["last_frame_time"] = _time.time()
                        buf = buf[e + 2:]
                    else:
                        break
        except Exception:
            pass
        _time.sleep(1)


def update_cam(root, label, config, get_view_mode, running_flag):
    """Update camera display. Schedules itself every 50ms (~20fps)."""
    try:
        if get_view_mode() == "cam":
            _start_new_cameras()
            urls = list(_streams.keys())
            n = len(urls)

            if n == 0:
                label.config(text="Searching for cameras...", image="")
                label.image = None
            elif _mode == "focus" and _focus_url in _streams:
                # Focus mode: show selected camera fullscreen
                _display_focus(root, label, config)
            elif n == 1:
                _display_single(root, label, urls[0], config)
            else:
                _display_grid(root, label, urls, n, config)
    except Exception:
        pass

    if running_flag[0]:
        root.after(50, lambda: update_cam(root, label, config, get_view_mode, running_flag))


def _display_focus(root, label, config):
    """Focus mode: display the selected camera fullscreen."""
    f = _streams[_focus_url]["frame"]
    if not f:
        return
    try:
        img = Image.open(io.BytesIO(f))
        rot = config.getint("cam", "rotation", fallback=0)
        if rot:
            img = img.rotate(-rot, expand=True)
        w = root.winfo_width() - 120
        h = root.winfo_height()
        if w > 50 and h > 50:
            iw, ih = img.size
            scale = min(w / iw, h / ih)
            img = img.resize((int(iw * scale), int(ih * scale)), Image.BILINEAR)
        if _is_stale(_streams[_focus_url]):
            err_color = config.get("coords", "error_color", fallback="red")
            img = _draw_no_signal(img, err_color)
        photo = ImageTk.PhotoImage(img)
        label.config(image=photo, text="")
        label.image = photo
    except Exception:
        pass


def _display_single(root, label, url, config):
    """Grid mode with 1 camera: display fullscreen."""
    global _grid_info
    f = _streams[url]["frame"]
    if not f:
        return
    try:
        img = Image.open(io.BytesIO(f))
        rot = config.getint("cam", "rotation", fallback=0)
        if rot:
            img = img.rotate(-rot, expand=True)
        w = root.winfo_width() - 120
        h = root.winfo_height()
        if w > 50 and h > 50:
            iw, ih = img.size
            scale = min(w / iw, h / ih)
            img = img.resize((int(iw * scale), int(ih * scale)), Image.BILINEAR)
        if _is_stale(_streams[url]):
            err_color = config.get("coords", "error_color", fallback="red")
            img = _draw_no_signal(img, err_color)
        _grid_info = {"cols": 1, "rows": 1, "cell_w": img.size[0], "cell_h": img.size[1], "n": 1}
        photo = ImageTk.PhotoImage(img)
        label.config(image=photo, text="")
        label.image = photo
    except Exception:
        pass


def _display_grid(root, label, urls, n, config):
    """Grid mode: display all cameras in a composite grid."""
    global _grid_info
    cols = math.ceil(math.sqrt(n))
    rows = math.ceil(n / cols)
    w = root.winfo_width() - 120
    h = root.winfo_height()
    if w <= 50 or h <= 50:
        return
    cell_w = w // cols
    cell_h = h // rows
    _grid_info = {"cols": cols, "rows": rows, "cell_w": cell_w, "cell_h": cell_h, "n": n}
    composite = Image.new("RGB", (w, h), "black")
    has_frame = False
    for i, url in enumerate(urls):
        f = _streams[url]["frame"]
        if f:
            has_frame = True
            try:
                img = Image.open(io.BytesIO(f))
                rot = config.getint("cam", "rotation", fallback=0)
                if rot:
                    img = img.rotate(-rot, expand=True)
                iw, ih = img.size
                scale = min(cell_w / iw, cell_h / ih)
                img = img.resize((int(iw * scale), int(ih * scale)), Image.BILINEAR)
                if _is_stale(_streams[url]):
                    err_color = config.get("coords", "error_color", fallback="red")
                    img = _draw_no_signal(img, err_color)
                r = i // cols
                c = i % cols
                composite.paste(img, (c * cell_w, r * cell_h))
            except Exception:
                pass
    if has_frame:
        photo = ImageTk.PhotoImage(composite)
        label.config(image=photo, text="")
        label.image = photo
