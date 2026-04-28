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
