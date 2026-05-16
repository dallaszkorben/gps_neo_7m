# ESP32-CAM WiFi Streaming

## Overview
ESP32-WROVER-DEV with OV2640 camera. Connects to Raspberry Pi's WiFi AP and serves a live MJPEG video stream.

## Architecture
```
Raspberry Pi (GREEN-BEAN AP, 10.42.0.1)
     ↑ WiFi (no password)
ESP32-CAM (client, esp32-cam.local)
     ↑ Camera
OV2640 sensor
```

## Hardware
- **Board**: Freenove ESP32-WROVER-CAM (ESP32-Wrover-E, 4MB PSRAM)
- **Camera**: OV2640 (640x480 VGA, JPEG)
- **USB chip**: CH340 (built-in programmer, /dev/ttyUSB0)
- **LED**: GPIO 2 (status indicator)

## WiFi Configuration
- Mode: **Station** (connects to Pi's AP)
- Target SSID: **GREEN-BEAN**
- Password: **none** (open network)
- mDNS hostname: **esp32-cam.local**
- Retries forever until connected (Pi might boot later)
- Auto-reconnects if WiFi drops

## Access URLs (from Pi or any device on GREEN-BEAN network)
- Web page: `http://esp32-cam.local` (port 80)
- Direct stream: `http://esp32-cam.local:81/stream`
- Or by IP: `http://10.42.0.x:81/stream`

## LED Behavior
| Pattern | Meaning |
|---------|---------|
| Blinking (slow) | Trying to connect to WiFi |
| Rapid blink | Camera init failed (halted) |
| Off | Running normally, connected |

## Camera Pin Mapping (Freenove ESP32-WROVER-CAM)

| Function | GPIO |
|----------|------|
| XCLK | 21 |
| SIOD (SDA) | 26 |
| SIOC (SCL) | 27 |
| Y9–Y2 | 35, 34, 39, 36, 19, 18, 5, 4 |
| VSYNC | 25 |
| HREF | 23 |
| PCLK | 22 |
| PWDN | -1 (not used) |
| RESET | -1 (not used) |

## Project Structure
```
~/Projects/seeboard/firmware/esp32-cam/
├── platformio.ini      # Build config (esp-wrover-kit, DIO flash, huge_app)
├── src/
│   └── main.cpp        # Firmware source (commented)
└── esp32-cam.md        # This documentation
```

## PlatformIO Configuration
```ini
[env:esp32cam]
platform = espressif32
board = esp-wrover-kit
framework = arduino
monitor_speed = 115200
upload_port = /dev/ttyUSB0
board_build.partitions = huge_app.csv
board_build.flash_mode = dio
upload_speed = 460800
build_flags = -DBOARD_HAS_PSRAM
```

## Building & Flashing
```bash
cd ~/Projects/seeboard/firmware/esp32-cam
pio run              # Build only
pio run -t upload    # Build + flash
```

ESP32 must be connected via USB (/dev/ttyUSB0).

## Key Design Decisions

### Why esp_http_server instead of Arduino WebServer?
Arduino's `WebServer` library is single-threaded — only one client can stream at a time. `esp_http_server` (ESP-IDF native) handles multiple concurrent connections, so multiple devices can view the stream simultaneously.

### Why two ports (80 and 81)?
- Port 80: serves the HTML page (quick response, closes immediately)
- Port 81: serves the MJPEG stream (long-lived connection, stays open)

Separating them prevents the stream from blocking page requests.

### Why mDNS?
The ESP32 gets a dynamic IP from the Pi's DHCP. mDNS (`esp32-cam.local`) provides a stable hostname so the Pi's `camera.py` doesn't need to know the IP.

### Camera mounted sideways
The image is rotated -90° in the Pi's display code (`camera.py` and `main.py`), not on the ESP32. This keeps the ESP32 firmware simple and avoids wasting its CPU on rotation.

## Troubleshooting

- **LED keeps blinking**: Pi's hotspot not active. On Pi: `sudo nmcli connection up Hotspot`
- **Camera init fails (0x20004)**: Camera ribbon cable loose. Reseat it.
- **Stream freezes after a while**: Known issue with long connections. Pi's viewer auto-reconnects.
- **Can't flash**: Check /dev/ttyUSB0 exists (`lsusb | grep CH340`). Try holding BOOT button during upload.
- **mDNS not resolving**: Install avahi on Pi: `sudo apt install avahi-daemon`

## Network Notes
- Pi's AP subnet: 10.42.0.0/24 (nmcli shared mode default)
- Pi's IP: 10.42.0.1
- ESP32 gets IP via DHCP (typically 10.42.0.x)
- To find ESP32's IP: `arp -a` or `cat /var/lib/misc/dnsmasq.leases` on Pi

## Multi-Camera Auto-Discovery

### How it works
- Each ESP32-CAM gets a **unique hostname** based on its MAC address (e.g., `esp32-cam-a1b2.local`)
- Advertises `_mjpeg._tcp` mDNS service on port 81
- The Pi discovers all cameras automatically using zeroconf — no hardcoded URLs needed

### Hostname format
`esp32-cam-XXYY` where XX and YY are the last 2 bytes of the MAC address in hex.

### Service advertisement
```cpp
MDNS.addService("mjpeg", "tcp", 81);
```

### Flashing multiple cameras
Each camera gets a unique name automatically (from MAC). Just flash the same firmware to all:
```bash
cd ~/Projects/seeboard/firmware/esp32-cam
# Connect each ESP32 one at a time and run:
pio run -t upload
```

### Pi-side discovery
The Pi uses `zeroconf` Python library to browse for `_mjpeg._tcp.local.` services.
When a camera appears/disappears, the grid layout updates automatically.

### Grid layout (on Pi's screen)
- 1 camera → fullscreen
- 2 cameras → side by side (2 columns)
- 3-4 cameras → 2x2 grid
- 5-6 cameras → 3x2 grid
- 7-9 cameras → 3x3 grid

## mDNS Service Advertisement

### How it works
The ESP32 uses mDNS (same as Apple Bonjour / Linux Avahi) to announce itself:
- Broadcasts a unique hostname: `esp32-cam-XXYY.local` (from MAC address)
- Advertises service type: `_mjpeg._tcp` on port 81

This lets the Pi auto-discover cameras without knowing their IPs.

### The service name `_mjpeg._tcp`
This is a custom name we chose (not an official standard). Both the ESP32 firmware
and the Pi's discovery code use the same name to find each other.

### Verifying from the Pi
```bash
# List all cameras advertising _mjpeg._tcp:
avahi-browse -rtp _mjpeg._tcp

# Resolve a camera hostname to IP:
avahi-resolve -n esp32-cam-8550.local

# Install avahi tools if needed:
sudo apt install avahi-utils
```

## Current Firmware Source (main.cpp)

```cpp
/*
 * ESP32-CAM MJPEG Streaming Firmware
 *
 * This firmware runs on a Freenove ESP32-WROVER-CAM board.
 * It connects to the Raspberry Pi's WiFi access point (GREEN-BEAN)
 * and serves a live MJPEG video stream over HTTP.
 *
 * Architecture:
 *   - ESP32 connects to Pi's AP as a WiFi client (station mode)
 *   - Two HTTP servers run on different ports:
 *     Port 80: serves an HTML page with embedded stream
 *     Port 81: serves the raw MJPEG stream (supports multiple clients)
 *   - mDNS advertises the device as "esp32-cam.local"
 *
 * Access:
 *   http://esp32-cam.local      — HTML page with embedded video
 *   http://esp32-cam.local:81/stream — direct MJPEG stream
 *
 * LED behavior (GPIO 2):
 *   Blinking = trying to connect to WiFi
 *   Rapid blink = camera init failed (halted)
 *   Off = running normally
 */

#include <Arduino.h>
#include <WiFi.h>
#include <ESPmDNS.h>
#include <esp_http_server.h>
#include "esp_camera.h"

// WiFi — connect to Pi's access point (open, no password)
const char* WIFI_SSID = "GREEN-BEAN";

// Status LED — built-in on GPIO 2
#define LED_PIN 2

// ─── Camera pin mapping for Freenove ESP32-WROVER-CAM ───
// These are fixed by the board's PCB layout — do not change
#define PWDN_GPIO_NUM    -1   // Not used (no power-down pin)
#define RESET_GPIO_NUM   -1   // Not used (no hardware reset pin)
#define XCLK_GPIO_NUM    21   // Camera clock input
#define SIOD_GPIO_NUM    26   // I2C data (camera config)
#define SIOC_GPIO_NUM    27   // I2C clock (camera config)
#define Y9_GPIO_NUM      35   // Data bit 7
#define Y8_GPIO_NUM      34   // Data bit 6
#define Y7_GPIO_NUM      39   // Data bit 5
#define Y6_GPIO_NUM      36   // Data bit 4
#define Y5_GPIO_NUM      19   // Data bit 3
#define Y4_GPIO_NUM      18   // Data bit 2
#define Y3_GPIO_NUM       5   // Data bit 1
#define Y2_GPIO_NUM       4   // Data bit 0
#define VSYNC_GPIO_NUM   25   // Vertical sync
#define HREF_GPIO_NUM    23   // Horizontal reference
#define PCLK_GPIO_NUM    22   // Pixel clock

// ─── MJPEG stream constants ───
// These define the HTTP multipart boundary used to separate JPEG frames
#define PART_BOUNDARY "frame"
static const char* STREAM_CONTENT_TYPE = "multipart/x-mixed-replace;boundary=" PART_BOUNDARY;
static const char* STREAM_BOUNDARY = "\r\n--" PART_BOUNDARY "\r\n";
static const char* STREAM_PART = "Content-Type: image/jpeg\r\nContent-Length: %u\r\n\r\n";

// HTTP server handles (two separate servers on different ports)
httpd_handle_t stream_httpd = NULL;
httpd_handle_t web_httpd = NULL;

// ─── Camera initialization ───
bool initCamera() {
    camera_config_t config;
    config.ledc_channel = LEDC_CHANNEL_0;
    config.ledc_timer = LEDC_TIMER_0;
    config.pin_d0 = Y2_GPIO_NUM;
    config.pin_d1 = Y3_GPIO_NUM;
    config.pin_d2 = Y4_GPIO_NUM;
    config.pin_d3 = Y5_GPIO_NUM;
    config.pin_d4 = Y6_GPIO_NUM;
    config.pin_d5 = Y7_GPIO_NUM;
    config.pin_d6 = Y8_GPIO_NUM;
    config.pin_d7 = Y9_GPIO_NUM;
    config.pin_xclk = XCLK_GPIO_NUM;
    config.pin_pclk = PCLK_GPIO_NUM;
    config.pin_vsync = VSYNC_GPIO_NUM;
    config.pin_href = HREF_GPIO_NUM;
    config.pin_sccb_sda = SIOD_GPIO_NUM;
    config.pin_sccb_scl = SIOC_GPIO_NUM;
    config.pin_pwdn = PWDN_GPIO_NUM;
    config.pin_reset = RESET_GPIO_NUM;
    config.xclk_freq_hz = 20000000;       // 20MHz clock to camera
    config.pixel_format = PIXFORMAT_JPEG;  // Hardware JPEG encoding
    config.frame_size = FRAMESIZE_VGA;     // 640x480 resolution
    config.jpeg_quality = 12;              // 0-63, lower = better quality
    config.fb_count = 2;                   // Double buffer for smoother streaming
    config.grab_mode = CAMERA_GRAB_LATEST; // Always get the newest frame

    esp_err_t err = esp_camera_init(&config);
    if (err != ESP_OK) {
        Serial.printf("Camera init failed: 0x%x\n", err);
        return false;
    }
    Serial.println("Camera initialized OK");
    return true;
}

// ─── MJPEG stream handler ───
// Each connected client gets its own instance of this handler.
// It continuously captures frames and sends them as multipart JPEG.
// The connection stays open until the client disconnects.
static esp_err_t stream_handler(httpd_req_t *req) {
    esp_err_t res = ESP_OK;
    char part_buf[64];

    res = httpd_resp_set_type(req, STREAM_CONTENT_TYPE);
    if (res != ESP_OK) return res;

    while (true) {
        camera_fb_t *fb = esp_camera_fb_get();
        if (!fb) {
            Serial.println("Camera capture failed");
            res = ESP_FAIL;
            break;
        }

        // Send boundary, then content-type/length header, then JPEG data
        size_t hlen = snprintf(part_buf, 64, STREAM_PART, fb->len);
        res = httpd_resp_send_chunk(req, STREAM_BOUNDARY, strlen(STREAM_BOUNDARY));
        if (res == ESP_OK)
            res = httpd_resp_send_chunk(req, part_buf, hlen);
        if (res == ESP_OK)
            res = httpd_resp_send_chunk(req, (const char*)fb->buf, fb->len);

        esp_camera_fb_return(fb);
        if (res != ESP_OK) break;  // Client disconnected
    }
    return res;
}

// ─── HTML page handler ───
// Serves a simple page that embeds the stream in an <img> tag.
// The browser handles MJPEG natively in <img src="...">.
static esp_err_t index_handler(httpd_req_t *req) {
    char html[256];
    snprintf(html, sizeof(html),
        "<html><head><title>ESP32-CAM</title></head>"
        "<body style='margin:0;background:#000;'>"
        "<img src='http://%s:81/stream' style='width:100%%;height:100vh;object-fit:contain;'>"
        "</body></html>",
        WiFi.localIP().toString().c_str());
    httpd_resp_set_type(req, "text/html");
    return httpd_resp_send(req, html, strlen(html));
}

// ─── Start both HTTP servers ───
// Port 80: HTML page (lightweight, quick response)
// Port 81: MJPEG stream (long-lived connections, handles multiple clients)
// Using esp_http_server instead of Arduino WebServer because it supports
// concurrent connections — multiple devices can view the stream simultaneously.
void startWebServer() {
    httpd_config_t config = HTTPD_DEFAULT_CONFIG();
    config.server_port = 80;

    if (httpd_start(&web_httpd, &config) == ESP_OK) {
        httpd_uri_t index_uri = {
            .uri = "/",
            .method = HTTP_GET,
            .handler = index_handler,
            .user_ctx = NULL
        };
        httpd_register_uri_handler(web_httpd, &index_uri);
        Serial.println("Web server on port 80");
    }

    // Separate server on port 81 for streaming
    config.server_port = 81;
    config.ctrl_port = 32769;  // Must differ from port 80's control port

    if (httpd_start(&stream_httpd, &config) == ESP_OK) {
        httpd_uri_t stream_uri = {
            .uri = "/stream",
            .method = HTTP_GET,
            .handler = stream_handler,
            .user_ctx = NULL
        };
        httpd_register_uri_handler(stream_httpd, &stream_uri);
        Serial.println("Stream server on port 81");
    }
}

// ─── WiFi connection with infinite retry ───
// The Pi's AP might not be running yet when the ESP32 boots,
// so we retry forever until connected. LED blinks during attempts.
void connectWiFi() {
    while (true) {
        // Full WiFi reset on each attempt — ensures clean state
        WiFi.disconnect(true);
        WiFi.mode(WIFI_OFF);
        delay(1000);
        WiFi.mode(WIFI_STA);
        WiFi.begin(WIFI_SSID);

        Serial.printf("Connecting to '%s'...\n", WIFI_SSID);
        int attempts = 0;
        while (WiFi.status() != WL_CONNECTED && attempts < 20) {
            delay(500);
            Serial.print(".");
            digitalWrite(LED_PIN, !digitalRead(LED_PIN));
            attempts++;
        }

        if (WiFi.status() == WL_CONNECTED) {
            Serial.printf("\nConnected! IP: %s\n", WiFi.localIP().toString().c_str());
            digitalWrite(LED_PIN, LOW);  // LED off = connected
            return;
        }

        // AP not available yet — wait and retry
        Serial.println("\nFailed. Retrying in 5s...");
        delay(5000);
    }
}

void setup() {
    Serial.begin(115200);
    delay(1000);
    Serial.println("\n\nESP32-CAM Starting...");

    pinMode(LED_PIN, OUTPUT);
    digitalWrite(LED_PIN, HIGH);  // LED on during init

    // Camera init with 3 retries (sometimes first attempt fails after cold boot)
    bool cam_ok = false;
    for (int i = 0; i < 3; i++) {
        cam_ok = initCamera();
        if (cam_ok) break;
        Serial.printf("Camera retry %d/3...\n", i + 1);
        delay(1000);
    }

    if (!cam_ok) {
        // Rapid blink = camera hardware error, halted
        Serial.println("Camera failed. Halting.");
        while (true) {
            digitalWrite(LED_PIN, !digitalRead(LED_PIN));
            delay(200);
        }
    }

    connectWiFi();
    startWebServer();

    // mDNS: unique hostname based on last 4 chars of MAC address
    // e.g., "esp32-cam-a1b2.local" — each camera gets a unique name
    uint8_t mac[6];
    WiFi.macAddress(mac);
    char hostname[20];
    snprintf(hostname, sizeof(hostname), "esp32-cam-%02x%02x", mac[4], mac[5]);

    if (MDNS.begin(hostname)) {
        // Advertise _mjpeg._tcp service so Pi can auto-discover all cameras
        MDNS.addService("mjpeg", "tcp", 81);
        Serial.printf("mDNS: %s.local\n", hostname);
    }

    Serial.printf("Ready! http://%s.local:81/stream\n", hostname);
}

void loop() {
    // Monitor WiFi — reconnect if connection drops
    if (WiFi.status() != WL_CONNECTED) {
        Serial.println("WiFi lost. Reconnecting...");
        connectWiFi();
    }
    delay(1000);
}
```
