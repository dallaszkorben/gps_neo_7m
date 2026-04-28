# NEO-7M GPS Project on Raspberry Pi

## Overview
GPS module NEO-7M connected to Raspberry Pi, reading position data via serial UART.

## Hardware Wiring

| NEO-7M | → | RPi Pin | GPIO          |
|--------|---|---------|---------------|
| VCC    | → | Pin 1   | 3.3V          |
| GND    | → | Pin 6   | GND           |
| TX     | → | Pin 10  | GPIO 15 (RXD) |
| RX     | → | Pin 8   | GPIO 14 (TXD) |

**Important**: TX↔RX are crossed — GPS TX connects to Pi RX and vice versa.

### Raspberry Pi GPIO Pinout (relevant pins)

```
         3.3V  1 | o   o | 2   5V
               3 | o   o | 4   5V
               5 | o   o | 6   GND        ← GPS GND
               7 | o   o | 8   GPIO 14    ← GPS RX
          GND  9 | o   o | 10  GPIO 15    ← GPS TX
              11 | o   o | 12
              ...
```

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

You should see NMEA sentences (`$GPGGA`, `$GPRMC`, etc.). If nothing appears, check wiring.

## Project Structure on Raspberry Pi

```
~/Projects/gps_project/
├── venv/          # Python virtual environment
└── mygps.py      # GPS reading script
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

**Note**: On Raspberry Pi OS Bookworm+, `pip install` only works inside a virtual environment. The system Python is "externally managed" and blocks direct pip installs.

## Running the Script

```bash
source ~/Projects/gps_project/venv/bin/activate
python3 ~/Projects/gps_project/mygps.py
```

## The Script (mygps.py)

```python
#!/usr/bin/env python3
import serial
import pynmea2

try:
    ser = serial.Serial('/dev/serial0', baudrate=9600, timeout=1)
except serial.SerialException as e:
    raise SystemExit(f"Error: Cannot open serial port: {e}\n"
                     "Check if another process is using it: sudo lsof /dev/serial0")

while True:
    try:
        line = ser.readline().decode('ascii', errors='replace').strip()
        if line.startswith('$GPGGA') or line.startswith('$GNGGA'):
            try:
                msg = pynmea2.parse(line)
                print(f"Time:       {msg.timestamp}")
                print(f"Latitude:   {msg.latitude:.6f} {msg.lat_dir}")
                print(f"Longitude:  {msg.longitude:.6f} {msg.lon_dir}")
                print(f"Quality:    {msg.gps_qual} ({['Invalid','GPS fix','DGPS fix','PPS fix'][min(msg.gps_qual,3)]})")
                print(f"Satellites: {msg.num_sats}")
                print("-" * 40)
            except pynmea2.ParseError:
                pass
    except KeyboardInterrupt:
        print("\nExiting.")
        ser.close()
        break
```

## Output Fields Explained

| Field      | Description                      |
|------------|----------------------------------|
| Time       | UTC time from GPS satellites     |
| Latitude   | Position N/S in degrees          |
| Longitude  | Position E/W in degrees          |
| Quality    | Fix quality (see below)          |
| Satellites | Number of satellites used in fix |

### GPS Quality Values

| Value | Name     | Meaning                                         |
|-------|----------|-------------------------------------------------|
| 0     | Invalid  | No fix — not enough satellites                  |
| 1     | GPS fix  | Standard positioning, ~2.5–5m accuracy          |
| 2     | DGPS fix | Differential GPS with ground corrections, ~1–2m |
| 3     | PPS fix  | Precise Positioning Service, sub-meter          |

NEO-7M will typically show 0 (searching) or 1 (normal fix).

## Troubleshooting

- **No output from `cat /dev/serial0`**: Check wiring (TX↔RX crossed), verify serial enabled in raspi-config
- **Garbled text**: Baud rate mismatch — NEO-7M defaults to 9600. Check with `stty -F /dev/serial0`
- **Always 0 satellites**: Move antenna outdoors or near window — needs sky visibility
- **pip install fails with "externally managed"**: You're not inside the venv. Run `source ~/Projects/gps_project/venv/bin/activate` first, verify with `which pip`
- **Cold start**: First fix can take 1–5 minutes outdoors
