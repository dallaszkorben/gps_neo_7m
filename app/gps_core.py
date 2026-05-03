"""
GPS Core — shared GPS reading logic.
"""

import serial
import pynmea2
import re
import time
import termios
import os
import atexit

SERIAL_PORT = '/dev/serial0'
BAUD_RATE = 9600
QUALITY_NAMES = ['No fix', 'GPS fix', 'DGPS fix', 'PPS fix']

# Show decimal seconds in DMS format (e.g., 18.99" vs 19")
SHOW_DMS_DECIMALS = False

_sats_in_view = '0'

def _dd_to_dms(dd):
    """Convert decimal degrees to degrees, minutes, seconds string."""
    d = int(dd)
    m_full = (dd - d) * 60
    m = int(m_full)
    s = (m_full - m) * 60
    if SHOW_DMS_DECIMALS:
        return f"{d}°{m:02d}'{s:05.2f}\""
    else:
        return f"{d}°{m:02d}'{int(round(s)):02d}\""

_ser = None
_original_termios = None


def _save_port_settings():
    global _original_termios
    if _original_termios is not None:
        return
    try:
        fd = os.open(SERIAL_PORT, os.O_RDWR | os.O_NOCTTY | os.O_NONBLOCK)
        _original_termios = termios.tcgetattr(fd)
        os.close(fd)
    except Exception:
        pass


def _restore_port_settings():
    global _original_termios
    if _original_termios is None:
        return
    try:
        fd = os.open(SERIAL_PORT, os.O_RDWR | os.O_NOCTTY | os.O_NONBLOCK)
        termios.tcsetattr(fd, termios.TCSANOW, _original_termios)
        os.close(fd)
    except Exception:
        pass


def open_serial():
    global _ser
    if _ser:
        try:
            _ser.close()
        except Exception:
            pass
        _ser = None

    _save_port_settings()

    try:
        _ser = serial.Serial(
            port=SERIAL_PORT,
            baudrate=BAUD_RATE,
            bytesize=serial.EIGHTBITS,
            parity=serial.PARITY_NONE,
            stopbits=serial.STOPBITS_ONE,
            timeout=2,
        )
        _ser.reset_input_buffer()
        return True
    except (serial.SerialException, OSError) as e:
        print(f"Cannot open serial port: {e}")
        _ser = None
        return False


def read_gps():
    global _sats_in_view, _ser

    if not _ser or not _ser.is_open:
        if not open_serial():
            time.sleep(1)
            return {'status': 'error', 'message': 'Cannot open serial port'}

    try:
        raw = _ser.readline()
    except (serial.SerialException, OSError) as e:
        print(f"Serial error: {e}")
        try:
            _ser.close()
        except Exception:
            pass
        _ser = None
        time.sleep(1)
        return {'status': 'error', 'message': str(e)}

    if not raw:
        return {'status': 'no_data'}

    line = raw.decode('ascii', errors='replace').strip()
    if not line:
        return None
    if not line.startswith('$'):
        return None

    if line.startswith('$GPGSV') or line.startswith('$GNGSV'):
        match = re.match(r'\$G[PN]GSV,\d+,\d+,(\d+)', line)
        if match:
            _sats_in_view = match.group(1)
        return None

    if not (line.startswith('$GPGGA') or line.startswith('$GNGGA')):
        return None

    try:
        msg = pynmea2.parse(line)
    except pynmea2.ParseError:
        return None

    if msg.lat_dir:
        return {
            'status': 'fix',
            'time': str(msg.timestamp),
            'lat': _dd_to_dms(msg.latitude),
            'lat_raw': msg.latitude,
            'lat_dir': msg.lat_dir,
            'lon': _dd_to_dms(msg.longitude),
            'lon_raw': msg.longitude,
            'lon_dir': msg.lon_dir,
            'quality': QUALITY_NAMES[min(msg.gps_qual, 3)],
            'sats_used': str(msg.num_sats or '0'),
            'sats_visible': _sats_in_view,
        }
    else:
        return {
            'status': 'no_fix',
            'time': str(msg.timestamp),
            'sats_used': str(msg.num_sats or '0'),
            'sats_visible': _sats_in_view,
        }


def close():
    global _ser
    if _ser:
        try:
            _ser.close()
        except Exception:
            pass
        _ser = None
    _restore_port_settings()


atexit.register(close)
