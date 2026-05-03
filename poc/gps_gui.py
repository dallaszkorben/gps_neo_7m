#!/usr/bin/env python3
"""
GPS GUI — Proof of Concept.
Same display as main project's COORDS view.
"""

import sys
import atexit
import time
import tkinter as tk
sys.path.insert(0, "/home/pi/Projects/seeboard")
from gps_core import open_serial, read_gps, close

while not open_serial():
    time.sleep(3)

root = tk.Tk()
root.title("GPS POC")
root.configure(bg='black')
root.update_idletasks()
root.attributes('-fullscreen', True)
root.update()
root.bind('<Escape>', lambda e: on_close())

_sh = root.winfo_screenheight()
FONT_COORD = ("Helvetica", _sh // 7, "bold")
FONT_INFO = ("Helvetica", _sh // 20)
FONT_STATUS = ("Helvetica", _sh // 27)

lat_var = tk.StringVar(value="---.------")
lon_var = tk.StringVar(value="---.------")
time_var = tk.StringVar(value="Time: --:--:--")
qual_var = tk.StringVar(value="Quality: -")
sat_var = tk.StringVar(value="Satellites: - used / - visible")
status_var = tk.StringVar(value="")

tk.Label(root, textvariable=lat_var, font=FONT_COORD,
         fg='lime', bg='black').pack(pady=(40, 5))
tk.Label(root, textvariable=lon_var, font=FONT_COORD,
         fg='lime', bg='black').pack(pady=5)
tk.Label(root, textvariable=time_var, font=FONT_INFO,
         fg='white', bg='black').pack(pady=10)
tk.Label(root, textvariable=qual_var, font=FONT_INFO,
         fg='white', bg='black').pack(pady=5)
tk.Label(root, textvariable=sat_var, font=FONT_INFO,
         fg='white', bg='black').pack(pady=5)
tk.Label(root, textvariable=status_var, font=FONT_STATUS,
         fg='red', bg='black').pack(pady=20)

empty_reads = 0

def update():
    global empty_reads
    data = read_gps()

    if data is None:
        root.after(100, update)
        return

    if data['status'] == 'error':
        status_var.set(f"⚠ {data['message']} — reconnecting...")
        root.after(2000, update)
        return

    if data['status'] == 'no_data':
        empty_reads += 1
        if empty_reads >= 10:
            status_var.set("⚠ No GPS data — check wiring!")
            empty_reads = 0
        root.after(100, update)
        return

    empty_reads = 0
    status_var.set("")

    if data['status'] == 'fix':
        lat_var.set(f"{data['lat']} {data['lat_dir']}")
        lon_var.set(f"{data['lon']} {data['lon_dir']}")
        time_var.set(f"Time: {data['time']}")
        qual_var.set(f"Quality: {data['quality']}")
        sat_var.set(f"Satellites: {data['sats_used']} used / {data['sats_visible']} visible")
    else:
        lat_var.set("---.------")
        status_var.set("Waiting for fix...")
        qual_var.set("Quality: No fix")
        time_var.set(f"Time: {data['time']}")
        sat_var.set(f"Satellites: {data['sats_used']} used / {data['sats_visible']} visible")

    root.after(1000, update)

def on_close():
    close()
    root.destroy()

atexit.register(close)
root.protocol("WM_DELETE_WINDOW", on_close)
root.after(1000, update)
root.mainloop()
