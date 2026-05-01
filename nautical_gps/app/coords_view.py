"""
Coordinates view — shows lat/lon in big bold text with time, quality, satellites.
"""
import tkinter as tk


class CoordsView(tk.Frame):
    def __init__(self, parent):
        super().__init__(parent, bg='black')

        self.lat_var = tk.StringVar(value="---.------")
        self.lon_var = tk.StringVar(value="---.------")
        self.time_var = tk.StringVar(value="Time: --:--:--")
        self.qual_var = tk.StringVar(value="Quality: -")
        self.sat_var = tk.StringVar(value="Satellites: -")

        # Big bold green text for coordinates
        tk.Label(self, textvariable=self.lat_var, font=("Helvetica", 48, "bold"),
                 fg='lime', bg='black').pack(pady=(40, 5))
        tk.Label(self, textvariable=self.lon_var, font=("Helvetica", 48, "bold"),
                 fg='lime', bg='black').pack(pady=5)
        # Smaller white text for metadata
        tk.Label(self, textvariable=self.time_var, font=("Helvetica", 24),
                 fg='white', bg='black').pack(pady=10)
        tk.Label(self, textvariable=self.qual_var, font=("Helvetica", 24),
                 fg='white', bg='black').pack(pady=5)
        tk.Label(self, textvariable=self.sat_var, font=("Helvetica", 24),
                 fg='white', bg='black').pack(pady=5)

    def update_data(self, data):
        """Update displayed values from a GPS data dict."""
        if data:
            self.lat_var.set(f"{data['lat']:.6f} {data['lat_dir']}")
            self.lon_var.set(f"{data['lon']:.6f} {data['lon_dir']}")
            self.time_var.set(f"Time: {data['time']}")
            self.qual_var.set(f"Quality: {data['quality']}")
            self.sat_var.set(f"Satellites: {data['satellites']}")
