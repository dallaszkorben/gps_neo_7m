#!/usr/bin/env python3
"""
Camera POC — displays MJPEG stream from ESP32-CAM on the Pi's screen.

The ESP32-CAM connects to the Pi's WiFi AP (GREEN-BEAN) and serves
a live MJPEG stream. This script reads that stream and displays it
fullscreen using tkinter.

Architecture:
  - Background thread: continuously reads JPEG frames from the HTTP stream
  - Main thread: displays the latest frame on screen at ~30fps
  - Auto-reconnects if the stream drops (ESP32 rebooted, WiFi glitch, etc.)

Usage:
  source ~/Projects/seeboard/venv/bin/activate
  python camera.py
  Press Escape to exit.
"""

import tkinter as tk
from PIL import Image, ImageTk
import urllib.request
import io
import threading
import time
import socket

# ESP32-CAM stream URL — uses mDNS name so IP doesn't matter
STREAM_URL = "http://esp32-cam.local:81/stream"

# Max buffer size in bytes. If the buffer grows beyond this,
# old data is discarded to prevent memory issues and lag.
MAX_BUF = 200000  # ~2 JPEG frames worth

# ─── GUI setup ───
root = tk.Tk()
root.title("ESP32-CAM")
root.configure(bg='black')
root.attributes('-fullscreen', True)

# Label widget that displays the video frames
label = tk.Label(root, bg='black')
label.pack(fill='both', expand=True)

# Status message shown when stream is not active
status_var = tk.StringVar(value="Connecting to ESP32-CAM...")
status_label = tk.Label(root, textvariable=status_var, font=("Helvetica", 18),
                        fg='white', bg='black')
status_label.place(relx=0.5, rely=0.5, anchor='center')

# Shared state between the reader thread and the display loop
current_frame = None       # Latest JPEG bytes (or None if no new frame)
frame_lock = threading.Lock()
running = True
last_frame_time = 0        # Timestamp of last received frame


def stream_reader():
    """Background thread: reads the MJPEG stream and extracts JPEG frames.

    MJPEG over HTTP works by sending a continuous multipart response where
    each part is a JPEG image. We find frames by looking for JPEG markers:
      - 0xFF 0xD8 = start of JPEG
      - 0xFF 0xD9 = end of JPEG
    """
    global current_frame, running, last_frame_time
    while running:
        try:
            # Open HTTP connection to the ESP32's stream endpoint
            stream = urllib.request.urlopen(STREAM_URL, timeout=5)
            # Set a read timeout so we detect stalls (ESP32 crashed, WiFi lost)
            stream.fp.raw._sock.settimeout(10)
            buf = b''

            while running:
                chunk = stream.read(4096)
                if not chunk:
                    break  # Connection closed by ESP32 — reconnect
                buf += chunk

                # Prevent buffer from growing forever (causes lag and memory issues)
                if len(buf) > MAX_BUF:
                    buf = buf[-MAX_BUF:]

                # Extract all complete JPEG frames from the buffer
                while True:
                    start = buf.find(b'\xff\xd8')  # JPEG start marker
                    end = buf.find(b'\xff\xd9', start + 2) if start != -1 else -1  # JPEG end
                    if start != -1 and end != -1:
                        jpg = buf[start:end + 2]
                        buf = buf[end + 2:]
                        # Store the latest frame for the display loop
                        with frame_lock:
                            current_frame = jpg
                            last_frame_time = time.time()
                    else:
                        break  # No complete frame yet — read more data

        except (urllib.error.URLError, socket.timeout, OSError):
            pass  # Connection failed or timed out — will retry below

        # Wait before reconnecting (ESP32 might be rebooting)
        time.sleep(1)


def update_display():
    """Main thread: shows the latest frame on screen.

    Called every 33ms (~30fps) by tkinter's after() scheduler.
    Only updates the display when a new frame is available.
    Shows a "waiting" message if no frames arrive for 3+ seconds.
    """
    global current_frame
    frame = None
    with frame_lock:
        if current_frame:
            frame = current_frame
            current_frame = None

    if frame:
        try:
            # Decode JPEG and resize to fill the screen
            img = Image.open(io.BytesIO(frame)).rotate(-90, expand=True)
            screen_w = root.winfo_width()
            screen_h = root.winfo_height()
            if screen_w > 1 and screen_h > 1:
                img = img.resize((screen_w, screen_h), Image.LANCZOS)
            photo = ImageTk.PhotoImage(img)
            label.config(image=photo)
            label.image = photo  # Keep reference to prevent garbage collection
            status_label.place_forget()  # Hide status message
        except Exception:
            pass
    else:
        # Only show "waiting" if no frame for 3+ seconds (not between every frame)
        if time.time() - last_frame_time > 3 and last_frame_time > 0:
            status_var.set("Waiting for stream...")
            status_label.place(relx=0.5, rely=0.5, anchor='center')

    if running:
        root.after(33, update_display)


def on_close():
    """Clean shutdown — stop the reader thread and close the window."""
    global running
    running = False
    root.destroy()


root.protocol("WM_DELETE_WINDOW", on_close)
root.bind('<Escape>', lambda e: on_close())

# Start the stream reader in a background thread (daemon=True means it dies with main)
thread = threading.Thread(target=stream_reader, daemon=True)
thread.start()

# Start the display update loop
root.after(100, update_display)
root.mainloop()
