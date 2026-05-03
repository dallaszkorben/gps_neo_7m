"""CAM view — live MJPEG streams from ESP32 cameras with auto-discovery."""

import tkinter as tk
import threading
import io
import math
from PIL import Image, ImageTk
from cam_discovery import start as start_cam_discovery, get_cameras, reset as reset_cam_discovery
import urllib.request as cam_urllib


# Module-level state
_streams = {}   # {url: {"running": bool, "frame": bytes|None}}
_known = {}     # {name: url}


def create(parent, fonts):
    """Create the CAM view frame and return (frame, update_func, on_show).

    Args:
        parent: parent tkinter widget
        fonts: dict with FONT_STATUS
    Returns:
        frame, update_cam, on_show, stop_all
    """
    frame = tk.Frame(parent, bg='black')
    label = tk.Label(frame, text="Searching for cameras...",
                     font=fonts["FONT_STATUS"], fg="white", bg="black")
    label.pack(fill="both", expand=True)

    return frame, label


def stop_all():
    """Stop all camera streams."""
    global _streams, _known
    for s in _streams.values():
        s["running"] = False
    _streams = {}
    _known = {}


def on_show(root, rebuild_delay=2000):
    """Called when switching to CAM view — reset discovery and rebuild."""
    reset_cam_discovery()
    root.after(rebuild_delay, rebuild_grid)


def rebuild_grid():
    """Stop old streams, discover cameras, start new streams."""
    global _known, _streams
    # Stop old
    for s in _streams.values():
        s["running"] = False
    _streams = {}
    _known = {}
    # Discover
    cameras = get_cameras()
    _known = cameras
    # Start new streams
    for name, url in cameras.items():
        state = {"running": True, "frame": None}
        t = threading.Thread(target=_reader, args=(url, state), daemon=True)
        t.start()
        _streams[url] = state


def _reader(url, state):
    """Background thread: reads MJPEG stream, extracts JPEG frames."""
    import time as _t
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
                        buf = buf[e + 2:]
                    else:
                        break
        except Exception:
            pass
        _t.sleep(1)


def update_cam(root, label, config, get_view_mode, running_flag):
    """Update camera display. Schedules itself via root.after.

    Args:
        root: tk root window
        label: the cam_label widget
        config: ConfigParser instance (re-read for rotation)
        get_view_mode: callable returning current view mode string
        running_flag: list with single bool [True/False]
    """
    global _known, _streams

    if get_view_mode() == "cam":
        # Auto-rebuild if new cameras appeared
        cameras = get_cameras()
        if len(cameras) > len(_known):
            rebuild_grid()

        urls = list(_streams.keys())
        n = len(urls)

        if n == 0:
            label.config(text="Searching for cameras...", image="")
            label.image = None
        elif n == 1:
            _display_single(root, label, urls[0], config)
        else:
            _display_multi(root, label, urls, n, config)

    if running_flag[0]:
        root.after(50, lambda: update_cam(root, label, config, get_view_mode, running_flag))


def _get_rotation(config):
    """Read rotation from config (re-reads each frame for live changes)."""
    return config.getint("cam", "rotation", fallback=0)


def _display_single(root, label, url, config):
    """Display a single camera fullscreen."""
    f = _streams[url]["frame"]
    if not f:
        return
    _streams[url]["frame"] = None
    try:
        img = Image.open(io.BytesIO(f))
        rot = _get_rotation(config)
        if rot:
            img = img.rotate(-rot, expand=True)
        w = root.winfo_width() - 120
        h = root.winfo_height()
        if w > 50 and h > 50:
            iw, ih = img.size
            scale = min(w / iw, h / ih)
            img = img.resize((int(iw * scale), int(ih * scale)), Image.LANCZOS)
        photo = ImageTk.PhotoImage(img)
        label.config(image=photo, text="")
        label.image = photo
    except Exception:
        pass


def _display_multi(root, label, urls, n, config):
    """Display multiple cameras in a grid composite."""
    cols = math.ceil(math.sqrt(n))
    rows = math.ceil(n / cols)
    w = root.winfo_width() - 120
    h = root.winfo_height()
    if w <= 50 or h <= 50:
        return
    cell_w = w // cols
    cell_h = h // rows
    composite = Image.new("RGB", (w, h), "black")
    for i, url in enumerate(urls):
        f = _streams[url]["frame"]
        if f:
            _streams[url]["frame"] = None
            try:
                img = Image.open(io.BytesIO(f))
                rot = _get_rotation(config)
                if rot:
                    img = img.rotate(-rot, expand=True)
                iw, ih = img.size
                scale = min(cell_w / iw, cell_h / ih)
                img = img.resize((int(iw * scale), int(ih * scale)), Image.LANCZOS)
                r = i // cols
                c = i % cols
                composite.paste(img, (c * cell_w, r * cell_h))
            except Exception:
                pass
    photo = ImageTk.PhotoImage(composite)
    label.config(image=photo, text="")
    label.image = photo
