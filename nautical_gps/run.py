#!/usr/bin/env python3
"""
Nautical GPS Application
Entry point — run this to start the app.
"""
from app.main_window import MainWindow

if __name__ == '__main__':
    app = MainWindow()
    app.run()
