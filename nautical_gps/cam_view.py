"""
Camera View — displays multiple MJPEG streams in a grid layout.

Grid logic:
  1 camera  → full screen
  2 cameras → 2 columns, 1 row
  3-4 cameras → 2x2 grid
  5-6 cameras → 3x2 grid
  7-9 cameras → 3x3 grid
"""

import tkinter as tk
from PIL import Image, ImageTk
import urllib.request
import io
import threading
import time
import socket
import math
from cam_discovery import start as start_discovery, stop as stop_discovery, get_cameras


class CameraStream:
    """Handles reading a single MJPEG stream in a background thread."""

    def __init__(self, url):
        self.url = url
        self.current_frame = None
        self.lock = threading.Lock()
        self.running = True
        self.thread = threading.Thread(target=self._reader, daemon=True)
        self.thread.start()

    def _reader(self):
        MAX_BUF = 200000
        while self.running:
            try:
                stream = urllib.request.urlopen(self.url, timeout=5)
                stream.fp.raw._sock.settimeout(10)
                buf = b''
                while self.running:
                    chunk = stream.read(4096)
                    if not chunk:
                        break
                    buf += chunk
                    if len(buf) > MAX_BUF:
                        buf = buf[-MAX_BUF:]
                    while True:
                        start = buf.find(b'\xff\xd8')
                        end = buf.find(b'\xff\xd9', start + 2) if start != -1 else -1
                        if start != -1 and end != -1:
                            jpg = buf[start:end + 2]
                            buf = buf[end + 2:]
                            with self.lock:
                                self.current_frame = jpg
                        else:
                            break
            except (urllib.error.URLError, socket.timeout, OSError):
                pass
            time.sleep(1)

    def get_frame(self):
        with self.lock:
            frame = self.current_frame
            self.current_frame = None
            return frame

    def stop(self):
        self.running = False


class CamView(tk.Frame):
    """Multi-camera grid view widget."""

    def __init__(self, parent):
        super().__init__(parent, bg='black')
        self.streams = {}  # {url: CameraStream}
        self.labels = {}   # {url: tk.Label}
        self.known_cameras = {}
        self.running = True

        # Status label shown when no cameras found
        self.status_var = tk.StringVar(value="Searching for cameras...")
        self.status_label = tk.Label(self, textvariable=self.status_var,
                                     font=("Helvetica", 18), fg='white', bg='black')
        self.status_label.place(relx=0.5, rely=0.5, anchor='center')

        start_discovery()

    def update_view(self):
        """Check for camera changes and update the grid. Call periodically."""
        if not self.running:
            return

        cameras = get_cameras()

        # Check if camera list changed
        if cameras != self.known_cameras:
            self.known_cameras = cameras
            self._rebuild_grid()

        # Update each camera's image
        for url, stream in list(self.streams.items()):
            if url not in self.labels:
                continue
            label = self.labels[url]
            w = label.winfo_width()
            h = label.winfo_height()
            if w < 10 or h < 10:
                continue  # Label not rendered yet, wait
            frame = stream.get_frame()
            if frame:
                try:
                    img = Image.open(io.BytesIO(frame)).rotate(-90, expand=True)
                    img = img.resize((w, h), Image.LANCZOS)
                    photo = ImageTk.PhotoImage(img)
                    label.config(image=photo)
                    label.image = photo
                except Exception:
                    pass

    def _rebuild_grid(self):
        """Rebuild the grid layout based on current camera count."""
        # Stop old streams
        for stream in self.streams.values():
            stream.stop()
        self.streams.clear()

        # Remove old labels
        for label in self.labels.values():
            label.destroy()
        self.labels.clear()

        urls = list(self.known_cameras.values())
        n = len(urls)

        if n == 0:
            self.status_label.place(relx=0.5, rely=0.5, anchor='center')
            self.status_var.set("Searching for cameras...")
            return

        self.status_label.place_forget()

        # Calculate grid dimensions
        cols = math.ceil(math.sqrt(n))
        rows = math.ceil(n / cols)

        # Reset all grid weights to 0 first (clear old layout)
        for r in range(10):
            self.grid_rowconfigure(r, weight=0, minsize=0)
        for c in range(10):
            self.grid_columnconfigure(c, weight=0, minsize=0)

        # Set uniform weights for active rows/cols
        for r in range(rows):
            self.grid_rowconfigure(r, weight=1, uniform=row)
        for c in range(cols):
            self.grid_columnconfigure(c, weight=1, uniform=col)

        # Create labels and streams — all cells same size
        for i, url in enumerate(urls):
            r = i // cols
            c = i % cols
            label = tk.Label(self, bg='black')
            label.grid(row=r, column=c, sticky='nsew', padx=1, pady=1)
            self.labels[url] = label
            self.streams[url] = CameraStream(url)

    def stop(self):
        self.running = False
        for stream in self.streams.values():
            stream.stop()
        stop_discovery()
