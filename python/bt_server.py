"""
bt_server.py — Bluetooth Classic SPP server for the Netra / GuideSense rover.

The Android companion app connects over RFCOMM and sends:
  - JSON commands  (navigate, stop, resume, set_speed)
  - Base64 JPEG camera frames
  - JSON sensor bundles (GPS, heading, accelerometer)

The rover sends back:
  - {"type": "speak", "text": "..."}           TTS for phone / BLE headphones
  - {"type": "status", ...}                    periodic telemetry
  - {"type": "state", "state": "navigating"}   state changes

Designed for the Arduino UNO Q Linux side (BlueZ / PyBluez).
Falls back to a no-op stub on Windows so development can continue offline.
"""

from __future__ import annotations

import base64
import json
import logging
import queue
import sys
import threading
import time
from typing import Any, Dict, Optional

import cv2
import numpy as np

from config import BT_SPP_UUID, BT_SERVICE_NAME, BT_BACKLOG

logger = logging.getLogger("netra.bt")

# RFCOMM channel used when the UUID bind is unavailable (Linux fallback).
BT_RFCOMM_PORT = 1


class BluetoothServer:
    """Thread-safe Bluetooth SPP server."""

    def __init__(self):
        self._command_queue: queue.Queue = queue.Queue(maxsize=64)
        self._frame_lock = threading.Lock()
        self.latest_frame: Optional[np.ndarray] = None
        self._sensor_lock = threading.Lock()
        self._latest_sensor: Optional[Dict[str, Any]] = None
        self._wifi_lock = threading.Lock()
        self._latest_wifi_data: list = []

        self._client_sock = None
        self._server_sock = None
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._connected = threading.Event()
        self._stub_mode = sys.platform == "win32"

    # ── Lifecycle ─────────────────────────────────────────────────────────

    def start(self):
        """Start the accept/receive thread."""
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(
            target=self._run, daemon=True, name="bt-server"
        )
        self._thread.start()
        logger.info("Bluetooth server starting (stub=%s)", self._stub_mode)

    def stop(self):
        self._running = False
        self._close_client()
        if self._server_sock is not None:
            try:
                self._server_sock.close()
            except Exception:
                pass
            self._server_sock = None
        logger.info("Bluetooth server stopped")

    # ── Public API ────────────────────────────────────────────────────────

    def get_command_queue(self) -> queue.Queue:
        return self._command_queue

    def get_latest_sensor_data(self) -> Optional[Dict[str, Any]]:
        with self._sensor_lock:
            return dict(self._latest_sensor) if self._latest_sensor else None

    def get_latest_wifi_data(self) -> list:
        """Return and clear buffered WiFi scan measurements from the phone."""
        with self._wifi_lock:
            data = list(self._latest_wifi_data)
            self._latest_wifi_data.clear()
            return data

    def send_speak(self, text: str):
        if not text:
            return
        self._send({"type": "speak", "text": text})

    def send_state_change(self, state: str):
        self._send({"type": "state", "state": state})

    def send_status(
        self,
        state: str,
        obstacles: list,
        speed: float,
        next_turn: Optional[dict] = None,
    ):
        payload: Dict[str, Any] = {
            "type": "status",
            "state": state,
            "obstacles": obstacles,
            "speed": round(speed, 2),
        }
        if next_turn is not None:
            payload["next_turn"] = next_turn
        self._send(payload)

    # ── Internal server loop ──────────────────────────────────────────────

    def _run(self):
        if self._stub_mode:
            logger.warning(
                "Windows stub mode — pair the phone with the UNO Q for real BT."
            )
            while self._running:
                time.sleep(0.5)
            return

        try:
            import bluetooth  # type: ignore  # PyBluez on Linux
        except ImportError:
            logger.error(
                "PyBluez not installed. Run: pip install pybluez  "
                "(or apt install python3-bluez on the UNO Q)"
            )
            while self._running:
                time.sleep(1.0)
            return

        try:
            self._server_sock = bluetooth.BluetoothSocket(bluetooth.RFCOMM)
            self._server_sock.bind(("", BT_RFCOMM_PORT))
            self._server_sock.listen(BT_BACKLOG)
            logger.info(
                "Listening for '%s' on RFCOMM channel %d",
                BT_SERVICE_NAME,
                BT_RFCOMM_PORT,
            )
        except Exception as exc:
            logger.error("Cannot bind Bluetooth socket: %s", exc)
            while self._running:
                time.sleep(1.0)
            return

        while self._running:
            try:
                logger.info("Waiting for phone connection …")
                client, info = self._server_sock.accept()
                self._client_sock = client
                self._connected.set()
                logger.info("Phone connected from %s", info)
                self._receive_loop(client)
            except Exception as exc:
                if self._running:
                    logger.warning("Accept error: %s", exc)
            finally:
                self._close_client()
                self._connected.clear()

    def _receive_loop(self, sock):
        buffer = ""
        while self._running:
            try:
                data = sock.recv(4096)
                if not data:
                    break
                buffer += data.decode("utf-8", errors="replace")
                while "\n" in buffer:
                    line, buffer = buffer.split("\n", 1)
                    line = line.strip()
                    if line:
                        self._handle_line(line)
            except Exception as exc:
                logger.debug("Receive ended: %s", exc)
                break
        logger.info("Phone disconnected")

    def _handle_line(self, line: str):
        # Camera frame messages can be large JSON with base64 payload.
        try:
            msg = json.loads(line)
        except json.JSONDecodeError:
            logger.debug("Non-JSON line ignored: %.80s", line)
            return

        msg_type = msg.get("type", "")

        if msg_type == "frame":
            self._handle_frame(msg)
        elif msg_type == "sensor":
            self._handle_sensor(msg)
        elif msg_type == "wifi_scan":
            self._handle_wifi_scan(msg)
        elif msg_type == "command" or "action" in msg:
            self._handle_command(msg)
        else:
            logger.debug("Unknown message type: %s", msg_type)

    def _handle_frame(self, msg: dict):
        b64 = msg.get("data") or msg.get("frame")
        if not b64:
            return
        try:
            raw = base64.b64decode(b64)
            arr = np.frombuffer(raw, dtype=np.uint8)
            frame = cv2.imdecode(arr, cv2.IMREAD_COLOR)
            if frame is not None:
                with self._frame_lock:
                    self.latest_frame = frame
        except Exception as exc:
            logger.warning("Frame decode failed: %s", exc)

    def _handle_sensor(self, msg: dict):
        with self._sensor_lock:
            self._latest_sensor = {
                "gps": msg.get("gps"),
                "heading": msg.get("heading", 0.0),
                "accel": msg.get("accel"),
            }

    def _handle_command(self, msg: dict):
        # Normalise legacy {"type":"command","action":...} format.
        if "action" not in msg and msg.get("type") == "command":
            return
        try:
            self._command_queue.put_nowait(msg)
        except queue.Full:
            logger.warning("Command queue full — dropping message")

    def _handle_wifi_scan(self, msg: dict):
        """Handle WiFi scan results from phone."""
        try:
            from wifi_sensing import WiFiMeasurement
            import time as _time
            scans = msg.get("scans", [])
            measurements = []
            for scan in scans:
                meas = WiFiMeasurement(
                    source_node_id="phone",
                    target_node_id=scan.get("bssid", "unknown"),
                    rssi_dbm=float(scan.get("rssi", -100)),
                    frequency_mhz=int(scan.get("frequency", 2412)),
                    timestamp=_time.time(),
                )
                measurements.append(meas)
            with self._wifi_lock:
                self._latest_wifi_data.extend(measurements)
            logger.debug("Received %d WiFi scan results from phone", len(measurements))
        except Exception as exc:
            logger.warning("WiFi scan parse failed: %s", exc)

    def _send(self, payload: dict):
        if self._client_sock is None:
            return
        try:
            data = (json.dumps(payload) + "\n").encode("utf-8")
            self._client_sock.send(data)
        except Exception as exc:
            logger.debug("Send failed: %s", exc)
            self._close_client()

    def _close_client(self):
        if self._client_sock is not None:
            try:
                self._client_sock.close()
            except Exception:
                pass
            self._client_sock = None
