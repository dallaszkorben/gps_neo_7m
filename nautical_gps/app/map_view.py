"""
Map view — shows current position on an OpenSeaMap nautical chart.
Uses tkintermapview to render map tiles.
"""
import tkinter as tk
import os
import tkintermapview

# Path to offline tiles (if downloaded)
TILES_DIR = os.path.join(os.path.dirname(__file__), '..', 'maps', 'tiles')


class MapView(tk.Frame):
    def __init__(self, parent):
        super().__init__(parent, bg='black')

        # Create the map widget filling the entire frame
        self.map_widget = tkintermapview.TkinterMapView(self, corner_radius=0)
        self.map_widget.pack(fill='both', expand=True)

        # Use OpenStreetMap as base map (shows coastline, land, water)
        # Note: OpenSeaMap overlay (buoys, lights) is not available as combined tiles
        # in tkintermapview since it only supports one tile layer at a time.
        # For full nautical charts, consider OpenCPN alongside this app.
        self.map_widget.set_tile_server(
            "https://a.tile.openstreetmap.org/{z}/{x}/{y}.png",
            max_zoom=17
        )

        # Use offline tiles database if available
        offline_db = os.path.join(TILES_DIR, 'osm_tiles.db')
        if os.path.exists(offline_db):
            self.map_widget.database_path = offline_db

        # Default position (will be updated by GPS)
        self.map_widget.set_position(56.1612, 15.5869)
        self.map_widget.set_zoom(14)

        # Marker for current position
        self.marker = self.map_widget.set_marker(56.1612, 15.5869, text="GPS")

    def update_data(self, data):
        """Move the map and marker to current GPS position."""
        if data:
            lat = data['lat']
            lon = data['lon']
            self.map_widget.set_position(lat, lon)
            self.marker.set_position(lat, lon)
