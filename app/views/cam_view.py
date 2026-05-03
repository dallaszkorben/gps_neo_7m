"""CAM view — live MJPEG streams from ESP32 cameras with auto-discovery.

Design decisions:
- Uses a single PIL composite image for multi-camera display instead of
  multiple tkinter widgets. This avoids tkinter grid sizing issues on the
  Pi's small screen and gives precise control over layout.
- Each camera stream runs in its own daemon thread. Threads are cheap and
  the MJPEG protocol is blocking (read until frame boundary), so async
  would add complexity without benefit here.
- Frames are stored as raw JPEG bytes in a shared dict. The main thread
  (update_cam) picks them up every 50ms and renders. This decouples
  network speed from display refresh rate.
"""

import tkinter as tk
import threading
import io
import math
from PIL import Image, ImageTk
from cam_discovery import start as start_cam_discovery, get_cameras, reset as reset_cam_discovery
import urllib.request as cam_urllib


# Module-level state (not instance-based) because tkinter is single-threaded
# and we only ever have one CAM view.
_streams = {}   # {url: {"running": bool, "frame": bytes|None}}
_known = {}     # {name: url} — cameras we've already started streams for


def create(parent, fonts):
    """Create the CAM view frame. Returns (frame, label).

    Uses a single Label widget for all camera display. The label's image
    is replaced every frame — simpler and faster than managing multiple
    widgets in a grid.
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
    global _streams, _known
    for s in _streams.values():
        s["running"] = False
    _streams = {}
    _known = {}


def on_show(root, rebuild_delay=2000):
    """Called when switching to CAM view — reset discovery and rebuild.

    Resets mDNS discovery cache so that only currently-alive cameras are
    shown. The 2s delay gives cameras time to respond to the new mDNS query.
    Without the delay, we'd often get 0 cameras on the first frame.
    """
    reset_cam_discovery()
    root.after(rebuild_delay, rebuild_grid)


def rebuild_grid():
    """Stop old streams, discover cameras, start new streams.

    Called on initial CAM view entry and when new cameras are detected.
    Stops everything first to ensure clean state — partially-dead streams
    from disconnected cameras are cleared.
    """
    global _known, _streams
    for s in _streams.values():
        s["running"] = False
    _streams = {}
    _known = {}

    cameras = get_cameras()
    _known = cameras

    for name, url in cameras.items():
        state = {"running": True, "frame": None}
        t = threading.Thread(target=_reader, args=(url, state), daemon=True)
        t.start()
        _streams[url] = state


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
    import time as _t
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
                    # Discard old data to prevent unbounded memory growth
                    buf = buf[-MAX_BUF:]
                # Extract all complete JPEG frames from buffer
                while True:
                    s = buf.find(b"\xff\xd8")
                    e = buf.find(b"\xff\xd9", s + 2) if s != -1 else -1
                    if s != -1 and e != -1:
                        # Store only the latest frame (overwrites previous)
                        state["frame"] = buf[s:e + 2]
                        buf = buf[e + 2:]
                    else:
                        break
        except Exception:
            pass
        # Brief pause before reconnect to avoid hammering a dead camera
        _t.sleep(1)


def update_cam(root, label, config, get_view_mode, running_flag):
    """Update camera display. Schedules itself every 50ms (~20fps).

    Only processes frames when CAM view is active to save CPU.
    Also checks for newly discovered cameras and auto-rebuilds the grid.
    """
    global _known, _streams

    if get_view_mode() == "cam":
        # Auto-rebuild if new cameras appeared since last check.
        # This handles cameras that boot after the app starts.
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
    """Read rotation from config each frame.

    Re-reads every frame (not cached) so that rotation changes in CONF
    take effect immediately without needing to restart the camera view.
    """
    return config.getint("cam", "rotation", fallback=0)


def _display_single(root, label, url, config):
    """Display a single camera fullscreen with aspect ratio preserved."""
    f = _streams[url]["frame"]
    if not f:
        return
    # Clear frame immediately so we don't re-display the same frame
    _streams[url]["frame"] = None
    try:
        img = Image.open(io.BytesIO(f))
        rot = _get_rotation(config)
        if rot:
            # Negative rotation because PIL rotates counter-clockwise
            # but users expect clockwise (90° = turn right)
            img = img.rotate(-rot, expand=True)
        # Subtract button panel width (120px) from available space
        w = root.winfo_width() - 120
        h = root.winfo_height()
        if w > 50 and h > 50:
            iw, ih = img.size
            scale = min(w / iw, h / ih)
            img = img.resize((int(iw * scale), int(ih * scale)), Image.LANCZOS)
        photo = ImageTk.PhotoImage(img)
        label.config(image=photo, text="")
        # Keep reference to prevent garbage collection
        label.image = photo
    except Exception:
        pass


def _display_multi(root, label, urls, n, config):
    """Display multiple cameras in a grid composite image.

    Uses a single composite PIL image rather than multiple tkinter widgets
    because tkinter's grid/pack managers fight over space on small screens
    and produce inconsistent cell sizes. A composite gives pixel-perfect
    control over the layout.

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
