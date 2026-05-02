#!/usr/bin/env python3
"""Download offline map tiles for Karlskrona area."""
from tkintermapview import OfflineLoader

# Karlskrona archipelago area
SW = (56.05, 15.30)
NE = (56.25, 15.80)

loader = OfflineLoader(
    path="../maps/tiles/osm_tiles.db",
    tile_server="https://a.tile.openstreetmap.org/{z}/{x}/{y}.png",
    max_zoom=15
)

print("Downloading tiles... this may take a few minutes.")
loader.save_offline_tiles(SW, NE, zoom_a=8, zoom_b=15)
print("Done — tiles saved to maps/tiles/osm_tiles.db")
