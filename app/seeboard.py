#!/usr/bin/env python3
"""
seeBoard — Nautical GPS + Camera application.

Touchscreen layout with button panel on the right.
Views: COORDS, MAP, CAM, CONF — each in its own module.

This file is the thin orchestrator: it creates the window, wires up
the views, and runs the main loop. All view logic lives in app/views/.
"""

import tkinter as tk
import configparser
import atexit

# Add app/ directory to Python path so that views/ and gps_core are importable
# without requiring package installation. This lets us run directly with
# "python app/seeboard.py" from the project root.
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from gps_core import open_serial, close
import gps_core

from views import coords_view
from views import map_view
from views import cam_view
from views import conf_view

# Ensure serial port is always restored on exit, even on crash.
# Without this, the port can be left in a bad state and `cat /dev/serial0`
# would stop working until a manual `stty sane`.
atexit.register(close)

# Block until GPS serial port is available. The NEO-7M may take a few
# seconds after power-on before the port is ready.
while not open_serial():
    import time; time.sleep(3)

# ─── Configuration ───
# Config file lives at project root (not inside app/) so it's easy to find
# and edit manually if needed. Absolute path avoids issues with working directory.
CONFIG_FILE = "/home/pi/Projects/seeboard/see_board.cfg"


def load_config():
    cfg = configparser.ConfigParser()
    cfg.read(CONFIG_FILE)
    if not cfg.has_section("gps"):
        cfg.add_section("gps")
    return cfg


def save_config(cfg):
    with open(CONFIG_FILE, "w") as f:
        cfg.write(f)


config = load_config()
gps_core.SHOW_DMS_DECIMALS = config.getboolean("gps", "show_dms_decimals", fallback=False)

# ─── Main window ───
root = tk.Tk()
root.title("seeBoard")
root.configure(bg='black')
root.update_idletasks()
# Fullscreen for touchscreen kiosk use — no window decorations or taskbar
root.attributes('-fullscreen', True)
root.update()
root.bind('<Escape>', lambda e: on_close())

# Font sizes are relative to screen height so the UI scales correctly
# on different displays (5" vs 7" touchscreen) without hardcoded pixel values.
_sh = root.winfo_screenheight()
fonts = {
    "FONT_COORD": ("Helvetica", _sh // 7, "bold"),
    "FONT_INFO": ("Helvetica", _sh // 20),
    "FONT_STATUS": ("Helvetica", _sh // 27),
    "FONT_BTN": ("Helvetica", _sh // 34, "bold"),
}

# ─── Right panel: buttons ───
# Fixed 120px width so the content area gets all remaining space.
# pack_propagate(False) prevents child widgets from shrinking the panel.
btn_panel = tk.Frame(root, bg='#222222', width=120)
btn_panel.pack(side='right', fill='y')
btn_panel.pack_propagate(False)

# ─── Left panel: content area ───
content = tk.Frame(root, bg='black')
content.pack(side='left', fill='both', expand=True)

# ─── Create views ───
# Each view module returns its frame + any callbacks needed by the orchestrator.
# Views are created once at startup and shown/hidden via pack/pack_forget
# (not destroyed/recreated) to preserve state and avoid flicker.
coords_frame, update_gps, coords_on_show = coords_view.create(
    content, fonts, config, CONFIG_FILE)
map_frame, map_widget, marker = map_view.create(content)
cam_frame, cam_label = cam_view.create(content, fonts)
conf_frame = conf_view.create(content, fonts, config, save_config, CONFIG_FILE)

# Show COORDS by default — most important view for navigation
coords_frame.pack(fill='both', expand=True)

# ─── View switching ───
view_mode = 'coords'
# Using a list so the closure in update_cam can see mutations
running = [True]


def get_view_mode():
    return view_mode


def show_view(mode):
    """Switch to the specified view. Hides all others."""
    global view_mode
    coords_frame.pack_forget()
    map_frame.pack_forget()
    cam_frame.pack_forget()
    conf_frame.pack_forget()

    # Always stop camera streams when leaving CAM view to free network
    # bandwidth and CPU. Streams are cheap to restart.
    cam_view.stop_all()

    if mode == 'coords':
        # Re-read config on every switch to COORDS so that settings changed
        # in CONF (like DMS decimals) take effect immediately.
        coords_on_show()
        coords_frame.pack(fill='both', expand=True)
    elif mode == 'map':
        map_frame.pack(fill='both', expand=True)
    elif mode == 'conf':
        conf_frame.pack(fill='both', expand=True)
    elif mode == 'cam':
        # Reset discovery and rebuild: ensures dead cameras are dropped
        # and newly connected cameras are found fresh.
        cam_view.on_show(root)
        cam_frame.pack(fill='both', expand=True)

    view_mode = mode
    # Highlight active button green, others white
    for btn, m in [(coords_btn, 'coords'), (map_btn, 'map'),
                   (cam_btn, 'cam'), (conf_btn, 'conf')]:
        if mode == m:
            btn.config(fg='lime', bg='#666666',
                       activeforeground='lime', activebackground='#777777')
        else:
            btn.config(fg='white', bg='#444444',
                       activeforeground='white', activebackground='#555555')


# ─── Buttons ───
# Large touch targets (ipady=12) for reliable touchscreen taps.
coords_btn = tk.Button(btn_panel, text="COORDS", font=fonts["FONT_BTN"],
                       bg="#666666", fg='lime', activebackground='#666666',
                       command=lambda: show_view('coords'))
coords_btn.pack(fill='x', padx=5, pady=(20, 5), ipady=12)

map_btn = tk.Button(btn_panel, text="MAP", font=fonts["FONT_BTN"],
                    bg='#444444', fg='white', activebackground='#666666',
                    command=lambda: show_view('map'))
map_btn.pack(fill='x', padx=5, pady=5, ipady=12)

cam_btn = tk.Button(btn_panel, text="CAM", font=fonts["FONT_BTN"],
                    bg='#444444', fg='white', activebackground='#666666',
                    command=lambda: show_view('cam'))
cam_btn.pack(fill='x', padx=5, pady=5, ipady=12)

conf_btn = tk.Button(btn_panel, text="CONF", font=fonts["FONT_BTN"],
                     bg='#444444', fg='white',
                     activeforeground='white', activebackground='#555555',
                     command=lambda: show_view('conf'))
conf_btn.pack(fill='x', padx=5, pady=5, ipady=12)

# TODO: SAVE button — will store current position as waypoint in SQLite
tk.Button(btn_panel, text="SAVE", font=fonts["FONT_BTN"],
          bg='#444444', fg='gray', state='disabled'
          ).pack(fill='x', padx=5, pady=5, ipady=12)

# TODO: REC/STOP button — will record GPS track to SQLite
tk.Button(btn_panel, text="REC", font=fonts["FONT_BTN"],
          bg='#444444', fg='gray', state='disabled'
          ).pack(fill='x', padx=5, pady=5, ipady=12)

# EXIT button at the bottom — separated from nav buttons to avoid accidental taps.
# Uses side='bottom' on a sub-frame to pin it to the panel's bottom edge.
exit_frame = tk.Frame(btn_panel, bg='#222222')
exit_frame.pack(side='bottom', fill='x')
tk.Button(exit_frame, text="EXIT", font=fonts["FONT_BTN"],
          bg='#444444', fg='red', activeforeground='red', activebackground='#555555',
          command=lambda: on_close()).pack(fill='x', padx=5, pady=(5, 20), ipady=12)


# ─── Cleanup ───
def on_close():
    running[0] = False
    cam_view.stop_all()
    root.destroy()


root.protocol("WM_DELETE_WINDOW", on_close)

# ─── Start update loops ───
# GPS updates every 1s (matches NMEA sentence rate from NEO-7M).
# Camera updates every 50ms (~20fps) for smooth video.
root.after(1000, lambda: update_gps(root, get_view_mode, marker, map_widget))
cam_view.update_cam(root, cam_label, config, get_view_mode, running)
root.mainloop()
close()
