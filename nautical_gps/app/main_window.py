"""
Main window — left panel (coords) + right panel (buttons).
MAP button launches OpenCPN as external app, minimizes this window.
"""
import tkinter as tk
import subprocess
import shutil
from app import gps_reader
from app.coords_view import CoordsView


class MainWindow:
    def __init__(self):
        gps_reader.init()

        self.root = tk.Tk()
        self.root.title("Nautical GPS")
        self.root.configure(bg='black')
        self.root.attributes('-fullscreen', True)
        self.root.bind('<Escape>', lambda e: self.root.destroy())

        self.opencpn_process = None

        # --- Right panel: buttons (fixed width) ---
        self.btn_panel = tk.Frame(self.root, bg='#222222', width=120)
        self.btn_panel.pack(side='right', fill='y')
        self.btn_panel.pack_propagate(False)  # Keep fixed width

        # MAP button — launches OpenCPN
        self.map_btn = tk.Button(
            self.btn_panel, text="MAP", font=("Helvetica", 16, "bold"),
            bg='#444444', fg='white', activebackground='#666666',
            command=self.launch_opencpn
        )
        self.map_btn.pack(fill='x', padx=5, pady=(20, 10), ipady=15)

        # TODO: SAVE button — store current coordinate as waypoint in SQLite
        tk.Button(
            self.btn_panel, text="SAVE", font=("Helvetica", 16, "bold"),
            bg='#444444', fg='gray', state='disabled'
        ).pack(fill='x', padx=5, pady=5, ipady=15)

        # TODO: REC/STOP button — continuous coordinate recording to SQLite
        tk.Button(
            self.btn_panel, text="REC", font=("Helvetica", 16, "bold"),
            bg='#444444', fg='gray', state='disabled'
        ).pack(fill='x', padx=5, pady=5, ipady=15)

        # TODO: EXIT button
        tk.Button(
            self.btn_panel, text="EXIT", font=("Helvetica", 16, "bold"),
            bg='#444444', fg='gray', state='disabled'
        ).pack(fill='x', padx=5, pady=5, ipady=15)

        # --- Left panel: coordinates display ---
        self.content = tk.Frame(self.root, bg='black')
        self.content.pack(side='left', fill='both', expand=True)

        self.coords_view = CoordsView(self.content)
        self.coords_view.pack(fill='both', expand=True)

    def launch_opencpn(self):
        """Minimize this app, launch OpenCPN, restore when OpenCPN closes."""
        if not shutil.which('opencpn'):
            # Show warning in the content area
            self.show_message("OpenCPN not installed\n\nsudo apt install opencpn")
            return

        # Minimize our window
        self.root.iconify()

        # Launch OpenCPN
        self.opencpn_process = subprocess.Popen(['opencpn'])

        # Poll every second to check if OpenCPN has closed
        self.check_opencpn()

    def show_message(self, text):
        """Briefly show a message in the content area."""
        msg = tk.Label(self.content, text=text, font=("Helvetica", 24),
                       fg='red', bg='black')
        msg.pack(pady=50)
        # Remove after 3 seconds
        self.root.after(3000, msg.destroy)

    def check_opencpn(self):
        """Check if OpenCPN is still running. Restore our window when it exits."""
        if self.opencpn_process and self.opencpn_process.poll() is not None:
            # OpenCPN has closed — restore our window
            self.opencpn_process = None
            self.root.deiconify()
            self.root.attributes('-fullscreen', True)
        else:
            # Still running — check again in 1 second
            self.root.after(1000, self.check_opencpn)

    def update(self):
        """Read GPS and update the display."""
        data = gps_reader.read()
        self.coords_view.update_data(data)
        self.root.after(1000, self.update)

    def run(self):
        """Start the application."""
        self.root.after(1000, self.update)
        self.root.mainloop()
        gps_reader.close()
