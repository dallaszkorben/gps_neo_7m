# NEO-7M GPS GUI on Raspberry Pi (7" Touchscreen)

## Overview
GPS module NEO-7M connected to Raspberry Pi with a 7-inch touchscreen, displaying position data in a fullscreen GUI using tkinter.

## Hardware Wiring

| NEO-7M | → | RPi Pin | GPIO          |
|--------|---|---------|---------------|
| VCC    | → | Pin 1   | 3.3V          |
| GND    | → | Pin 6   | GND           |
| TX     | → | Pin 10  | GPIO 15 (RXD) |
| RX     | → | Pin 8   | GPIO 14 (TXD) |

**Important**: TX↔RX are crossed — GPS TX connects to Pi RX and vice versa.

## Raspberry Pi Setup

### 1. Enable serial port

```bash
sudo raspi-config
```

Navigate to: **Interface Options → Serial Port**
- "Login shell over serial?" → **No**
- "Serial port hardware enabled?" → **Yes**

Reboot after changing.

### 2. Verify GPS is sending data

```bash
cat /dev/serial0
```

You should see NMEA sentences (`$GPGGA`, `$GPRMC`, etc.).

## Project Structure on Raspberry Pi

```
~/Projects/gps_project/
├── venv/          # Python virtual environment
├── mygps.py      # Console version
└── gps_gui.py    # GUI version (this file)
```

## Python Environment Setup

```bash
# Create virtual environment (one time)
python3 -m venv ~/Projects/gps_project/venv

# Activate it
source ~/Projects/gps_project/venv/bin/activate

# Install dependencies
pip install pyserial pynmea2
```

**Note**: `tkinter` comes pre-installed with Raspberry Pi OS — no pip install needed. If missing:
```bash
sudo apt install python3-tk
```

## Running the GUI

```bash
source ~/Projects/gps_project/venv/bin/activate
python3 ~/Projects/gps_project/gps_gui.py
```

- Opens **fullscreen** on the 7" touchscreen
- Press **Escape** to exit

## The Script (gps_gui.py)

```python
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
```

## GUI Layout

- **Black background** — easy on the eyes, good contrast on small screen
- **Latitude & Longitude** — large bold green text (48pt), the main focus
- **Time, Quality, Satellites** — smaller white text (24pt) below
- **Fullscreen** — uses the entire 7" display
- **Escape key** — exits the application

## GPS Quality Values

| Value | Name     | Meaning                                         |
|-------|----------|-------------------------------------------------|
| 0     | Invalid  | No fix — not enough satellites                  |
| 1     | GPS fix  | Standard positioning, ~2.5–5m accuracy          |
| 2     | DGPS fix | Differential GPS with ground corrections, ~1–2m |
| 3     | PPS fix  | Precise Positioning Service, sub-meter          |

## Troubleshooting

- **No output from `cat /dev/serial0`**: Check wiring (TX↔RX crossed), verify serial enabled in raspi-config
- **Garbled text**: Baud rate mismatch — NEO-7M defaults to 9600
- **Always 0 satellites**: Move antenna outdoors or near window
- **Serial port busy**: Check with `sudo lsof /dev/serial0`
- **tkinter not found**: `sudo apt install python3-tk`
- **GUI doesn't appear**: Make sure you're running on the Pi desktop, not over SSH (or use `export DISPLAY=:0` before running)
pGJEWuDolEUtU7v2VV6YAYIQhoTfAT2lAg4D