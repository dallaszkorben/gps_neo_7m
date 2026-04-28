#!/usr/bin/env python3
import tkinter as tk
import serial
import pynmea2

try:
    ser = serial.Serial('/dev/serial0', baudrate=9600, timeout=0.5)
except serial.SerialException as e:
    raise SystemExit(f"Error: Cannot open serial port: {e}\n"
                     "Check if another process is using it: sudo lsof /dev/serial0")

root = tk.Tk()
root.title("GPS")
root.configure(bg='black')
root.attributes('-fullscreen', True)
root.bind('<Escape>', lambda e: root.destroy())

lat_var = tk.StringVar(value="---.------")
lon_var = tk.StringVar(value="---.------")
time_var = tk.StringVar(value="Time: --:--:--")
qual_var = tk.StringVar(value="Quality: -")
sat_var = tk.StringVar(value="Satellites: -")

tk.Label(root, textvariable=lat_var, font=("Helvetica", 48, "bold"),
         fg='lime', bg='black').pack(pady=(40, 5))
tk.Label(root, textvariable=lon_var, font=("Helvetica", 48, "bold"),
         fg='lime', bg='black').pack(pady=5)
tk.Label(root, textvariable=time_var, font=("Helvetica", 24),
         fg='white', bg='black').pack(pady=10)
tk.Label(root, textvariable=qual_var, font=("Helvetica", 24),
         fg='white', bg='black').pack(pady=5)
tk.Label(root, textvariable=sat_var, font=("Helvetica", 24),
         fg='white', bg='black').pack(pady=5)


def update():
    line = ser.readline().decode('ascii', errors='replace').strip()
    if line.startswith('$GPGGA') or line.startswith('$GNGGA'):
        try:
            msg = pynmea2.parse(line)
            lat_var.set(f"{msg.latitude:.6f} {msg.lat_dir}")
            lon_var.set(f"{msg.longitude:.6f} {msg.lon_dir}")
            time_var.set(f"Time: {msg.timestamp}")
            qual_var.set(f"Quality: {['Invalid','GPS fix','DGPS fix','PPS fix'][min(msg.gps_qual,3)]}")
            sat_var.set(f"Satellites: {msg.num_sats}")
        except pynmea2.ParseError:
            pass
    root.after(100, update)


root.after(100, update)
root.mainloop()
ser.close()
