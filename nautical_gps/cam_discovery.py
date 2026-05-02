"""
Camera Discovery — finds ESP32-CAM devices on the network via mDNS.

Cameras advertise themselves as _mjpeg._tcp services.
This module discovers them and provides their stream URLs.
"""

import threading
import time
from zeroconf import ServiceBrowser, Zeroconf, ServiceStateChange
import socket

SERVICE_TYPE = "_mjpeg._tcp.local."

_cameras = {}  # {name: "http://ip:port/stream"}
_lock = threading.Lock()
_zeroconf = None
_browser = None


def _on_service_state_change(zeroconf, service_type, name, state_change):
    """Called when a camera appears or disappears on the network."""
    if state_change == ServiceStateChange.Added:
        info = zeroconf.get_service_info(service_type, name)
        if info:
            ip = socket.inet_ntoa(info.addresses[0])
            port = info.port
            url = f"http://{ip}:{port}/stream"
            with _lock:
                _cameras[name] = url

    elif state_change == ServiceStateChange.Removed:
        with _lock:
            _cameras.pop(name, None)


def start():
    """Start discovering cameras on the network."""
    global _zeroconf, _browser
    _zeroconf = Zeroconf()
    _browser = ServiceBrowser(_zeroconf, SERVICE_TYPE, handlers=[_on_service_state_change])


def stop():
    """Stop discovery."""
    global _zeroconf, _browser
    if _zeroconf:
        _zeroconf.close()
        _zeroconf = None
        _browser = None


def get_cameras():
    """Return dict of currently discovered cameras: {name: stream_url}"""
    with _lock:
        return dict(_cameras)


def reset():
    """Stop discovery, clear cache, restart. Call before rebuild."""
    global _cameras
    stop()
    with _lock:
        _cameras = {}
    start()
