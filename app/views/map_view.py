"""MAP view — displays GPS position on an OpenStreetMap.

Uses pre-downloaded offline tiles (SQLite database) so the map works
without internet connection. Tiles cover the Karlskrona area at zoom 8-17.
To download tiles for a different area, use tools/download_tiles.py.
"""

import tkinter as tk
import os
import tkintermapview


# Default map center (Karlskrona, Sweden) shown before GPS fix.
# This ensures the user sees a meaningful map immediately on startup,
# rather than a zoomed-out world view or empty area.
DEFAULT_LAT = 56.1612
DEFAULT_LON = 15.5869
DEFAULT_ZOOM = 13

# Pre-downloaded OSM tiles (148 MB, zoom 8-17, Karlskrona area).
# Stored as SQLite because tkintermapview's OfflineLoader uses this format.
# The database must be generated beforehand using tools/download_tiles.py.
TILES_DB = "/home/pi/Projects/seeboard/app/maps/tiles/osm_tiles.db"


def create(parent):
    """Create the MAP view frame with an interactive map and GPS marker.

    The map uses offline tiles from a local SQLite database. If the database
    is missing, it falls back to fetching tiles from the internet.

    Args:
        parent: parent tkinter widget
    Returns:
        tuple: (frame, map_widget, marker)
            - frame: the view's tk.Frame
            - map_widget: TkinterMapView instance (for position updates)
            - marker: map marker (for GPS position updates)
    """
    frame = tk.Frame(parent, bg='black')

    # database_path and use_database_only are passed in the constructor
    # (not set afterwards) because set_tile_server() triggers immediate
    # tile fetching. If we set them after construction, the widget would
    # attempt internet requests before knowing it should use local tiles only.
    if os.path.exists(TILES_DB):
        map_widget = tkintermapview.TkinterMapView(
            frame, corner_radius=0,
            database_path=TILES_DB, use_database_only=True, max_zoom=17)
    else:
        # Fallback: fetch tiles from OpenStreetMap (requires internet).
        # This path only runs during development when tiles haven't been
        # downloaded yet — in production the Pi has no internet in AP mode.
        map_widget = tkintermapview.TkinterMapView(frame, corner_radius=0)
        map_widget.set_tile_server(
            "https://a.tile.openstreetmap.org/{z}/{x}/{y}.png", max_zoom=17)
    map_widget.pack(fill='both', expand=True)

    # Set initial view to default position until GPS provides a fix.
    # The coords_view update loop will call marker.set_position() and
    # map_widget.set_position() once a GPS fix is acquired.
    map_widget.set_position(DEFAULT_LAT, DEFAULT_LON)
    map_widget.set_zoom(DEFAULT_ZOOM)
    marker = map_widget.set_marker(DEFAULT_LAT, DEFAULT_LON, text="GPS")

    return frame, map_widget, marker
