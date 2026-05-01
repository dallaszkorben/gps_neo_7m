#!/usr/bin/env python3
import tkinter as tk
import serial
import pynmea2
import random

DEMO_MODE = False

# --- Open the GPS serial port ---
# NEO-7M sends NMEA data at 9600 baud on /dev/serial0
# If the port doesn't exist (e.g. running on desktop), switch to demo mode
try:
    ser = serial.Serial('/dev/serial0', baudrate=9600, timeout=0.5)
except (serial.SerialException, OSError):
    print("Serial port not available — running in DEMO mode")
    ser = None
    DEMO_MODE = True

# --- Create the GUI window ---
root = tk.Tk()
root.title("GPS")
root.configure(bg='black')
root.attributes('-fullscreen', True)       # Fill the entire screen (7" touchscreen)
root.bind('<Escape>', lambda e: root.destroy())  # Press Escape to quit

# --- Variables that hold the displayed text ---
# StringVar is a tkinter mechanism: when you call .set() on it,
# any Label linked to it updates automatically on screen
lat_var = tk.StringVar(value="---.------")
lon_var = tk.StringVar(value="---.------")
time_var = tk.StringVar(value="Time: --:--:--")
qual_var = tk.StringVar(value="Quality: -")
sat_var = tk.StringVar(value="Satellites: -")

# --- Layout: labels stacked vertically ---
# Lat/Lon: big bold green text (the main info)
tk.Label(root, textvariable=lat_var, font=("Helvetica", 48, "bold"),
         fg='lime', bg='black').pack(pady=(40, 5))
tk.Label(root, textvariable=lon_var, font=("Helvetica", 48, "bold"),
         fg='lime', bg='black').pack(pady=5)
# Time, quality, satellites: smaller white text
tk.Label(root, textvariable=time_var, font=("Helvetica", 24),
         fg='white', bg='black').pack(pady=10)
tk.Label(root, textvariable=qual_var, font=("Helvetica", 24),
         fg='white', bg='black').pack(pady=5)
tk.Label(root, textvariable=sat_var, font=("Helvetica", 24),
         fg='white', bg='black').pack(pady=5)


def update():
    """Read one line from GPS and update the display.

    This function is called repeatedly by root.after() — tkinter's way of
    scheduling a function to run after a delay (in milliseconds) without
    blocking the GUI. It's like a timer that fires every 1000ms.
    We can't use a while-loop here because that would freeze the window.
    """
    if DEMO_MODE:
        # Simulate GPS data with slight random movement (for desktop testing)
        lat = 47.497913 + random.uniform(-0.0001, 0.0001)
        lon = 19.040236 + random.uniform(-0.0001, 0.0001)
        lat_var.set(f"{lat:.6f} N")
        lon_var.set(f"{lon:.6f} E")
        time_var.set("Time: 12:34:56")
        qual_var.set("Quality: GPS fix")
        sat_var.set("Satellites: 8")
    else:
        # Read one NMEA sentence from the GPS module
        line = ser.readline().decode('ascii', errors='replace').strip()
        # We only care about GGA sentences — they contain position + satellite info
        # $GPGGA = GPS only, $GNGGA = multi-constellation (GPS+GLONASS)
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

    # Schedule this function to run again in 1000ms (1 second)
    # This is how tkinter does repeated updates without freezing the GUI
    root.after(1000, update)


# Start the first update after 1 second
root.after(1000, update)

# Run the GUI event loop (blocks here until window is closed)
root.mainloop()

# Clean up serial port when done
if ser:
    ser.close()
