# seeBoard — Main Project

## Overview
seeBoard application for Raspberry Pi with 7" touchscreen.
Three-view layout with GPS coordinates, map, and live camera feed.
Button panel on the right for view switching.

## Layout
```
+----------------------------------+----------+
|                                  | [COORDS] |
|   Content area                   | [MAP]    |
|   (COORDS / MAP / CAM / CONF)    | [CAM]    |
|                                  | [CONF]   |
|                                  | [REC]    |
+----------------------------------+----------+
```

Active button is highlighted green. Views:
- **COORDS** — big bold GPS coordinates (default)
- **MAP** — OpenStreetMap with GPS position marker (offline tiles for Karlskrona)
- **CAM** — live MJPEG stream from ESP32-CAM
- **CONF** — configuration settings (persistent)

## Hardware

### NEO-7M GPS Wiring

| NEO-7M | → | RPi Pin | GPIO          |
|--------|---|---------|---------------|
| VCC    | → | Pin 1   | 3.3V          |
| GND    | → | Pin 6   | GND           |
| TX     | → | Pin 10  | GPIO 15 (RXD) |
| RX     | → | Pin 8   | GPIO 14 (TXD) |

TX↔RX are crossed.

### ESP32-CAM (Freenove ESP32-WROVER-CAM)
- Connects to Pi's WiFi AP as a client
- Serves MJPEG stream on port 81
- Reachable at `esp32-cam.local` via mDNS
- Stream URL: `http://esp32-cam.local:81/stream`
- Camera image rotated -90° in software (mounted sideways)

## Network Architecture

```
Raspberry Pi (GREEN-BEAN AP)  ←WiFi→  ESP32-CAM (client)
     10.42.0.1                          10.42.0.x (esp32-cam.local)
```

- Pi runs as WiFi Access Point (SSID: GREEN-BEAN, no password)
- ESP32 connects to Pi's AP (retries forever if Pi not ready yet)
- Pi also reads GPS via serial `/dev/serial0`

### Pi WiFi AP Setup

Activate hotspot:
```bash
sudo nmcli connection up Hotspot
```

Switch back to home WiFi:
```bash
sudo nmcli connection up blabla2.4
```

The Hotspot connection was created with:
```bash
sudo nmcli connection add type wifi ifname wlan0 con-name Hotspot autoconnect no ssid GREEN-BEAN 802-11-wireless.mode ap ipv4.method shared
```

**IMPORTANT**: Pi has only one WiFi interface. When Hotspot is active, Pi loses home network access. Use Ethernet or connect your laptop to GREEN-BEAN for SSH.

### Changing AP IP Address

The Pi AP IP defaults to 10.42.0.1. To change it:

```bash
sudo nmcli connection modify Hotspot ipv4.addresses 192.168.10.1/24
sudo nmcli connection down Hotspot && sudo nmcli connection up Hotspot
```

DHCP range adjusts automatically to match the subnet.

### Checking Connected Clients

```bash
iw dev wlan0 station dump | grep Station
arp -a
```

### Finding ESP32's IP
```bash
arp -a
# or
cat /var/lib/misc/dnsmasq.leases
# or
nmap -sn 10.42.0.0/24
```

## Raspberry Pi Setup

### 1. Enable serial port (one time)
```bash
sudo raspi-config
# Interface Options → Serial Port → Login shell: No, Hardware enabled: Yes
# Reboot
```

### 2. Serial port fix
Previous sessions can leave the port in a bad state. The code runs `stty sane` automatically before opening. If `cat /dev/serial0` shows nothing:
```bash
stty -F /dev/serial0 9600 sane
```

### 3. Disable screen blanking
Already configured. If screen goes black after reboot:
```bash
export DISPLAY=:0
xset s off
xset -dpms
xset s noblank
```

Persistent fix in `/etc/lightdm/lightdm.conf`:
```
[Seat:*]
xserver-command=X -s 0 -dpms
```

### 4. Install dependencies
```bash
cd ~/Projects/seeboard
source venv/bin/activate
pip install pyserial pynmea2 tkintermapview pillow
sudo apt install python3-tk
```

## Project Structure

```
~/Projects/seeboard/
├── gps_console.py        ← POC: GPS on console
├── gps_gui.py            ← POC: GPS on screen
├── camera.py             ← POC: ESP32-CAM stream viewer
├── venv/                 ← Python virtual environment
└── seeboard/         ← Main project
    ├── seeboard.py           ← Entry point (thin orchestrator, view switching)
    ├── coords_view.py    ← COORDS view (GPS display + update loop)
    ├── map_view.py       ← MAP view (offline OpenStreetMap)
    ├── cam_view.py       ← CAM view (multi-camera streams + grid)
    ├── conf_view.py      ← CONF view (settings UI)
    ├── gps_core.py       ← GPS logic (serial, NMEA parsing, DMS conversion)
    ├── cam_discovery.py  ← mDNS camera discovery
    ├── see_board.cfg     ← Persistent configuration
    ├── main.md           ← This documentation
    ├── charts/           ← KAP chart files (unused)
    ├── maps/tiles/       ← Offline OSM tiles (osm_tiles.db, 148 MB)
    └── requirements.txt
```

## Running

```bash
cd ~/Projects/seeboard
source venv/bin/activate
python app/seeboard.py
```

Press **Escape** to exit.

## GPS Core (gps_core.py)

- Resets serial port with `stty sane` before opening (fixes broken state)
- Opens `/dev/serial0` at 9600 baud
- Parses GGA sentences (position, quality, satellite count)
- Returns dict: `{'status': 'fix'|'no_fix'|'no_data', ...}`

## Offline Map Tiles

Downloaded for Karlskrona area (zoom 8–17, 148 MB):
- Bounding box: NW(56.225, 15.242) to SE(55.944, 16.118)
- Stored in: `maps/tiles/osm_tiles.db`
- Auto-detected by seeboard.py if file exists

To re-download or extend:
```python
from tkintermapview import OfflineLoader
loader = OfflineLoader(path="maps/tiles/osm_tiles.db",
    tile_server="https://a.tile.openstreetmap.org/{z}/{x}/{y}.png", max_zoom=17)
loader.save_offline_tiles((56.225, 15.242), (55.944, 16.118), zoom_a=8, zoom_b=17)
```

## ESP32-CAM Firmware

Source: `firmware/esp32-cam/` (in this project)

Key details:
- Board: Freenove ESP32-WROVER-CAM (esp-wrover-kit in PlatformIO)
- WiFi: Station mode, connects to GREEN-BEAN (no password)
- Retries WiFi connection forever (Pi might boot later)
- mDNS hostname: esp32-cam.local
- Web page: port 80, Stream: port 81 (`/stream`)
- Uses esp_http_server (supports multiple concurrent clients)
- LED blinks while connecting, off when ready, rapid blink = camera error
- Flash mode: DIO
- Partition: huge_app.csv

Build & flash (from desktop):
```bash
cd ~/Projects/seeboard/firmware/esp32-cam
pio run -t upload
```

## Camera Stream in seeboard.py

- Background thread continuously reads MJPEG from `http://esp32-cam.local:81/stream`
- Extracts JPEG frames by finding 0xFFD8/0xFFD9 markers
- Rotates image -90° (camera mounted sideways)
- Displays at ~30fps when CAM view is active
- Auto-reconnects on connection loss
- Buffer capped at 200KB to prevent lag

## GPS Quality Values

| Value | Name     | Meaning               |
|-------|----------|-----------------------|
| 0     | No fix   | Not enough satellites |
| 1     | GPS fix  | ~2.5–5m accuracy      |
| 2     | DGPS fix | ~1–2m                 |
| 3     | PPS fix  | Sub-meter             |

## Troubleshooting

- **`cat /dev/serial0` shows nothing**: Run `stty -F /dev/serial0 9600 sane` first
- **GPS "Waiting for fix"**: Move antenna outdoors/near window. Cold start 1–5 min.
- **ESP32 LED keeps blinking**: Not connecting to GREEN-BEAN. Check Pi's hotspot is active: `nmcli dev status`
- **Camera stream freezes**: ESP32 may have crashed. Power cycle it. The app auto-reconnects.
- **Screen goes black**: Run `xset s off && xset -dpms` or check lightdm config
- **Can't SSH to Pi when hotspot active**: Connect your laptop to GREEN-BEAN, SSH to 10.42.0.1
- **OpenCPN**: Broken on this Pi (segfault). Using tkintermapview instead.

## CONF View (Configuration)

Settings are stored in `see_board.cfg` (INI format, absolute path used internally).

### Available Settings

| Setting              | Section | Key               | Default |
|----------------------|---------|-------------------|---------|
| Show decimal seconds | gps     | show_dms_decimals | False   |
| Camera rotation      | cam     | rotation          | 0       |

### Behavior
- Changes are saved to  immediately when toggled
- When switching to COORDS view, the config file is re-read and applied
- GPS coordinates are formatted at display time (not at parse time), so changes take effect within 1 second of switching views

### Config File Format
```ini
[gps]
show_dms_decimals = True

[cam]
rotation = 90
```


### DMS Display Formats
- **Decimals OFF**: 
- **Decimals ON**: 

## TODO
- SAVE button — waypoint storage in SQLite
- REC/STOP button — continuous track recording to SQLite
- gpsd integration — share GPS between multiple apps

## Multi-Camera System

### Architecture
```
Pi (GREEN-BEAN AP) ←WiFi→ ESP32-CAM #1 (esp32-cam-a1b2.local)
                   ←WiFi→ ESP32-CAM #2 (esp32-cam-c3d4.local)
                   ←WiFi→ ESP32-CAM #3 (esp32-cam-e5f6.local)
                   ...
```

### Auto-Discovery
- Cameras advertise `_mjpeg._tcp` mDNS service on port 81
- Pi uses `zeroconf` library to discover all cameras automatically
- No hardcoded URLs — plug in a new camera and it appears on screen

### Grid Layout (CAM view)
- 1 camera → fullscreen
- 2 cameras → 2 columns, 1 row
- 3-4 cameras → 2x2 grid
- 5-6 cameras → 3x2 grid
- 7-9 cameras → 3x3 grid

Layout rebuilds automatically when cameras connect/disconnect.

### Camera Hostnames
Each ESP32 gets a unique mDNS name from its MAC address:
`esp32-cam-XXYY.local` (last 2 bytes of MAC in hex)

### Project Files
- `cam_discovery.py` — mDNS service browser (finds cameras on network)
- `cam_view.py` — multi-camera grid widget (auto-sizing layout)

### Dependencies
```bash
pip install zeroconf pillow
```

### Flashing Cameras
All cameras use the same firmware. Flash from the Pi (with ESP32 connected via USB):
```bash
cd ~/Projects/seeboard/firmware/esp32-cam
pio run -t upload  # connect each ESP32 one at a time
```

### Verifying Discovery
On the Pi, check if cameras are found:
```python
from cam_discovery import start, get_cameras
import time
start()
time.sleep(5)
print(get_cameras())
```

## mDNS Service Discovery Explained

### What is it?
mDNS (multicast DNS) + DNS-SD (service discovery) lets devices announce themselves
on a local network without any manual configuration. Same technology as Apple Bonjour,
Linux Avahi, Chromecast, AirPlay, network printers.

### How our cameras use it
Each ESP32-CAM advertises a custom service `_mjpeg._tcp` on port 81:
```cpp
// In ESP32 firmware:
MDNS.addService("mjpeg", "tcp", 81);
```

The Pi discovers all devices advertising this service:
```python
# In cam_discovery.py:
SERVICE_TYPE = "_mjpeg._tcp.local."
```

The service name `_mjpeg._tcp` is our own choice — not a standard. Both sides just need to match.

### Useful commands

List all cameras on the network:
```bash
avahi-browse -rtp _mjpeg._tcp
```

List all mDNS services on the network:
```bash
avahi-browse -all
```

Resolve a specific hostname:
```bash
avahi-resolve -n esp32-cam-8550.local
```

Install avahi tools (if not present):
```bash
sudo apt install avahi-utils
```

## Viewing Camera in Browser

Connect your laptop/phone to the GREEN-BEAN WiFi, then open:

```
http://esp32-cam-8550.local:81/stream
```

Or by IP:
```
http://10.42.0.73:81/stream
```

To find camera IPs:
```bash
avahi-browse -rtp _mjpeg._tcp
# or
arp -a
```

**Note**: Each ESP32 can only serve ~1 stream client at a time. If seeboard.py is
streaming from a camera (CAM view active), the browser won't connect to that
same camera. Switch to COORDS/MAP view first to free the stream slot.

## CAM View Behavior

### Grid rules
- 1 camera → fullscreen
- 2 cameras → side by side
- 3-4 cameras → 2x2 grid
- Layout uses full available space, maintains aspect ratio

### Dynamic behavior
- **New camera connects** (while on CAM view): grid auto-rebuilds to include it
- **Camera disconnects** (while on CAM view): its slot goes black, grid stays
- **Click CAM button** (even if already on CAM): clears discovery cache, re-discovers only live cameras, rebuilds grid fresh. Dead camera placeholders are removed.

### Technical flow on CAM button press
1. Stop all active streams
2. Clear discovery cache (reset)
3. Restart mDNS discovery
4. Wait 2 seconds for live cameras to respond
5. Rebuild grid with only responding cameras
