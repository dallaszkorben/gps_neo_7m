#!/usr/bin/env python3
"""
Nautical GPS — main application.

Split-screen layout:
  Left:  Content area (COORDS / MAP / CAM views, switched by buttons)
  Right: Button panel

Buttons cycle through views:
  COORDS — big bold GPS coordinates (default)
  MAP    — OpenStreetMap with GPS position marker
  CAM    — live camera feed from ESP32-CAM
"""

import tkinter as tk
import atexit
import tkintermapview
import os
import threading
import time
import io


from PIL import Image, ImageTk
from gps_core import open_serial, read_gps, close
atexit.register(close)

while not open_serial():
    import time; time.sleep(3)

# ─── Main window ───
root = tk.Tk()
root.title("Nautical GPS")
root.configure(bg='black')
root.update_idletasks()
root.attributes('-fullscreen', True)
root.update()
root.bind('<Escape>', lambda e: on_close())

# Calculate font sizes relative to screen height
_sh = root.winfo_screenheight()
FONT_COORD = ("Helvetica", _sh // 7, "bold")
FONT_INFO = ("Helvetica", _sh // 20)
FONT_STATUS = ("Helvetica", _sh // 27)
FONT_BTN = ("Helvetica", _sh // 34, "bold")

# ─── Right panel: buttons ───
btn_panel = tk.Frame(root, bg='#222222', width=120)
btn_panel.pack(side='right', fill='y')
btn_panel.pack_propagate(False)

# Track which view is active: 'coords', 'map', or 'cam'
view_mode = 'coords'


def show_view(mode):
    """Switch to the specified view. Hides all others."""
    global view_mode, cam_streams, cam_known
    coords_frame.pack_forget()
    map_frame.pack_forget()
    cam_frame.pack_forget()

    # Always stop camera streams when switching views or re-entering CAM
    if cam_streams:
        for s in cam_streams.values():
            s["running"] = False
        cam_streams = {}
        cam_known = {}

    if mode == 'coords':
        coords_frame.pack(fill='both', expand=True)
    elif mode == 'map':
        map_frame.pack(fill='both', expand=True)
    elif mode == 'cam':
        reset_cam_discovery()  # Clear cache, restart discovery fresh
        cam_frame.pack(fill='both', expand=True)
        root.after(2000, rebuild_cam_grid)  # Wait for fresh discovery, then rebuild

    view_mode = mode
    for btn, m in [(coords_btn, 'coords'), (map_btn, 'map'), (cam_btn, 'cam')]:
            if mode == m:
                btn.config(fg='lime', bg='#666666', activeforeground='lime', activebackground='#777777')
            else:
                btn.config(fg='white', bg='#444444', activeforeground='white', activebackground='#555555')


# View buttons — each switches to its view
coords_btn = tk.Button(btn_panel, text="COORDS", font=FONT_BTN,
                       bg="#666666", fg='lime', activebackground='#666666',
                       command=lambda: show_view('coords'))
coords_btn.pack(fill='x', padx=5, pady=(20, 5), ipady=12)

map_btn = tk.Button(btn_panel, text="MAP", font=FONT_BTN,
                    bg='#444444', fg='white', activebackground='#666666',
                    command=lambda: show_view('map'))
map_btn.pack(fill='x', padx=5, pady=5, ipady=12)

cam_btn = tk.Button(btn_panel, text="CAM", font=FONT_BTN,
                    bg='#444444', fg='white', activebackground='#666666',
                    command=lambda: show_view('cam'))
cam_btn.pack(fill='x', padx=5, pady=5, ipady=12)

# TODO: SAVE button
tk.Button(btn_panel, text="SAVE", font=FONT_BTN,
          bg='#444444', fg='gray', state='disabled'
          ).pack(fill='x', padx=5, pady=5, ipady=12)

# TODO: REC/STOP button
tk.Button(btn_panel, text="REC", font=FONT_BTN,
          bg='#444444', fg='gray', state='disabled'
          ).pack(fill='x', padx=5, pady=5, ipady=12)

# ─── Left panel: content area ───
content = tk.Frame(root, bg='black')
content.pack(side='left', fill='both', expand=True)

# ─── COORDS view ───
coords_frame = tk.Frame(content, bg='black')

lat_var = tk.StringVar(value="---.------")
lon_var = tk.StringVar(value="---.------")
time_var = tk.StringVar(value="Time: --:--:--")
qual_var = tk.StringVar(value="Quality: -")
sat_var = tk.StringVar(value="Satellites: - used / - visible")
status_var = tk.StringVar(value="")

tk.Label(coords_frame, textvariable=lat_var, font=FONT_COORD,
         fg='lime', bg='black').pack(pady=(40, 5))
tk.Label(coords_frame, textvariable=lon_var, font=FONT_COORD,
         fg='lime', bg='black').pack(pady=5)
tk.Label(coords_frame, textvariable=time_var, font=FONT_INFO,
         fg='white', bg='black').pack(pady=10)
tk.Label(coords_frame, textvariable=qual_var, font=FONT_INFO,
         fg='white', bg='black').pack(pady=5)
tk.Label(coords_frame, textvariable=sat_var, font=FONT_INFO,
         fg='white', bg='black').pack(pady=5)
tk.Label(coords_frame, textvariable=status_var, font=FONT_STATUS,
         fg='red', bg='black').pack(pady=20)

coords_frame.pack(fill='both', expand=True)

# ─── MAP view ───
map_frame = tk.Frame(content, bg='black')

map_widget = tkintermapview.TkinterMapView(map_frame, corner_radius=0)
map_widget.pack(fill='both', expand=True)
map_widget.set_tile_server("https://a.tile.openstreetmap.org/{z}/{x}/{y}.png", max_zoom=17)

offline_db = "/home/pi/Projects/gps_neo_7m/nautical_gps/maps/tiles/osm_tiles.db"
if os.path.exists(offline_db):
    map_widget.database_path = offline_db

map_widget.set_position(56.1612, 15.5869)
map_widget.set_zoom(13)
marker = map_widget.set_marker(56.1612, 15.5869, text="GPS")

# ─── CAM view ───
cam_frame = tk.Frame(content, bg='black')
cam_label = tk.Label(cam_frame, text="Searching for cameras...", font=FONT_STATUS, fg="white", bg="black")
cam_label.pack(fill="both", expand=True)
running = True

# Camera streaming (uses discovery)
from cam_discovery import start as start_cam_discovery, get_cameras, reset as reset_cam_discovery
import urllib.request as cam_urllib
# Discovery starts when CAM view is selected

cam_streams = {}  # {url: {thread, frame, lock}}
cam_known = {}

def _cam_reader(url, state):
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
                    e = buf.find(b"\xff\xd9", s+2) if s != -1 else -1
                    if s != -1 and e != -1:
                        state["frame"] = buf[s:e+2]
                        buf = buf[e+2:]
                    else:
                        break
        except Exception:
            pass
        import time as _t; _t.sleep(1)








def rebuild_cam_grid():
    """Stop old streams, discover cameras, start new streams."""
    global cam_known, cam_streams
    # Stop old streams
    for s in cam_streams.values():
        s["running"] = False
    cam_streams = {}
    cam_known = {}
    # Get current cameras
    
    cameras = get_cameras()
    cam_known = cameras
    # Start new streams
    for name, url in cameras.items():
        state = {"running": True, "frame": None}
        t = threading.Thread(target=_cam_reader, args=(url, state), daemon=True)
        t.start()
        cam_streams[url] = state

def update_cam():
    """Update camera display with auto-discovery grid."""
    global cam_known, cam_streams
    if view_mode == "cam":
        # Auto-rebuild if NEW cameras appeared (more than we had)
        cameras = get_cameras()
        if len(cameras) > len(cam_known):
            rebuild_cam_grid()

        # Display frames
        urls = list(cam_streams.keys())
        n = len(urls)
        if n == 0:
            cam_label.config(text="Searching for cameras...", image="")
            cam_label.image = None
        elif n == 1:
            f = cam_streams[urls[0]]["frame"]
            if f:
                cam_streams[urls[0]]["frame"] = None
                try:
                    img = Image.open(io.BytesIO(f))
                    w = root.winfo_width() - 120
                    h = root.winfo_height()
                    if w > 50 and h > 50:
                        # Maintain aspect ratio
                        iw, ih = img.size
                        scale = min(w / iw, h / ih)
                        img = img.resize((int(iw * scale), int(ih * scale)), Image.LANCZOS)
                    photo = ImageTk.PhotoImage(img)
                    cam_label.config(image=photo, text="")
                    cam_label.image = photo
                except Exception:
                    pass
        else:
            # Multi-camera: composite into one image
            import math
            cols = math.ceil(math.sqrt(n))
            rows = math.ceil(n / cols)
            w = root.winfo_width() - 120
            h = root.winfo_height()
            if w > 50 and h > 50:
                cell_w = w // cols
                cell_h = h // rows
                composite = Image.new("RGB", (w, h), "black")
                for i, url in enumerate(urls):
                    f = cam_streams[url]["frame"]
                    if f:
                        cam_streams[url]["frame"] = None
                        try:
                            img = Image.open(io.BytesIO(f))
                            iw, ih = img.size
                            scale = min(cell_w / iw, cell_h / ih)
                            img = img.resize((int(iw * scale), int(ih * scale)), Image.LANCZOS)
                            r = i // cols
                            c = i % cols
                            composite.paste(img, (c * cell_w, r * cell_h))
                        except Exception:
                            pass
                photo = ImageTk.PhotoImage(composite)
                cam_label.config(image=photo, text="")
                cam_label.image = photo

    if running:
        root.after(50, update_cam)


# ─── GPS update loop ───
empty_reads = 0
last_lat = None
last_lon = None


def update_gps():
    """Read GPS and update coords + map views."""
    global empty_reads, last_lat, last_lon

    data = read_gps()

    if data is None:
        root.after(100, update_gps)
        return

    if data["status"] == "error":
        status_var.set(f"⚠ {data['message']} — reconnecting...")
        root.after(2000, update_gps)
        return

    if data['status'] == 'no_data':
        empty_reads += 1
        if empty_reads >= 10:
            status_var.set("⚠ No GPS data — check wiring!")
            empty_reads = 0
        root.after(100, update_gps)
        return

    empty_reads = 0
    status_var.set("")

    if data['status'] == 'fix':
        lat_var.set(f"{data['lat']} {data['lat_dir']}")
        lon_var.set(f"{data['lon']} {data['lon_dir']}")
        time_var.set(f"Time: {data['time']}")
        qual_var.set(f"Quality: {data['quality']}")
        sat_var.set(f"Satellites: {data['sats_used']} used / {data['sats_visible']} visible")

        lat = float(data['lat'])
        lon = float(data['lon'])
        if lat != last_lat or lon != last_lon:
            marker.set_position(lat, lon)
            if view_mode == 'map':
                map_widget.set_position(lat, lon)
            last_lat = lat
            last_lon = lon
    else:
        lat_var.set("---.------")
        lon_var.set("---.------")
        status_var.set("Waiting for fix...")
        qual_var.set("Quality: No fix")
        time_var.set(f"Time: {data['time']}")
        sat_var.set(f"Satellites: {data['sats_used']} used / {data['sats_visible']} visible")

    root.after(1000, update_gps)


def on_close():
    global running
    running = False
    for s in cam_streams.values():
        s["running"] = False
    root.destroy()


root.protocol("WM_DELETE_WINDOW", on_close)

# Start update loops
root.after(1000, update_gps)
root.after(100, update_cam)
root.mainloop()
close()
