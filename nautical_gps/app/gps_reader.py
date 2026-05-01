"""
GPS data reader.
Priority: gpsd → direct serial → demo mode.

- gpsd: allows multiple apps to share GPS (needed when OpenCPN + this app run together)
- serial: fallback if gpsd not running
- demo: fake data when no GPS hardware available (desktop testing)
"""
import random

DEMO_MODE = False
_source = None  # 'gpsd', 'serial', or 'demo'
_gpsd_client = None
_ser = None


def init():
    """Try gpsd first, then direct serial, then fall back to demo mode."""
    global _source, _gpsd_client, _ser, DEMO_MODE

    # Try gpsd first
    try:
        from gpsdclient import GPSDClient
        client = GPSDClient()
        # Test connection by getting one result
        stream = client.dict_stream(convert_datetime=False)
        _gpsd_client = stream
        _source = 'gpsd'
        print("GPS source: gpsd")
        return
    except Exception:
        pass

    # Try direct serial
    try:
        import serial
        _ser = serial.Serial('/dev/serial0', baudrate=9600, timeout=0.5)
        _source = 'serial'
        print("GPS source: /dev/serial0 (direct serial)")
        return
    except Exception:
        pass

    # Fall back to demo
    _source = 'demo'
    DEMO_MODE = True
    print("GPS source: DEMO mode (no GPS hardware detected)")


def read():
    """Return a dict with current GPS data, or None if no new fix available.

    Keys: lat, lon, lat_dir, lon_dir, time, quality, satellites
    """
    if _source == 'demo':
        return _read_demo()
    elif _source == 'gpsd':
        return _read_gpsd()
    elif _source == 'serial':
        return _read_serial()
    return None


def _read_demo():
    return {
        'lat': 56.1612 + random.uniform(-0.0001, 0.0001),
        'lon': 15.5869 + random.uniform(-0.0001, 0.0001),
        'lat_dir': 'N',
        'lon_dir': 'E',
        'time': '12:34:56',
        'quality': 'GPS fix',
        'satellites': '8',
    }


def _read_gpsd():
    global _gpsd_client
    try:
        result = next(_gpsd_client)
        if result.get('class') == 'TPV' and 'lat' in result and 'lon' in result:
            lat = result['lat']
            lon = result['lon']
            mode = result.get('mode', 0)
            quality_names = {0: 'Invalid', 1: 'Invalid', 2: '2D fix', 3: '3D fix'}
            return {
                'lat': abs(lat),
                'lon': abs(lon),
                'lat_dir': 'N' if lat >= 0 else 'S',
                'lon_dir': 'E' if lon >= 0 else 'W',
                'time': result.get('time', '--:--:--'),
                'quality': quality_names.get(mode, 'Unknown'),
                'satellites': str(result.get('nSat', '-')),
            }
    except (StopIteration, Exception):
        pass
    return None


def _read_serial():
    import pynmea2
    try:
        line = _ser.readline().decode('ascii', errors='replace').strip()
        if line.startswith('$GPGGA') or line.startswith('$GNGGA'):
            msg = pynmea2.parse(line)
            quality_names = ['Invalid', 'GPS fix', 'DGPS fix', 'PPS fix']
            return {
                'lat': msg.latitude,
                'lon': msg.longitude,
                'lat_dir': msg.lat_dir,
                'lon_dir': msg.lon_dir,
                'time': str(msg.timestamp),
                'quality': quality_names[min(msg.gps_qual, 3)],
                'satellites': str(msg.num_sats),
            }
    except Exception:
        pass
    return None


def close():
    """Close the serial port if open."""
    if _ser:
        _ser.close()
