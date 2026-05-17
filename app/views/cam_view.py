"""CAM view — live MJPEG streams from ESP32 cameras with auto-discovery.

Features:
- Auto-discovers cameras via mDNS (no manual configuration)
- Adds new cameras without interrupting existing streams
- Shows "No Signal" overlay when a camera stops sending frames for 3+ seconds
- Supports configurable image rotation from CONF view
- Grid layout adapts automatically to camera count
"""

import tkinter as tk
import threading
import io
import math
from PIL import Image, ImageTk, ImageDraw, ImageFont
from cam_discovery import get_cameras, reset as reset_cam_discovery
import urllib.request as cam_urllib
import time as _time


# Module-level state (not instance-based) because tkinter is single-threaded
# and we only ever have one CAM view.
_streams = {}   # {url: {"running": bool, "frame": bytes|None, "last_frame_time": float}}
_known_urls = set()  # URLs we already have active streams for

# How long to wait without receiving a frame before showing "No Signal".
# 3 seconds balances between quick detection and avoiding false alarms
# during brief network hiccups.
_NO_SIGNAL_TIMEOUT = 3


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
    return frame, label


def stop_all():
    """Stop all camera streams and clear state.

    Called every time the user leaves CAM view. Streams are stopped to
    free network bandwidth (important on the Pi's single WiFi interface
    which is also serving as AP for the cameras).
    """
    global _streams, _known_urls
    for s in _streams.values():
        s["running"] = False
    _streams = {}
    _known_urls = set()


def on_show(root, rebuild_delay=2000):
    """Called when switching to CAM view — reset discovery and rebuild.

    Resets mDNS discovery cache so that only currently-alive cameras are
    shown. The 2s delay gives cameras time to respond to the new mDNS query.
    Without the delay, we'd often get 0 cameras on the first frame.
    """
    reset_cam_discovery()
    root.after(rebuild_delay, _start_new_cameras)


def _start_new_cameras():
    """Start streams for any newly discovered cameras without stopping existing ones.

    This is the key design choice: we never stop working streams when a new
    camera appears. We only add new ones. This prevents the black screen
    flash that happened when all streams were killed and restarted.
    """
    global _known_urls
    cameras = get_cameras()
    new_urls = {url for url in cameras.values()} - _known_urls
    for url in new_urls:
        # last_frame_time initialized to now so we don't immediately show
        # "No Signal" before the first frame arrives from the network.
        state = {"running": True, "frame": None, "last_frame_time": _time.time()}
        t = threading.Thread(target=_reader, args=(url, state), daemon=True)
        t.start()
        _streams[url] = state
        _known_urls.add(url)


def _reader(url, state):
    """Background thread: reads MJPEG stream, extracts JPEG frames.

    MJPEG is a sequence of JPEG images. We find frame boundaries by
    looking for JPEG SOI (0xFFD8) and EOI (0xFFD9) markers in the byte
    stream. Only the latest frame is kept — older frames are discarded
    to prevent lag buildup.

    Reconnects automatically on network errors (1s backoff). The ESP32
    cameras support only ~1 concurrent client, so if another client
    connects, this stream may drop and reconnect.
    """
    # Cap buffer at 200KB to prevent memory growth if frames aren't consumed
    MAX_BUF = 200000
    while state["running"]:
        try:
            stream = cam_urllib.urlopen(url, timeout=5)
            # Set socket timeout to detect dead connections faster than
            # the default (which can hang for minutes)
            stream.fp.raw._sock.settimeout(10)
            buf = b""
            while state["running"]:
                chunk = stream.read(4096)
                if not chunk:
                    break
                buf += chunk
                if len(buf) > MAX_BUF:
                    buf = buf[-MAX_BUF:]
                # Extract all complete JPEG frames from buffer
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
        # Brief pause before reconnect to avoid hammering a dead camera
        _time.sleep(1)


def update_cam(root, label, config, get_view_mode, running_flag):
    """Update camera display. Schedules itself every 50ms (~20fps).

    Only processes frames when CAM view is active to save CPU.
    Also checks for newly discovered cameras and starts streams for them.
    """
    try:
        if get_view_mode() == "cam":
            _start_new_cameras()
            urls = list(_streams.keys())
            n = len(urls)

            if n == 0:
                label.config(text="Searching for cameras...", image="")
                label.image = None
            elif n == 1:
                _display_single(root, label, urls[0], config)
            else:
                _display_multi(root, label, urls, n, config)
    except Exception:
        pass

    if running_flag[0]:
        root.after(50, lambda: update_cam(root, label, config, get_view_mode, running_flag))


def _display_single(root, label, url, config):
    """Display a single camera fullscreen with aspect ratio preserved."""
    f = _streams[url]["frame"]
    if not f:
        return
    try:
        img = Image.open(io.BytesIO(f))
        rot = config.getint("cam", "rotation", fallback=0)
        if rot:
            # Negative because PIL rotates counter-clockwise but users
            # expect clockwise (90° = turn right)
            img = img.rotate(-rot, expand=True)
        # Subtract button panel width (120px) from available space
        w = root.winfo_width() - 120
        h = root.winfo_height()
        if w > 50 and h > 50:
            iw, ih = img.size
            scale = min(w / iw, h / ih)
            img = img.resize((int(iw * scale), int(ih * scale)), Image.BILINEAR)
        # Show "No Signal" overlay if no new frame for 3+ seconds
        if _is_stale(_streams[url]):
            img = _draw_no_signal(img)
        photo = ImageTk.PhotoImage(img)
        label.config(image=photo, text="")
        label.image = photo
    except Exception:
        pass


def _display_multi(root, label, urls, n, config):
    """Display multiple cameras in a grid composite image.

    Grid sizing: sqrt(n) columns gives a roughly square grid.
    1 cam = full, 2 = 2x1, 3-4 = 2x2, 5-6 = 3x2, 7-9 = 3x3.
    """
    cols = math.ceil(math.sqrt(n))
    rows = math.ceil(n / cols)
    w = root.winfo_width() - 120
    h = root.winfo_height()
    if w <= 50 or h <= 50:
        return
    cell_w = w // cols
    cell_h = h // rows
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
                    img = _draw_no_signal(img)
                r = i // cols
                c = i % cols
                composite.paste(img, (c * cell_w, r * cell_h))
            except Exception:
                pass
    # Only update display if at least one frame exists — avoids black flash
    # during initial stream connection
    if has_frame:
        photo = ImageTk.PhotoImage(composite)
        label.config(image=photo, text="")
        label.image = photo
