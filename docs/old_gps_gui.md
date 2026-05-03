# Nautical GPS — GUI Application

## Project Structure

```
nautical_gps/
├── run.py                  # Entry point — run this to start
├── requirements.txt        # Python dependencies
├── app/
│   ├── __init__.py
│   ├── main_window.py      # Main window: layout, button panel, OpenCPN launch
│   ├── coords_view.py      # Big bold coordinate display
│   ├── map_view.py         # (unused) Embedded map widget — replaced by OpenCPN
│   └── gps_reader.py       # Serial GPS reader + demo mode fallback
├── charts/                 # OpenCPN chart files (.kap)
│   └── OSM-OpenCPN2-KAP-Baltic-20240325-1313/  # Baltic Sea KAP charts
├── maps/
│   └── tiles/              # Offline map tiles (tkintermapview, unused currently)
├── data/                   # SQLite database (future: waypoints, tracks)
└── docs/                   # This documentation
```

## How It Works

### Layout
```
+----------------------------------+--------+
|                                  | [MAP]  |
|   Big bold GPS coordinates       | [SAVE] |
|   (lat, lon, time, quality,      | [REC]  |
|    satellites)                    | [EXIT] |
|                                  |        |
+----------------------------------+--------+
         ~80% width                 ~20%
```

### MAP Button Behavior
1. Press **MAP** → your app minimizes → **OpenCPN** launches fullscreen with offline charts
2. Close OpenCPN → your app restores to fullscreen

### Demo Mode
Activates automatically when:
- Serial port `/dev/serial0` doesn't exist (desktop testing)
- `pyserial` or `pynmea2` not installed

Generates fake GPS coordinates near Karlskrona with slight random movement.

## Setup on Desktop (Ubuntu) for Testing

### 1. Python environment

```bash
cd ~/Projects/python/gps
source venv/bin/activate
pip install -r nautical_gps/requirements.txt
```

Note: `tkinter` must be installed system-wide:
```bash
sudo apt install python3-tk
```

### 2. Install OpenCPN

```bash
sudo apt install opencpn
```

### 3. Configure OpenCPN charts

Run `opencpn` once manually, then:
- Go to **Options → Charts → Chart Directories**
- Click **Add Directory**
- Point to: `/home/akoel/Projects/python/gps/nautical_gps/charts/OSM-OpenCPN2-KAP-Baltic-20240325-1313/`
- Click **Apply**

The Baltic Sea charts (including Karlskrona) will load.

### 4. Run the app

```bash
cd ~/Projects/python/gps/nautical_gps
source ../venv/bin/activate
python3 run.py
```

Press **Escape** to exit fullscreen.

## Setup on Raspberry Pi

### 1. Enable serial port (one time)

```bash
sudo raspi-config
# Interface Options → Serial Port
# Login shell: No
# Hardware enabled: Yes
# Reboot
```

### 2. Install dependencies

```bash
cd ~/Projects/gps_project
python3 -m venv venv
source venv/bin/activate
pip install pyserial pynmea2 tkintermapview
sudo apt install python3-tk opencpn
```

### 3. Configure OpenCPN charts on Pi

- Copy the `charts/` folder to the Pi (or download directly)
- Open OpenCPN → Options → Charts → Add Directory → point to the charts folder
- Apply

### 4. Run

```bash
source venv/bin/activate
python3 run.py
```

Since `/dev/serial0` exists on the Pi, it will use the real GPS automatically.

## Charts

### Current charts
- **OSM-OpenCPN2-KAP-Baltic**: Raster KAP charts covering the Baltic Sea (including Karlskrona area)
- Downloaded from: https://ftp.gwdg.de/pub/misc/openstreetmap/openseamap/charts/kap/
- Format: `.kap` files (BSB/KAP raster nautical charts)

### First-time OpenCPN chart setup (required once)

OpenCPN does NOT auto-detect charts. You must manually add the chart directory:

1. Open OpenCPN (press MAP in the app, or run `opencpn` directly)
2. Click the **wrench/settings icon** (or go to **Options**)
3. Go to the **Charts** tab
4. Click **Add Directory**
5. Navigate to: `/home/akoel/Projects/python/gps/nautical_gps/charts/OSM-OpenCPN2-KAP-Baltic-20240325-1313/`
6. Click **OK** / **Apply**
7. OpenCPN scans and indexes the `.kap` files

After this, zoom into the Baltic/Karlskrona area — charts will render. OpenCPN remembers this setting permanently.

**If charts don't appear when zooming in:**
- Zoom **out** first — chart coverage areas show as colored rectangles
- Zoom **into** one of those rectangles to see the chart detail
- Charts only cover certain zoom levels; if you zoom too far in/out they disappear

### Adding more charts
1. Download `.kap` files for your area
2. Place them in `nautical_gps/charts/`
3. Add the directory in OpenCPN: Options → Charts → Add Directory

### Chart sources (free)
- **OpenSeaMap KAP charts**: https://ftp.gwdg.de/pub/misc/openstreetmap/openseamap/charts/kap/
- **CM93 worldwide vector charts**: Search "CM93 charts download"
- **Swedish official charts (Sjöfartsverket)**: Available via OpenCPN Chart Downloader plugin

## GPS Hardware

### NEO-7M Wiring to Raspberry Pi

| NEO-7M | → | RPi Pin | GPIO |
|--------|---|---------|------|
| VCC | → | Pin 1 | 3.3V |
| GND | → | Pin 6 | GND |
| TX | → | Pin 10 | GPIO 15 (RXD) |
| RX | → | Pin 8 | GPIO 14 (TXD) |

**TX↔RX are crossed** — GPS TX connects to Pi RX and vice versa.

### Serial port
- Device: `/dev/serial0`
- Baud rate: 9600
- Protocol: NMEA 0183 (GGA sentences)

### GPS data source priority

The app tries these in order:
1. **gpsd** — if gpsd daemon is running, reads from it (allows GPS sharing with OpenCPN)
2. **Direct serial** — if gpsd not available, reads `/dev/serial0` directly
3. **Demo mode** — if no GPS hardware found (desktop testing)

### gpsd setup on Raspberry Pi (recommended)

gpsd allows both your app AND OpenCPN to read GPS simultaneously:

```bash
sudo apt install gpsd gpsd-clients
```

Configure `/etc/default/gpsd`:
```
DEVICES="/dev/serial0"
GPSD_OPTIONS="-n"
```

Restart:
```bash
sudo systemctl restart gpsd
```

Verify:
```bash
cgps
```

Then configure OpenCPN: **Options → Connections → Add → GPSD, localhost, port 2947**

Both apps now share GPS data — no conflicts even when REC is running while viewing the map.

## GPS Quality Values

| Value | Name | Meaning |
|-------|------|---------|
| 0 | Invalid | No fix — not enough satellites |
| 1 | GPS fix | Standard positioning, ~2.5–5m accuracy |
| 2 | DGPS fix | Differential GPS with ground corrections, ~1–2m |
| 3 | PPS fix | Precise Positioning Service, sub-meter |

## Troubleshooting

- **MAP button shows "OpenCPN not installed"**: Run `sudo apt install opencpn`
- **No output from `cat /dev/serial0`**: Check wiring, verify serial enabled in raspi-config
- **Always 0 satellites**: Move antenna outdoors or near window
- **Serial port busy**: Check with `sudo lsof /dev/serial0`
- **tkinter not found**: `sudo apt install python3-tk`
- **GUI doesn't appear over SSH**: Use `export DISPLAY=:0` or run directly on the Pi desktop

## TODO (Future Features)
- **SAVE button** — store current coordinate as named waypoint in SQLite
- **REC/STOP button** — continuous coordinate recording to SQLite (track log)
- **EXIT button** — clean shutdown
