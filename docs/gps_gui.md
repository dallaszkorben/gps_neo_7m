# GPS GUI — Proof of Concept

## What it does
Simple fullscreen display of GPS coordinates using tkinter.
No buttons, no split screen — just proves GPS data can be shown in a GUI window.

## Running

```bash
cd ~/Projects/gps_neo_7m
source venv/bin/activate
python gps_gui.py
```

Press **Escape** to exit.

## Display
- Black background, fullscreen
- Latitude & Longitude in big bold green text (48pt)
- Time, satellites, quality in smaller white text

## Notes
- Resets serial port at startup (`stty sane`) to fix leftover bad state
- Shows "Waiting for fix..." when GPS can't see enough satellites
- For the full application with buttons and OpenCPN, see `nautical_gps/main.py`
