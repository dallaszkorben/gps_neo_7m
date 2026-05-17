"""
GPS Core — serial port management and NMEA sentence parsing.

Handles the NEO-7M GPS module connected via UART (/dev/serial0).
Key design decisions:
- Uses pyserial (not stty) to configure the port, so Python controls all settings.
- Saves/restores termios settings via atexit so that `cat /dev/serial0` still
  works after the script exits (even on crash).
- Auto-reconnects on serial errors without crashing the GUI.
- Returns raw float lat/lon alongside DMS strings so callers can use either.
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

# Human-readable names for GGA quality indicator values
QUALITY_NAMES = ['No fix', 'GPS fix', 'DGPS fix', 'PPS fix']

# Controls whether DMS format includes decimal seconds (e.g., 18.99" vs 19").
# Modified at runtime by conf_view when user toggles the setting.
SHOW_DMS_DECIMALS = False

# Satellites in view, updated from GSV sentences.
# Stored module-level because GSV and GGA arrive in separate sentences.
_sats_in_view = '0'


def _dd_to_dms(dd):
    """Convert decimal degrees to DMS string (e.g., 56°10'18").

    Called at display time (not parse time) so that changes to
    SHOW_DMS_DECIMALS take effect immediately without waiting for
    a new GPS sentence.
    """
    d = int(dd)
    m_full = (dd - d) * 60
    m = int(m_full)
    s = (m_full - m) * 60
    if SHOW_DMS_DECIMALS:
        return f"{d}\u00b0{m:02d}'{s:05.2f}\""
    else:
        return f"{d}\u00b0{m:02d}'{int(round(s)):02d}\""


_ser = None
_original_termios = None


def _save_port_settings():
    """Save the serial port's original termios settings.

    Done once before we open the port with pyserial. This lets us restore
    the exact original state on exit, so other tools (cat, minicom) still
    work on the port without needing `stty sane`.
    """
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
    """Restore the serial port to its original termios state.

    Called on exit (via atexit) to undo any changes pyserial made.
    Without this, `cat /dev/serial0` may show garbled output or nothing.
    """
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
    """Open the GPS serial port. Returns True on success, False on failure.

    Closes any existing connection first to handle reconnection cleanly.
    Saves termios before opening so we can restore on exit.
    """
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
            # 0.1s timeout: must be short to avoid blocking the tkinter main loop.
            # GPS sends data every 1s; we poll frequently with short timeout.
            timeout=0.1,
        )
        _ser.reset_input_buffer()
        return True
    except (serial.SerialException, OSError) as e:
        print(f"Cannot open serial port: {e}")
        _ser = None
        return False


def read_gps():
    """Read one NMEA sentence and return parsed GPS data.

    Returns:
        dict with 'status' key:
            'fix'     — valid position (includes lat/lon/time/quality/sats)
            'no_fix'  — GPS running but no satellite lock yet
            'no_data' — empty read (timeout, no sentence available)
            'error'   — serial port problem (will auto-reconnect next call)
        None — sentence was not GGA/GSV (ignored, call again)

    Design: returns raw floats (lat_raw, lon_raw) alongside formatted DMS
    strings. The raw values are used by the map for positioning; the DMS
    strings are legacy and may be removed in the future since coords_view
    now formats at display time using _dd_to_dms() directly.
    """
    global _sats_in_view, _ser

    # Auto-reconnect if port was lost
    if not _ser or not _ser.is_open:
        if not open_serial():
            time.sleep(1)
            return {'status': 'error', 'message': 'Cannot open serial port'}

    try:
        raw = _ser.readline()
    except (serial.SerialException, OSError) as e:
        # Port disappeared (USB unplug, kernel error). Close and let next
        # call attempt reconnection.
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

    # GSV sentences carry satellite-in-view count. We extract it here
    # and store it module-level because GGA (position) sentences don't
    # include this information.
    if line.startswith('$GPGSV') or line.startswith('$GNGSV'):
        match = re.match(r'\$G[PN]GSV,\d+,\d+,(\d+)', line)
        if match:
            _sats_in_view = match.group(1)
        return None

    # Only process GGA sentences (position + quality + sat count)
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
    """Close serial port and restore original termios settings."""
    global _ser
    if _ser:
        try:
            _ser.close()
        except Exception:
            pass
        _ser = None
    _restore_port_settings()


# ─── Background GPS reader thread ───
# GPS reading is done in a background thread to avoid blocking the tkinter
# main loop. Without this, the 0.1s serial timeout would freeze the UI
# (especially camera display) every time read_gps() is called.
# The main thread polls get_latest() which returns instantly.
# Runs continuously, stores latest parsed data in _latest_data.
# The main thread (tkinter) reads _latest_data without blocking.
import threading

_latest_data = None
_gps_thread = None
_gps_running = False


def _gps_reader_loop():
    """Background thread: continuously reads GPS and stores latest result.
    Clears stored data after repeated errors (GPS disconnected)."""
    global _latest_data
    _error_count = 0
    while _gps_running:
        data = read_gps()
        if data is not None and data.get('status') in ('fix', 'no_fix'):
            _latest_data = data
            _error_count = 0
        elif data is not None and data.get('status') == 'error':
            _error_count += 1
            # After 3 consecutive errors (~3s), clear data to signal GPS lost
            if _error_count >= 3:
                _latest_data = None
        elif data is not None and data.get('status') == 'no_data':
            _error_count += 1
            if _error_count >= 30:
                # 30 empty reads (~3s at 0.1s timeout) = GPS disconnected
                _latest_data = None
        # Small sleep to prevent tight loop when no data
        if data is None or (data and data.get('status') == 'no_data'):
            time.sleep(0.05)


def start_background_reader():
    """Start the background GPS reader thread."""
    global _gps_thread, _gps_running
    _gps_running = True
    _gps_thread = threading.Thread(target=_gps_reader_loop, daemon=True)
    _gps_thread.start()


def stop_background_reader():
    """Stop the background GPS reader thread."""
    global _gps_running
    _gps_running = False


def get_latest():
    """Get the latest GPS data (non-blocking, called from main thread)."""
    return _latest_data


atexit.register(close)
