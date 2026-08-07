# -*- coding: utf-8 -*-
"""
stream_server.py -- NEMO_SENSE Webcam Stream Server
=====================================================
Runs ON the Arduino UNO Q (Debian Linux / Cortex-A53).
Captures the USB webcam and streams MJPEG over WiFi so
a PC running nemo_demo.py can receive and process it.

Protocols supported:
  - MJPEG over HTTP  (http://ARDUINO_IP:8080/)     <- primary, lowest latency
  - Single snapshot  (http://ARDUINO_IP:8080/snap)  <- for testing

Usage on the Arduino UNO Q:
    python3 stream_server.py                 # auto WiFi, port 8080
    python3 stream_server.py --port 9000     # custom port
    python3 stream_server.py --quality 60    # lower JPEG quality = faster
    python3 stream_server.py --width 320 --height 240   # lower resolution

Then on the PC:
    python nemo_demo.py --stream http://192.168.1.X:8080/

Dependencies (already on most Linux systems):
    pip3 install opencv-python-headless
    (no display needed -- headless is smaller and faster)
"""

from __future__ import annotations
import argparse
import logging
import socket
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import cv2
import numpy as np

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [STREAM] %(levelname)s %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("stream")

# ---- Shared frame buffer (thread-safe) --------------------------------------

class FrameBuffer:
    def __init__(self):
        self._lock  = threading.Lock()
        self._frame = None
        self._ts    = 0.0
        self._count = 0

    def put(self, jpg_bytes: bytes):
        with self._lock:
            self._frame = jpg_bytes
            self._ts    = time.monotonic()
            self._count += 1

    def get(self):
        with self._lock:
            return self._frame, self._ts

    @property
    def count(self):
        with self._lock:
            return self._count

_buf = FrameBuffer()

# ---- Capture thread ---------------------------------------------------------

def capture_loop(camera_idx: int, width: int, height: int,
                 fps: int, quality: int, stop_event: threading.Event):
    """Runs in a background thread. Grabs frames and compresses to JPEG."""
    log.info("Opening camera index %d at %dx%d %dfps...", camera_idx, width, height, fps)

    cap = None
    for attempt in range(5):
        cap = cv2.VideoCapture(camera_idx)
        if cap.isOpened():
            break
        log.warning("Camera not ready, retry %d/5...", attempt+1)
        time.sleep(1.0)

    if not cap or not cap.isOpened():
        log.error("Could not open camera %d. Streaming test pattern.", camera_idx)
        cap = None

    if cap:
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, width)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, height)
        cap.set(cv2.CAP_PROP_FPS, fps)
        cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)  # minimal buffer = low latency
        log.info("Camera opened OK. Actual size: %dx%d",
                 int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)),
                 int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT)))

    encode_params = [cv2.IMWRITE_JPEG_QUALITY, quality]
    frame_interval = 1.0 / fps
    t_last = 0.0
    frame_no = 0

    while not stop_event.is_set():
        t_now = time.monotonic()
        if t_now - t_last < frame_interval:
            time.sleep(0.002)
            continue
        t_last = t_now

        if cap:
            ret, frame = cap.read()
            if not ret or frame is None:
                log.warning("Frame grab failed, reconnecting...")
                cap.release()
                time.sleep(0.5)
                cap = cv2.VideoCapture(camera_idx)
                continue
        else:
            # Test pattern -- grey frame with moving dot
            frame = np.full((height, width, 3), 60, dtype=np.uint8)
            cx = int((width/2) + (width/3)*np.sin(t_now*1.2))
            cy = int((height/2) + (height/3)*np.cos(t_now*0.9))
            cv2.circle(frame, (cx, cy), 30, (0, 200, 100), -1)
            cv2.putText(frame, "NO CAMERA - TEST PATTERN",
                        (10, height-10), cv2.FONT_HERSHEY_SIMPLEX,
                        0.45, (180, 180, 180), 1, cv2.LINE_AA)

        # Resize if needed
        if frame.shape[1] != width or frame.shape[0] != height:
            frame = cv2.resize(frame, (width, height))

        # Burn timestamp + frame counter into frame
        ts_str = time.strftime("%H:%M:%S") + f".{int((t_now%1)*100):02d}  #{frame_no}"
        cv2.putText(frame, ts_str, (4, 14),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.4, (0, 255, 120), 1, cv2.LINE_AA)

        ok, jpg = cv2.imencode(".jpg", frame, encode_params)
        if ok:
            _buf.put(jpg.tobytes())
            frame_no += 1

    if cap:
        cap.release()
    log.info("Capture thread stopped.")

# ---- HTTP handler -----------------------------------------------------------

BOUNDARY = b"--frame"

class MJPEGHandler(BaseHTTPRequestHandler):

    def log_message(self, fmt, *args):
        # Only log new connections, not every frame request
        if "/snap" in self.path or self.path == "/":
            pass  # suppress per-request noise
        else:
            super().log_message(fmt, *args)

    def do_GET(self):
        if self.path == "/" or self.path == "/stream":
            self._stream_mjpeg()
        elif self.path == "/snap":
            self._send_snapshot()
        elif self.path == "/status":
            self._send_status()
        else:
            self.send_response(404)
            self.end_headers()

    def _stream_mjpeg(self):
        """Stream MJPEG frames continuously."""
        client = f"{self.client_address[0]}:{self.client_address[1]}"
        log.info("Client connected: %s", client)

        self.send_response(200)
        self.send_header("Content-Type",
                         "multipart/x-mixed-replace; boundary=frame")
        self.send_header("Cache-Control", "no-cache")
        self.send_header("X-Framerate", "target")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()

        last_ts  = 0.0
        frames_sent = 0

        try:
            while True:
                jpg, ts = _buf.get()
                if jpg is None or ts == last_ts:
                    time.sleep(0.01)
                    continue
                last_ts = ts

                header = (
                    b"\r\n" + BOUNDARY + b"\r\n"
                    b"Content-Type: image/jpeg\r\n"
                    b"Content-Length: " + str(len(jpg)).encode() + b"\r\n"
                    b"\r\n"
                )
                try:
                    self.wfile.write(header + jpg)
                    self.wfile.flush()
                    frames_sent += 1
                except (BrokenPipeError, ConnectionResetError):
                    break

        except Exception as e:
            log.debug("Client %s disconnected: %s", client, e)
        finally:
            log.info("Client %s disconnected. Sent %d frames.", client, frames_sent)

    def _send_snapshot(self):
        """Return a single JPEG snapshot."""
        jpg, _ = _buf.get()
        if jpg is None:
            self.send_response(503)
            self.end_headers()
            return
        self.send_response(200)
        self.send_header("Content-Type", "image/jpeg")
        self.send_header("Content-Length", str(len(jpg)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(jpg)

    def _send_status(self):
        """Return JSON status."""
        import json
        status = {
            "frames_captured": _buf.count,
            "server": "NEMO_SENSE stream_server",
            "time": time.strftime("%H:%M:%S"),
        }
        body = json.dumps(status).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

# ---- Helpers ----------------------------------------------------------------

def get_local_ip() -> str:
    """Get the WiFi/LAN IP address of this device."""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"

# ---- Entry point ------------------------------------------------------------

def main():
    ap = argparse.ArgumentParser(description="NEMO_SENSE Webcam Stream Server")
    ap.add_argument("--camera",  type=int,   default=0,   help="Camera index (default 0)")
    ap.add_argument("--port",    type=int,   default=8080, help="HTTP port (default 8080)")
    ap.add_argument("--width",   type=int,   default=320,  help="Frame width (default 320)")
    ap.add_argument("--height",  type=int,   default=240,  help="Frame height (default 240)")
    ap.add_argument("--fps",     type=int,   default=12,   help="Target capture FPS (default 12)")
    ap.add_argument("--quality", type=int,   default=70,   help="JPEG quality 1-100 (default 70)")
    ap.add_argument("--bind",    type=str,   default="0.0.0.0", help="Bind address")
    args = ap.parse_args()

    local_ip = get_local_ip()

    print("")
    print(" +---------------------------------------------------------+")
    print(" |  NEMO_SENSE -- Webcam Stream Server                     |")
    print(" |  Running on Arduino UNO Q (Debian Linux)                |")
    print(" +---------------------------------------------------------+")
    print(f" Camera    : index {args.camera}  ({args.width}x{args.height} @ {args.fps}fps)")
    print(f" JPEG      : quality {args.quality}%")
    print(f" Stream URL: http://{local_ip}:{args.port}/")
    print(f" Snapshot  : http://{local_ip}:{args.port}/snap")
    print(f" Status    : http://{local_ip}:{args.port}/status")
    print("")
    print(" On the PC run:")
    print(f"   python nemo_demo.py --stream http://{local_ip}:{args.port}/")
    print("")
    print(" Press Ctrl+C to stop.")
    print("")

    # Start capture thread
    stop_event = threading.Event()
    t = threading.Thread(
        target=capture_loop,
        args=(args.camera, args.width, args.height, args.fps, args.quality, stop_event),
        daemon=True,
    )
    t.start()

    # Wait for first frame
    log.info("Waiting for first frame...")
    for _ in range(30):
        if _buf.count > 0:
            break
        time.sleep(0.1)
    if _buf.count == 0:
        log.warning("No frames yet -- starting server anyway")

    # Start HTTP server
    server = ThreadingHTTPServer((args.bind, args.port), MJPEGHandler)
    log.info("Server listening on %s:%d", args.bind, args.port)

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down...")
    finally:
        stop_event.set()
        server.shutdown()
        log.info("Done.")

if __name__ == "__main__":
    main()
