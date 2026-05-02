#!/usr/bin/env python3
"""
GPS GUI — Proof of Concept.
Simple fullscreen display of GPS coordinates using gps_core.
Shows same output as main project's COORDS view.
"""

import sys
import atexit
import tkinter as tk
sys.path.insert(0, "/home/pi/Projects/gps_neo_7m/nautical_gps")
from gps_core import open_serial, read_gps, close
atexit.register(close)

# Connect to GPS (retries until successful)
import time
while not open_serial():
    time.sleep(3)

# --- GUI ---
root = tk.Tk()
root.title("GPS POC")
root.configure(bg='black')
root.attributes('-fullscreen', True)
root.bind('<Escape>', lambda e: on_close())

lat_var = tk.StringVar(value="---.------")
lon_var = tk.StringVar(value="---.------")
info_var = tk.StringVar(value="Waiting for GPS...")

tk.Label(root, textvariable=lat_var, font=("Helvetica", 48, "bold"),
         fg='lime', bg='black').pack(pady=(80, 5))
tk.Label(root, textvariable=lon_var, font=("Helvetica", 48, "bold"),
         fg='lime', bg='black').pack(pady=5)
tk.Label(root, textvariable=info_var, font=("Helvetica", 24),
         fg='white', bg='black').pack(pady=30)


def update():
    data = read_gps()

    if data is None:
        root.after(100, update)
        return

    if data['status'] == 'error':
        info_var.set(f"⚠ {data['message']} — reconnecting...")
        root.after(2000, update)
        return

    if data['status'] == 'no_data':
        root.after(100, update)
        return

    if data['status'] == 'fix':
        lat_var.set(f"{data['lat']} {data['lat_dir']}")
        lon_var.set(f"{data['lon']} {data['lon_dir']}")
        info_var.set(f"Time: {data['time']}  |  Sats: {data['sats_used']} used / {data['sats_visible']} visible  |  {data['quality']}")
    else:
        lat_var.set("Waiting for fix...")
        lon_var.set("")
        info_var.set(f"Satellites: {data['sats_used']} used / {data['sats_visible']} visible")

    root.after(1000, update)


def on_close():
    close()  # Restore serial port settings so cat works after
    root.destroy()


root.protocol("WM_DELETE_WINDOW", on_close)
root.after(1000, update)
root.mainloop()
