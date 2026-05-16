# seeBoard

Nautical GPS + multi-camera system for Raspberry Pi with touchscreen.

## What it does

- Displays GPS coordinates (DMS format) from a NEO-7M module
- Shows position on an offline OpenStreetMap (no internet needed at sea)
- Streams live video from multiple ESP32-CAM cameras with auto-discovery
- Touchscreen-friendly UI with configurable settings

## Hardware

| Component             | Role                               |
|-----------------------|------------------------------------|
| Raspberry Pi 3        | Main computer, WiFi access point   |
| 5" touchscreen        | Display + input                    |
| NEO-7M GPS            | Position via serial UART           |
| ESP32-WROVER-CAM (×N) | Wireless cameras (MJPEG over WiFi) |

## Architecture

```
Raspberry Pi (WiFi AP: GREEN-BEAN)
├── GPS via /dev/serial0 (UART)
├── seeBoard app (tkinter fullscreen)
└── WiFi clients:
    ├── ESP32-CAM #1 (esp32-cam-a1b2.local)
    ├── ESP32-CAM #2 (esp32-cam-c3d4.local)
    └── ...
```

Cameras connect to the Pi's hotspot and advertise themselves via mDNS (`_mjpeg._tcp`). The app discovers them automatically — no configuration needed.

## Views

| Button | View                                                 |
|--------|------------------------------------------------------|
| COORDS | GPS coordinates, time, quality, satellite count      |
| MAP    | Offline OpenStreetMap with position marker           |
| CAM    | Live camera grid (auto-layout based on camera count) |
| CONF   | Settings (DMS decimals, camera rotation)             |

## Setup

### Raspberry Pi

```bash
# Clone
git clone https://github.com/dallaszkorben/seeboard.git
cd seeboard

# Virtual environment
python3 -m venv venv
source venv/bin/activate
pip install pyserial pynmea2 tkintermapview pillow zeroconf

# Enable UART (one time)
sudo raspi-config  # Interface Options → Serial Port → Login shell: No, Hardware: Yes
# Add to /boot/firmware/config.txt:
#   enable_uart=1
#   dtoverlay=miniuart-bt

# Run
./seeboard.sh
```

### ESP32-CAM Firmware

The firmware source lives in `firmware/esp32-cam/`. All cameras use the same firmware — each gets a unique mDNS hostname from its MAC address.

```bash
cd firmware/esp32-cam
pio run -t upload    # connect each ESP32 via USB one at a time
```

See `docs/esp32-cam.md` for detailed firmware documentation.

## Project Structure

```
seeboard/
├── seeboard.sh           ← Launcher (activates hotspot + runs app)
├── see_board.cfg         ← Persistent config
├── README.md
├── requirements.txt
│
├── app/                  ← Pi application (Python)
│   ├── seeboard.py       ← Entry point
│   ├── gps_core.py       ← GPS serial/NMEA logic
│   ├── cam_discovery.py  ← mDNS camera auto-discovery
│   ├── views/
│   │   ├── coords_view.py
│   │   ├── map_view.py
│   │   ├── cam_view.py
│   │   └── conf_view.py
│   └── maps/tiles/       ← Offline OSM tiles (not in repo)
│
├── firmware/             ← ESP32 camera firmware (C++/PlatformIO)
│   └── esp32-cam/
│       ├── platformio.ini
│       └── src/main.cpp
│
├── poc/                  ← Proof-of-concept scripts
│   ├── gps_console.py
│   ├── gps_gui.py
│   └── camera.py
│
├── tools/                ← Utilities
│   └── download_tiles.py
│
├── docs/                 ← Documentation
│   ├── seeboard.md
│   ├── esp32-cam.md
│   └── ...
│
└── icons/                ← Desktop icon
    └── seeBoard.png
```

## Configuration

Settings in `see_board.cfg`:

```ini
[gps]
show_dms_decimals = False

[cam]
rotation = 0
```

## GPS Wiring (NEO-7M → Raspberry Pi)

| NEO-7M | RPi Pin | Function      |
|--------|---------|---------------|
| VCC    | Pin 1   | 3.3V          |
| GND    | Pin 6   | GND           |
| TX     | Pin 10  | GPIO 15 (RXD) |
| RX     | Pin 8   | GPIO 14 (TXD) |

## License

MIT
