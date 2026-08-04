"""
motor_link.py — L9110S Motor Driver interface for Netra Rover.

Communicates with the STM32 co-processor via the arduino-router Unix socket
using MsgPack RPC (the correct protocol for Arduino_RouterBridge).

RPC calls:
    drive(cmd: int) → int
        0 = STOP
        1 = FORWARD
        2 = BACK
        3 = LEFT  (pivot left)
        4 = RIGHT (pivot right)

    ping() → int   (returns 1, used as heartbeat)

Hardware: L9110S-4 dual H-bridge
    Left motors (1+2) : D2=IA, D3=IB
    Right motors (3+4): D4=IA, D5=IB
"""

from __future__ import annotations

import logging
import socket
import struct
import time
from typing import Optional

logger = logging.getLogger("netra.motor")

# ── Drive command constants ───────────────────────────────────────────────────
CMD_STOP    = 0
CMD_FORWARD = 1
CMD_BACK    = 2
CMD_LEFT    = 3
CMD_RIGHT   = 4

# ── arduino-router Unix socket ────────────────────────────────────────────────
ROUTER_SOCK = "/var/run/arduino-router.sock"
CALL_TIMEOUT = 1.0   # seconds to wait for RPC response


class MotorLink:
    """
    Sends drive commands to the L9110S motor driver via arduino-router RPC.

    The arduino-router exposes the STM32 Bridge as a Unix domain socket
    using MsgPack-encoded RPC arrays:
        Request:  [method_name: str, arg1, arg2, ...]
        Response: [result]
    """

    def __init__(self, sock_path: str = ROUTER_SOCK):
        self._sock_path = sock_path
        self._sock: Optional[socket.socket] = None
        self._last_cmd = CMD_STOP
        self._connected = False

    # ── Connection ─────────────────────────────────────────────────────────────
    def open(self) -> bool:
        try:
            self._sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            self._sock.settimeout(CALL_TIMEOUT)
            self._sock.connect(self._sock_path)
            self._connected = True
            logger.info("Motor link open via %s", self._sock_path)
            # Heartbeat check
            result = self._rpc("ping")
            if result == 1:
                logger.info("STM32 ping OK — L9110S motor driver ready")
            else:
                logger.warning("STM32 ping returned unexpected value: %s", result)
            return True
        except Exception as exc:
            logger.error("Cannot open motor link: %s", exc)
            self._sock = None
            self._connected = False
            return False

    def close(self):
        self.stop()
        if self._sock:
            try:
                self._sock.close()
            except Exception:
                pass
            self._sock = None
        self._connected = False
        logger.info("Motor link closed")

    @property
    def is_open(self) -> bool:
        return self._connected and self._sock is not None

    # ── Drive commands (high-level) ────────────────────────────────────────────
    def stop(self):
        self._drive(CMD_STOP)

    def forward(self):
        self._drive(CMD_FORWARD)

    def back(self):
        self._drive(CMD_BACK)

    def left(self):
        self._drive(CMD_LEFT)

    def right(self):
        self._drive(CMD_RIGHT)

    def send_motor(self, left: int, right: int):
        """
        Compatibility shim for old code that passed left/right PWM values.
        Maps differential values to the 4-command drive system.
        """
        if left == 0 and right == 0:
            self._drive(CMD_STOP)
        elif left > 0 and right > 0:
            self._drive(CMD_FORWARD)
        elif left < 0 and right < 0:
            self._drive(CMD_BACK)
        elif left < 0 and right > 0:
            self._drive(CMD_LEFT)
        elif left > 0 and right < 0:
            self._drive(CMD_RIGHT)
        else:
            self._drive(CMD_STOP)

    def ping(self) -> bool:
        """Returns True if STM32 responds to ping."""
        try:
            return self._rpc("ping") == 1
        except Exception:
            return False

    # ── Internal ───────────────────────────────────────────────────────────────
    def _drive(self, cmd: int):
        if self._last_cmd == cmd:
            return  # Avoid redundant sends
        try:
            self._rpc("drive", cmd)
            self._last_cmd = cmd
        except Exception as exc:
            logger.warning("Drive command %d failed: %s", cmd, exc)
            self._connected = False

    def _rpc(self, method: str, *args):
        """
        Send a MsgPack RPC call over the Unix socket and return the result.

        MsgPack array format:  [method_name, arg1, arg2, ...]
        We use a minimal hand-coded MsgPack encoder to avoid a heavy dependency.
        """
        if self._sock is None:
            raise ConnectionError("Motor link not connected")

        payload = _msgpack_encode([method] + list(args))
        self._sock.sendall(payload)

        # Read response (MsgPack array with one element)
        data = b""
        deadline = time.time() + CALL_TIMEOUT
        while time.time() < deadline:
            try:
                chunk = self._sock.recv(64)
                if chunk:
                    data += chunk
                    # Try to decode — success means we have a complete response
                    try:
                        result = _msgpack_decode(data)
                        if isinstance(result, list) and len(result) > 0:
                            return result[0]
                        return result
                    except Exception:
                        continue  # Need more data
            except socket.timeout:
                break

        raise TimeoutError(f"No RPC response for '{method}' within {CALL_TIMEOUT}s")


# ── Minimal MsgPack encoder/decoder ──────────────────────────────────────────
# Handles only what arduino-router needs: arrays of str/int

def _msgpack_encode(obj) -> bytes:
    """Encode a Python list to MsgPack bytes."""
    if isinstance(obj, list):
        n = len(obj)
        if n <= 15:
            header = bytes([0x90 | n])
        else:
            header = struct.pack(">BH", 0xdc, n)
        return header + b"".join(_msgpack_encode(item) for item in obj)
    elif isinstance(obj, str):
        b = obj.encode("utf-8")
        n = len(b)
        if n <= 31:
            return bytes([0xa0 | n]) + b
        elif n <= 0xFF:
            return struct.pack(">BB", 0xd9, n) + b
        else:
            return struct.pack(">BH", 0xda, n) + b
    elif isinstance(obj, bool):
        return bytes([0xc3 if obj else 0xc2])
    elif isinstance(obj, int):
        if 0 <= obj <= 127:
            return bytes([obj])
        elif -32 <= obj < 0:
            return bytes([0xe0 | (obj + 32)])
        elif 0 <= obj <= 0xFF:
            return struct.pack(">BB", 0xcc, obj)
        elif obj < 0:
            return struct.pack(">Bb", 0xd0, obj)
        else:
            return struct.pack(">Bi", 0xd2, obj)
    elif obj is None:
        return bytes([0xc0])
    else:
        raise TypeError(f"Cannot MsgPack-encode type {type(obj)}")


def _msgpack_decode(data: bytes):
    """Decode MsgPack bytes to a Python object (arrays and scalars only)."""
    val, _ = _decode_one(data, 0)
    return val


def _decode_one(data: bytes, pos: int):
    b = data[pos]
    pos += 1

    # Positive fixint
    if b <= 0x7f:
        return b, pos
    # Negative fixint
    if b >= 0xe0:
        return b - 256, pos
    # fixarray
    if 0x90 <= b <= 0x9f:
        n = b & 0x0f
        return _decode_array(data, pos, n)
    # fixstr
    if 0xa0 <= b <= 0xbf:
        n = b & 0x1f
        return data[pos:pos+n].decode("utf-8"), pos + n
    # nil
    if b == 0xc0:
        return None, pos
    # bool
    if b == 0xc2:
        return False, pos
    if b == 0xc3:
        return True, pos
    # uint8
    if b == 0xcc:
        return data[pos], pos + 1
    # int8
    if b == 0xd0:
        return struct.unpack_from(">b", data, pos)[0], pos + 1
    # int32
    if b == 0xd2:
        return struct.unpack_from(">i", data, pos)[0], pos + 4
    # str8
    if b == 0xd9:
        n = data[pos]; pos += 1
        return data[pos:pos+n].decode("utf-8"), pos + n
    # array16
    if b == 0xdc:
        n = struct.unpack_from(">H", data, pos)[0]; pos += 2
        return _decode_array(data, pos, n)
    raise ValueError(f"Unsupported MsgPack byte 0x{b:02x} at pos {pos-1}")


def _decode_array(data: bytes, pos: int, n: int):
    result = []
    for _ in range(n):
        item, pos = _decode_one(data, pos)
        result.append(item)
    return result, pos
