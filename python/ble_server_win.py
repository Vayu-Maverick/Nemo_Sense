"""
ble_server_win.py — Windows BLE GATT Server for Netra Guide Rover.

Advertises a custom BLE GATT service that the GuideSense Android app connects to.
Uses the `bleak` library (Windows-native WinRT backend).

GATT Service UUID: 12345678-1234-5678-1234-56789abcdef0
Characteristics:
  - FRAME_CHAR   (Write): Phone → Rover  base64 JPEG frames
  - SENSOR_CHAR  (Write): Phone → Rover  JSON sensor data (GPS, heading, accel)
  - COMMAND_CHAR (Write): Phone → Rover  JSON commands (navigate, stop, etc.)
  - SPEAK_CHAR   (Notify): Rover → Phone  TTS text to speak

Usage (as a library):
    server = BLEServer(on_frame=cb, on_sensor=cb, on_command=cb)
    server.run()   # blocking — run in a background thread
    server.stop()
"""

from __future__ import annotations

import asyncio
import base64
import json
import logging
import threading
from typing import Callable, Optional

import numpy as np
import cv2

logger = logging.getLogger("netra.ble")

# ── GATT UUIDs ────────────────────────────────────────────────────────────
SERVICE_UUID  = "12345678-1234-5678-1234-56789abcdef0"
FRAME_CHAR    = "12345678-1234-5678-1234-56789abcdef1"  # Write (camera)
SENSOR_CHAR   = "12345678-1234-5678-1234-56789abcdef2"  # Write (GPS/IMU)
COMMAND_CHAR  = "12345678-1234-5678-1234-56789abcdef3"  # Write (commands)
SPEAK_CHAR    = "12345678-1234-5678-1234-56789abcdef4"  # Notify (TTS)


class BLEServer:
    """
    BLE GATT peripheral server.

    Callbacks are called from the asyncio event loop — keep them fast or
    dispatch to a thread pool.
    """

    def __init__(
        self,
        on_frame:   Optional[Callable[[np.ndarray], None]] = None,
        on_sensor:  Optional[Callable[[dict], None]] = None,
        on_command: Optional[Callable[[dict], None]] = None,
    ):
        self._on_frame   = on_frame
        self._on_sensor  = on_sensor
        self._on_command = on_command
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._running = False
        self._connected_device = None
        self._speak_queue: asyncio.Queue = asyncio.Queue()

    # ── Public API ────────────────────────────────────────────────────────

    def run(self):
        """Start the BLE server (blocking call — run in a thread)."""
        try:
            from bleak import BleakServer  # type: ignore
            _has_server = True
        except ImportError:
            _has_server = False

        if not _has_server:
            logger.warning(
                "BleakServer not available on this version of bleak. "
                "Using simulated BLE mode (data-only, no real BLE advertising)."
            )
            self._run_simulated()
            return

        self._loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self._loop)
        self._running = True
        try:
            self._loop.run_until_complete(self._run_server())
        except Exception as exc:
            logger.error("BLE server error: %s", exc)
        finally:
            self._running = False

    def stop(self):
        self._running = False
        if self._loop and self._loop.is_running():
            self._loop.call_soon_threadsafe(self._loop.stop)

    def send_speak(self, text: str):
        """Queue a TTS message to send to the phone."""
        if self._loop and self._loop.is_running():
            asyncio.run_coroutine_threadsafe(
                self._speak_queue.put(text), self._loop
            )

    # ── BLE GATT server ───────────────────────────────────────────────────

    async def _run_server(self):
        """Run the BLE GATT peripheral. Uses bleak's server API."""
        try:
            from bleak import BleakServer
            from bleak.backends.characteristic import BleakGATTCharacteristic

            def write_handler(characteristic: BleakGATTCharacteristic,
                               data: bytearray):
                uuid = str(characteristic.uuid).lower()
                self._dispatch(uuid, bytes(data))

            async with BleakServer(
                name="NetraGuide",
                services=[SERVICE_UUID],
                # Write characteristics
                characteristics={
                    FRAME_CHAR:   {"properties": ["write"], "callback": write_handler},
                    SENSOR_CHAR:  {"properties": ["write"], "callback": write_handler},
                    COMMAND_CHAR: {"properties": ["write"], "callback": write_handler},
                    SPEAK_CHAR:   {"properties": ["notify", "read"]},
                },
            ) as server:
                logger.info("BLE GATT server running — advertising as 'NetraGuide'")
                while self._running:
                    await asyncio.sleep(1.0)

        except Exception as exc:
            logger.warning("BleakServer start failed (%s). Running in log-only mode.", exc)
            while self._running:
                await asyncio.sleep(1.0)

    def _dispatch(self, uuid: str, data: bytes):
        """Route incoming BLE write to the correct callback."""
        try:
            if uuid == FRAME_CHAR:
                # Expect raw JPEG bytes or base64-encoded JPEG
                try:
                    img_bytes = data
                    np_arr = np.frombuffer(img_bytes, np.uint8)
                    frame = cv2.imdecode(np_arr, cv2.IMREAD_COLOR)
                    if frame is None:
                        # Try base64 decode
                        img_bytes = base64.b64decode(data)
                        np_arr = np.frombuffer(img_bytes, np.uint8)
                        frame = cv2.imdecode(np_arr, cv2.IMREAD_COLOR)
                    if frame is not None and self._on_frame:
                        self._on_frame(frame)
                except Exception as e:
                    logger.debug("Frame decode error: %s", e)

            elif uuid == SENSOR_CHAR:
                msg = json.loads(data.decode("utf-8"))
                logger.debug("BLE sensor: %s", msg)
                if self._on_sensor:
                    self._on_sensor(msg)

            elif uuid == COMMAND_CHAR:
                msg = json.loads(data.decode("utf-8"))
                logger.info("BLE command: %s", msg)
                if self._on_command:
                    self._on_command(msg)

        except Exception as exc:
            logger.warning("BLE dispatch error: %s", exc)

    def _run_simulated(self):
        """Fallback: run without real BLE, just log messages."""
        logger.info("BLE running in simulated mode — no phone connection needed.")
        self._running = True
        while self._running:
            import time
            time.sleep(1.0)
