#!/usr/bin/env -S python3 -u
"""
GPS Console — Proof of Concept.
Simple terminal output of GPS coordinates. Never quits on errors — retries forever.
"""
import atexit

import sys
import time
sys.path.insert(0, "/home/pi/Projects/seeboard")
from gps_core import open_serial, read_gps, close
atexit.register(close)

# Initial connection (retries until successful)
while not open_serial():
    print("Retrying in 3s...")
    time.sleep(3)

print("Reading GPS... (Ctrl+C to quit)")

empty_reads = 0

while True:
    try:
        data = read_gps()

        if data is None:
            continue

        if data['status'] == 'error':
            # Serial port lost — gps_core will reconnect on next read_gps() call
            print(f"⚠ {data['message']} — reconnecting...")
            time.sleep(2)
            continue

        if data['status'] == 'no_data':
            empty_reads += 1
            if empty_reads >= 10:
                print("WARNING: No data from GPS for 20 seconds.")
                print("  - Check wiring (GPS TX → Pi pin 10)")
                empty_reads = 0
            continue

        empty_reads = 0

        if data['status'] == 'fix':
            print(f"Time:       {data['time']}")
            print(f"Latitude:   {data['lat']} {data['lat_dir']}")
            print(f"Longitude:  {data['lon']} {data['lon_dir']}")
            print(f"Quality:    {data['quality']}")
            print(f"Satellites: {data['sats_used']} used / {data['sats_visible']} visible")
        else:
            print(f"Waiting for fix... Satellites: {data['sats_used']} used / {data['sats_visible']} visible")

        print("-" * 40)

    except KeyboardInterrupt:
        print("\nExiting.")
        close()
        break
