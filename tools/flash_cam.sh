#!/bin/bash
# Flash ESP32-CAM firmware via PlatformIO.
# Must be run from a desktop/laptop with the ESP32 toolchain installed.

FIRMWARE_DIR="$(dirname "$0")/../firmware/esp32-cam"

# Block on Raspberry Pi — too slow for ESP32 compilation
if grep -q "Raspberry Pi" /proc/device-tree/model 2>/dev/null; then
    echo "ERROR: This script cannot run on Raspberry Pi."
    echo ""
    echo "ESP32 compilation is too slow on Pi (~5 min) and the toolchain"
    echo "requires ~500 MB of disk space. Flash from a desktop/laptop instead:"
    echo ""
    echo "  cd ~/Projects/seeboard/firmware/esp32-cam"
    echo "  pio run -t upload"
    exit 1
fi

# Check PlatformIO is installed
if ! command -v pio &>/dev/null; then
    echo "ERROR: PlatformIO (pio) is not installed on this machine."
    echo ""
    echo "Install with: pip install platformio"
    exit 1
fi

# Check ESP32 toolchain is available
if [ ! -d "$HOME/.platformio/packages/toolchain-xtensa-esp32" ]; then
    echo "ERROR: ESP32 toolchain is not installed."
    echo ""
    echo "The toolchain is downloaded automatically on first PlatformIO build."
    echo "Run once with internet connection:"
    echo ""
    echo "  cd ~/Projects/seeboard/firmware/esp32-cam"
    echo "  pio run"
    exit 1
fi

# Check ESP32 is connected via USB (auto-detect port)
USB_PORT=$(ls /dev/ttyUSB* 2>/dev/null | head -1)
if [ -z "$USB_PORT" ]; then
    echo "ERROR: No ESP32 found. No /dev/ttyUSB* device detected."
    echo ""
    echo "Connect the ESP32-CAM via USB and try again."
    exit 1
fi
echo "Found ESP32 on: $USB_PORT"

cd "$FIRMWARE_DIR" || { echo "Error: firmware directory not found"; exit 1; }
echo "Flashing ESP32-CAM..."
pio run -t upload --upload-port "$USB_PORT"
