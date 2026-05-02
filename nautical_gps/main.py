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
import socket
import urllib.request
from PIL import Image, ImageTk
from gps_core import open_serial, read_gps, close
atexit.register(close)

while not open_serial():
    import time; time.sleep(3)

# ─── Main window ───
root = tk.Tk()
root.title("Nautical GPS")
root.configure(bg='black')
root.attributes('-fullscreen', True)
root.bind('<Escape>', lambda e: on_close())

# ─── Right panel: buttons ───
btn_panel = tk.Frame(root, bg='#222222', width=120)
btn_panel.pack(side='right', fill='y')
btn_panel.pack_propagate(False)

# Track which view is active: 'coords', 'map', or 'cam'
view_mode = 'coords'


def show_view(mode):
    """Switch to the specified view. Hides all others."""
    global view_mode
    coords_frame.pack_forget()
    map_frame.pack_forget()
    cam_frame.pack_forget()

    if mode == 'coords':
        coords_frame.pack(fill='both', expand=True)
    elif mode == 'map':
        map_frame.pack(fill='both', expand=True)
    elif mode == 'cam':
        cam_frame.pack(fill='both', expand=True)

    view_mode = mode
    # Highlight the active button, dim the others
    coords_btn.config(fg='lime' if mode == 'coords' else 'white')
    map_btn.config(fg='lime' if mode == 'map' else 'white')
    cam_btn.config(fg='lime' if mode == 'cam' else 'white')


# View buttons — each switches to its view
coords_btn = tk.Button(btn_panel, text="COORDS", font=("Helvetica", 14, "bold"),
                       bg='#444444', fg='lime', activebackground='#666666',
                       command=lambda: show_view('coords'))
coords_btn.pack(fill='x', padx=5, pady=(20, 5), ipady=12)

map_btn = tk.Button(btn_panel, text="MAP", font=("Helvetica", 14, "bold"),
                    bg='#444444', fg='white', activebackground='#666666',
                    command=lambda: show_view('map'))
map_btn.pack(fill='x', padx=5, pady=5, ipady=12)

cam_btn = tk.Button(btn_panel, text="CAM", font=("Helvetica", 14, "bold"),
                    bg='#444444', fg='white', activebackground='#666666',
                    command=lambda: show_view('cam'))
cam_btn.pack(fill='x', padx=5, pady=5, ipady=12)

# TODO: SAVE button
tk.Button(btn_panel, text="SAVE", font=("Helvetica", 14, "bold"),
          bg='#444444', fg='gray', state='disabled'
          ).pack(fill='x', padx=5, pady=5, ipady=12)

# TODO: REC/STOP button
tk.Button(btn_panel, text="REC", font=("Helvetica", 14, "bold"),
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

tk.Label(coords_frame, textvariable=lat_var, font=("Helvetica", 48, "bold"),
         fg='lime', bg='black').pack(pady=(40, 5))
tk.Label(coords_frame, textvariable=lon_var, font=("Helvetica", 48, "bold"),
         fg='lime', bg='black').pack(pady=5)
tk.Label(coords_frame, textvariable=time_var, font=("Helvetica", 24),
         fg='white', bg='black').pack(pady=10)
tk.Label(coords_frame, textvariable=qual_var, font=("Helvetica", 24),
         fg='white', bg='black').pack(pady=5)
tk.Label(coords_frame, textvariable=sat_var, font=("Helvetica", 24),
         fg='white', bg='black').pack(pady=5)
tk.Label(coords_frame, textvariable=status_var, font=("Helvetica", 18),
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
cam_label = tk.Label(cam_frame, bg='black')
cam_label.pack(fill='both', expand=True)

# Camera stream reader (background thread)
STREAM_URL = "http://esp32-cam.local:81/stream"
MAX_BUF = 200000
cam_current_frame = None
cam_frame_lock = threading.Lock()
cam_last_frame_time = 0
running = True


def cam_stream_reader():
    """Background thread: reads MJPEG stream from ESP32-CAM."""
    global cam_current_frame, running, cam_last_frame_time
    while running:
        try:
            stream = urllib.request.urlopen(STREAM_URL, timeout=5)
            stream.fp.raw._sock.settimeout(10)
            buf = b''
            while running:
                chunk = stream.read(4096)
                if not chunk:
                    break
                buf += chunk
                if len(buf) > MAX_BUF:
                    buf = buf[-MAX_BUF:]
                while True:
                    start = buf.find(b'\xff\xd8')
                    end = buf.find(b'\xff\xd9', start + 2) if start != -1 else -1
                    if start != -1 and end != -1:
                        jpg = buf[start:end + 2]
                        buf = buf[end + 2:]
                        with cam_frame_lock:
                            cam_current_frame = jpg
                            cam_last_frame_time = time.time()
                    else:
                        break
        except (urllib.error.URLError, socket.timeout, OSError):
            pass
        time.sleep(1)


# Start camera reader thread
cam_thread = threading.Thread(target=cam_stream_reader, daemon=True)
cam_thread.start()


def update_cam():
    """Update camera display (only when CAM view is active)."""
    global cam_current_frame
    if view_mode == 'cam':
        frame = None
        with cam_frame_lock:
            if cam_current_frame:
                frame = cam_current_frame
                cam_current_frame = None
        if frame:
            try:
                img = Image.open(io.BytesIO(frame)).rotate(-90, expand=True)
                w = cam_frame.winfo_width()
                h = cam_frame.winfo_height()
                if w > 1 and h > 1:
                    img = img.resize((w, h), Image.LANCZOS)
                photo = ImageTk.PhotoImage(img)
                cam_label.config(image=photo)
                cam_label.image = photo
            except Exception:
                pass
    if running:
        root.after(33, update_cam)


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
        lat_var.set("Waiting for fix...")
        lon_var.set("")
        sat_var.set(f"Satellites: {data['sats_used']} used / {data['sats_visible']} visible")

    root.after(1000, update_gps)


def on_close():
    global running
    running = False
    root.destroy()


root.protocol("WM_DELETE_WINDOW", on_close)

# Start update loops
root.after(1000, update_gps)
root.after(100, update_cam)
root.mainloop()
close()
