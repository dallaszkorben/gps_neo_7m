# Camera POC — ESP32-CAM Stream Viewer

## What it does
Displays the live MJPEG stream from ESP32-CAM fullscreen on the Pi's 7" touchscreen.
Simple proof-of-concept — for the full app with GPS + map + camera, use `nautical_gps/main.py`.

## Prerequisites
1. Pi's WiFi hotspot active: `sudo nmcli connection up Hotspot`
2. ESP32-CAM powered and connected (LED stops blinking)
3. Pillow installed: `pip install pillow`

## Running
```bash
cd ~/Projects/gps_neo_7m
source venv/bin/activate
python camera.py
```
Press **Escape** to exit.

## Network
- Pi runs AP: GREEN-BEAN (no password), IP: 10.42.0.1
- ESP32 connects as client, reachable at esp32-cam.local
- Stream URL: http://esp32-cam.local:81/stream

## How it works
- Background thread reads MJPEG stream via HTTP
- Finds JPEG frames by 0xFFD8/0xFFD9 markers
- Rotates -90° (camera mounted sideways)
- Displays fullscreen at ~30fps
- Auto-reconnects if stream drops
- Shows "Waiting for stream..." only after 3s of no frames

## Troubleshooting
- **Black screen, "Connecting..."**: ESP32 not connected. Check LED is off (not blinking).
- **Freezes after minutes**: Stream stalled. App auto-reconnects within 10s.
- **Wrong rotation**: Change `rotate(-90, expand=True)` to `rotate(90, ...)` or `rotate(180, ...)`
- **mDNS not working**: `sudo apt install avahi-daemon` or use IP directly
