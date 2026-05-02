"""COORDS view — displays GPS coordinates, time, quality, satellites."""

import tkinter as tk
from gps_core import read_gps, _dd_to_dms
import gps_core


def create(parent, fonts, config, config_file):
    """Create the COORDS view frame and return (frame, update_func, on_show).

    Args:
        parent: parent tkinter widget
        fonts: dict with FONT_COORD, FONT_INFO, FONT_STATUS
        config: ConfigParser instance
        config_file: absolute path to config file
    Returns:
        frame, update_gps, on_show
    """
    frame = tk.Frame(parent, bg='black')

    lat_var = tk.StringVar(value="---.------")
    lon_var = tk.StringVar(value="---.------")
    time_var = tk.StringVar(value="Time: --:--:--")
    qual_var = tk.StringVar(value="Quality: -")
    sat_var = tk.StringVar(value="Satellites: - used / - visible")
    status_var = tk.StringVar(value="")

    tk.Label(frame, textvariable=lat_var, font=fonts["FONT_COORD"],
             fg='lime', bg='black').pack(pady=(40, 5))
    tk.Label(frame, textvariable=lon_var, font=fonts["FONT_COORD"],
             fg='lime', bg='black').pack(pady=5)
    tk.Label(frame, textvariable=time_var, font=fonts["FONT_INFO"],
             fg='white', bg='black').pack(pady=10)
    tk.Label(frame, textvariable=qual_var, font=fonts["FONT_INFO"],
             fg='white', bg='black').pack(pady=5)
    tk.Label(frame, textvariable=sat_var, font=fonts["FONT_INFO"],
             fg='white', bg='black').pack(pady=5)
    tk.Label(frame, textvariable=status_var, font=fonts["FONT_STATUS"],
             fg='red', bg='black').pack(pady=20)

    # State for GPS update loop
    empty_reads = [0]
    last_pos = [None, None]  # [lat, lon]

    def on_show():
        """Called when switching to COORDS view — re-read config."""
        config.read(config_file)
        gps_core.SHOW_DMS_DECIMALS = config.getboolean(
            'gps', 'show_dms_decimals', fallback=False)

    def update_gps(root, get_view_mode, marker, map_widget):
        """Read GPS and update display. Schedules itself via root.after."""
        data = read_gps()

        if data is None:
            root.after(100, lambda: update_gps(root, get_view_mode, marker, map_widget))
            return

        if data["status"] == "error":
            status_var.set(f"\u26a0 {data['message']} \u2014 reconnecting...")
            root.after(2000, lambda: update_gps(root, get_view_mode, marker, map_widget))
            return

        if data['status'] == 'no_data':
            empty_reads[0] += 1
            if empty_reads[0] >= 10:
                status_var.set("\u26a0 No GPS data \u2014 check wiring!")
                empty_reads[0] = 0
            root.after(100, lambda: update_gps(root, get_view_mode, marker, map_widget))
            return

        empty_reads[0] = 0
        status_var.set("")

        if data['status'] == 'fix':
            lat_var.set(f"{_dd_to_dms(data['lat_raw'])} {data['lat_dir']}")
            lon_var.set(f"{_dd_to_dms(data['lon_raw'])} {data['lon_dir']}")
            time_var.set(f"Time: {data['time']}")
            qual_var.set(f"Quality: {data['quality']}")
            sat_var.set(f"Satellites: {data['sats_used']} used / {data['sats_visible']} visible")

            lat = data['lat_raw']
            lon = data['lon_raw']
            if lat != last_pos[0] or lon != last_pos[1]:
                marker.set_position(lat, lon)
                if get_view_mode() == 'map':
                    map_widget.set_position(lat, lon)
                last_pos[0] = lat
                last_pos[1] = lon
        else:
            lat_var.set("---.------")
            lon_var.set("---.------")
            status_var.set("Waiting for fix...")
            qual_var.set("Quality: No fix")
            time_var.set(f"Time: {data['time']}")
            sat_var.set(f"Satellites: {data['sats_used']} used / {data['sats_visible']} visible")

        root.after(1000, lambda: update_gps(root, get_view_mode, marker, map_widget))

    return frame, update_gps, on_show
