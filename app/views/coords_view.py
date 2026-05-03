"""COORDS view — displays GPS coordinates, time, quality, satellites.

This is the primary navigation view showing position in DMS format.
The update loop runs continuously (even when another view is visible)
so that the map marker stays current regardless of which view is active.
"""

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

    # StringVars allow the labels to update without recreating widgets.
    # Initial values show placeholder dashes until GPS data arrives.
    lat_var = tk.StringVar(value="--°--'--\"")
    lon_var = tk.StringVar(value="---°--'--\"")
    time_var = tk.StringVar(value="Time: --:--:--")
    qual_var = tk.StringVar(value="Quality: -")
    sat_var = tk.StringVar(value="Satellites: - used / - visible")
    status_var = tk.StringVar(value="")

    # Large green text for coordinates — must be readable from a distance
    # on a boat in daylight. Lime on black provides high contrast.
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
    # Red for errors/warnings — draws attention to problems
    tk.Label(frame, textvariable=status_var, font=fonts["FONT_STATUS"],
             fg='red', bg='black').pack(pady=20)

    # Mutable state in lists so nested functions can modify them.
    # (Python closures can read but not assign to outer variables without nonlocal)
    empty_reads = [0]
    last_pos = [None, None]  # [lat, lon]

    def on_show():
        """Called when switching to COORDS view — re-read config from file.

        The config file is re-read (not just the in-memory object) because
        conf_view writes changes to disk. This ensures the DMS decimal
        setting takes effect immediately when the user switches views.
        """
        config.read(config_file)
        gps_core.SHOW_DMS_DECIMALS = config.getboolean(
            'gps', 'show_dms_decimals', fallback=False)

    def update_gps(root, get_view_mode, marker, map_widget):
        """Read GPS and update display. Schedules itself via root.after.

        This loop runs regardless of which view is active because:
        1. The map marker needs continuous position updates
        2. GPS data must be consumed from the serial buffer to prevent overflow
        3. Switching to COORDS should show current data immediately, not stale
        """
        data = read_gps()

        if data is None:
            # Not a GGA/GSV sentence — try again quickly
            root.after(100, lambda: update_gps(root, get_view_mode, marker, map_widget))
            return

        if data["status"] == "error":
            status_var.set(f"\u26a0 {data['message']} \u2014 reconnecting...")
            # Wait longer on error to avoid hammering a broken port
            root.after(2000, lambda: update_gps(root, get_view_mode, marker, map_widget))
            return

        if data['status'] == 'no_data':
            empty_reads[0] += 1
            # Show warning after 10 consecutive empty reads (~1s at 100ms interval)
            # to alert user about possible wiring issues
            if empty_reads[0] >= 10:
                status_var.set("\u26a0 No GPS data \u2014 check wiring!")
                empty_reads[0] = 0
            root.after(100, lambda: update_gps(root, get_view_mode, marker, map_widget))
            return

        empty_reads[0] = 0
        status_var.set("")

        if data['status'] == 'fix':
            # Format at display time using _dd_to_dms() so that changes to
            # SHOW_DMS_DECIMALS take effect within 1 second (next GPS read)
            # without needing to restart the app.
            lat_var.set(f"{_dd_to_dms(data['lat_raw'])} {data['lat_dir']}")
            lon_var.set(f"{_dd_to_dms(data['lon_raw'])} {data['lon_dir']}")
            time_var.set(f"Time: {data['time']}")
            qual_var.set(f"Quality: {data['quality']}")
            sat_var.set(f"Satellites: {data['sats_used']} used / {data['sats_visible']} visible")

            lat = data['lat_raw']
            lon = data['lon_raw']
            # Only update map when position actually changes to avoid
            # unnecessary redraws (map redraw is expensive on Pi 3)
            if lat != last_pos[0] or lon != last_pos[1]:
                marker.set_position(lat, lon)
                if get_view_mode() == 'map':
                    map_widget.set_position(lat, lon)
                last_pos[0] = lat
                last_pos[1] = lon
        else:
            lat_var.set("--°--'--\"")
            lon_var.set("---°--'--\"")
            status_var.set("Waiting for fix...")
            qual_var.set("Quality: No fix")
            time_var.set(f"Time: {data['time']}")
            sat_var.set(f"Satellites: {data['sats_used']} used / {data['sats_visible']} visible")

        # 1s interval matches the NEO-7M's default 1Hz update rate
        root.after(1000, lambda: update_gps(root, get_view_mode, marker, map_widget))

    return frame, update_gps, on_show
