"""MAP view — offline OpenStreetMap with GPS position marker."""

import tkinter as tk
import os
import tkintermapview


# Default position (Karlskrona)
DEFAULT_LAT = 56.1612
DEFAULT_LON = 15.5869
DEFAULT_ZOOM = 13
TILES_DB = "/home/pi/Projects/gps_neo_7m/nautical_gps/maps/tiles/osm_tiles.db"


def create(parent):
    """Create the MAP view frame and return (frame, map_widget, marker).

    Args:
        parent: parent tkinter widget
    Returns:
        frame, map_widget, marker
    """
    frame = tk.Frame(parent, bg='black')

    map_widget = tkintermapview.TkinterMapView(frame, corner_radius=0)
    map_widget.pack(fill='both', expand=True)
    map_widget.set_tile_server(
        "https://a.tile.openstreetmap.org/{z}/{x}/{y}.png", max_zoom=17)

    if os.path.exists(TILES_DB):
        map_widget.database_path = TILES_DB

    map_widget.set_position(DEFAULT_LAT, DEFAULT_LON)
    map_widget.set_zoom(DEFAULT_ZOOM)
    marker = map_widget.set_marker(DEFAULT_LAT, DEFAULT_LON, text="GPS")

    return frame, map_widget, marker
