#!/usr/bin/env python3
"""
seeBoard — Nautical GPS + Camera application.

Touchscreen layout with button panel on the right.
Views: COORDS, MAP, CAM, CONF — each in its own module.
"""

import tkinter as tk
import configparser
import atexit

import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from gps_core import open_serial, close
import gps_core

from views import coords_view
from views import map_view
from views import cam_view
from views import conf_view

atexit.register(close)

# Wait for GPS serial port
while not open_serial():
    import time; time.sleep(3)

# ─── Configuration ───
CONFIG_FILE = "/home/pi/Projects/seeboard/see_board.cfg"  # At project root


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
root.attributes('-fullscreen', True)
root.update()
root.bind('<Escape>', lambda e: on_close())

# Font sizes relative to screen height
_sh = root.winfo_screenheight()
fonts = {
    "FONT_COORD": ("Helvetica", _sh // 7, "bold"),
    "FONT_INFO": ("Helvetica", _sh // 20),
    "FONT_STATUS": ("Helvetica", _sh // 27),
    "FONT_BTN": ("Helvetica", _sh // 34, "bold"),
}

# ─── Right panel: buttons ───
btn_panel = tk.Frame(root, bg='#222222', width=120)
btn_panel.pack(side='right', fill='y')
btn_panel.pack_propagate(False)

# ─── Left panel: content area ───
content = tk.Frame(root, bg='black')
content.pack(side='left', fill='both', expand=True)

# ─── Create views ───
coords_frame, update_gps, coords_on_show = coords_view.create(
    content, fonts, config, CONFIG_FILE)
map_frame, map_widget, marker = map_view.create(content)
cam_frame, cam_label = cam_view.create(content, fonts)
conf_frame = conf_view.create(content, fonts, config, save_config, CONFIG_FILE)

# Show COORDS by default
coords_frame.pack(fill='both', expand=True)

# ─── View switching ───
view_mode = 'coords'
running = [True]


def get_view_mode():
    return view_mode


def show_view(mode):
    """Switch to the specified view."""
    global view_mode
    coords_frame.pack_forget()
    map_frame.pack_forget()
    cam_frame.pack_forget()
    conf_frame.pack_forget()

    # Stop camera streams when leaving CAM
    cam_view.stop_all()

    if mode == 'coords':
        coords_on_show()
        coords_frame.pack(fill='both', expand=True)
    elif mode == 'map':
        map_frame.pack(fill='both', expand=True)
    elif mode == 'conf':
        conf_frame.pack(fill='both', expand=True)
    elif mode == 'cam':
        cam_view.on_show(root)
        cam_frame.pack(fill='both', expand=True)

    view_mode = mode
    # Highlight active button
    for btn, m in [(coords_btn, 'coords'), (map_btn, 'map'),
                   (cam_btn, 'cam'), (conf_btn, 'conf')]:
        if mode == m:
            btn.config(fg='lime', bg='#666666',
                       activeforeground='lime', activebackground='#777777')
        else:
            btn.config(fg='white', bg='#444444',
                       activeforeground='white', activebackground='#555555')


# ─── Buttons ───
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

# TODO: SAVE button
tk.Button(btn_panel, text="SAVE", font=fonts["FONT_BTN"],
          bg='#444444', fg='gray', state='disabled'
          ).pack(fill='x', padx=5, pady=5, ipady=12)

# TODO: REC/STOP button
tk.Button(btn_panel, text="REC", font=fonts["FONT_BTN"],
          bg='#444444', fg='gray', state='disabled'
          ).pack(fill='x', padx=5, pady=5, ipady=12)

# EXIT button at the bottom
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
root.after(1000, lambda: update_gps(root, get_view_mode, marker, map_widget))
cam_view.update_cam(root, cam_label, config, get_view_mode, running)
root.mainloop()
close()
