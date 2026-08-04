#!/usr/bin/env python3
"""
test_gps.py — NEO-6M GPS Test Script via arduino-router RPC
Netra Blind Guide Rover

The NEO-6M is connected to the STM32 co-processor via SoftwareSerial:
    D12 = RX  (NEO-6M TX → Arduino D12)
    D13 = TX  (Arduino D13 → NEO-6M RX, optional)

The STM32 reads NMEA sentences and exposes them via Bridge RPC:
    gps_nmea() → latest NMEA sentence string

This script calls gps_nmea() repeatedly and parses the result.

Usage:
    python3 test_gps.py              # 30 second test
    python3 test_gps.py --duration 60
    python3 test_gps.py --raw        # print all raw NMEA sentences
"""

import argparse
import socket
import struct
import sys
import time

try:
    import pynmea2
except ImportError:
    print("[ERROR] pynmea2 not installed. Run: pip3 install pynmea2")
    sys.exit(1)

# ── Colours ────────────────────────────────────────────────────────────────────
GREEN  = "\033[92m"
YELLOW = "\033[93m"
RED    = "\033[91m"
CYAN   = "\033[96m"
RESET  = "\033[0m"

ROUTER_SOCK = "/var/run/arduino-router.sock"
CALL_TIMEOUT = 2.0


# ── Minimal MsgPack encoder/decoder (no extra dependencies) ───────────────────

def _msgpack_encode(obj) -> bytes:
    if isinstance(obj, list):
        n = len(obj)
        header = bytes([0x90 | n]) if n <= 15 else struct.pack(">BH", 0xdc, n)
        return header + b"".join(_msgpack_encode(i) for i in obj)
    elif isinstance(obj, str):
        b = obj.encode("utf-8")
        n = len(b)
        if n <= 31:   return bytes([0xa0 | n]) + b
        elif n <= 255: return struct.pack(">BB", 0xd9, n) + b
        else:          return struct.pack(">BH", 0xda, n) + b
    elif isinstance(obj, bool):
        return bytes([0xc3 if obj else 0xc2])
    elif isinstance(obj, int):
        if 0 <= obj <= 127:   return bytes([obj])
        elif -32 <= obj < 0:  return bytes([0xe0 | (obj + 32)])
        elif obj <= 0xFF:     return struct.pack(">BB", 0xcc, obj)
        else:                 return struct.pack(">Bi", 0xd2, obj)
    elif obj is None:
        return bytes([0xc0])
    raise TypeError(f"Cannot encode {type(obj)}")


def _decode_one(data: bytes, pos: int):
    b = data[pos]; pos += 1
    if b <= 0x7f:            return b, pos
    if b >= 0xe0:            return b - 256, pos
    if 0x90 <= b <= 0x9f:
        n = b & 0x0f
        arr = []; 
        for _ in range(n): 
            v, pos = _decode_one(data, pos); arr.append(v)
        return arr, pos
    if 0xa0 <= b <= 0xbf:
        n = b & 0x1f; return data[pos:pos+n].decode("utf-8"), pos+n
    if b == 0xc0:  return None, pos
    if b == 0xc2:  return False, pos
    if b == 0xc3:  return True, pos
    if b == 0xcc:  return data[pos], pos+1
    if b == 0xd0:  return struct.unpack_from(">b", data, pos)[0], pos+1
    if b == 0xd2:  return struct.unpack_from(">i", data, pos)[0], pos+4
    if b == 0xd9:  n=data[pos]; pos+=1; return data[pos:pos+n].decode("utf-8"), pos+n
    if b == 0xdc:  n=struct.unpack_from(">H",data,pos)[0]; pos+=2
    raise ValueError(f"Unknown MsgPack byte 0x{b:02x}")


def rpc_call(sock: socket.socket, method: str, *args):
    """Send RPC call and return result."""
    payload = _msgpack_encode([method] + list(args))
    sock.sendall(payload)

    data = b""
    deadline = time.time() + CALL_TIMEOUT
    while time.time() < deadline:
        try:
            chunk = sock.recv(256)
            if chunk:
                data += chunk
                try:
                    result, _ = _decode_one(data, 0)
                    if isinstance(result, list) and result:
                        return result[0]
                    return result
                except Exception:
                    continue
        except socket.timeout:
            break
    raise TimeoutError(f"No response for '{method}'")


# ── Main test ─────────────────────────────────────────────────────────────────

def test_gps(duration: int = 30, show_raw: bool = False):
    print(f"\n{CYAN}{'='*55}{RESET}")
    print(f"{CYAN}  NEO-6M GPS Test — D12(RX) D13(TX){RESET}")
    print(f"{CYAN}{'='*55}{RESET}")
    print(f"  Socket   : {ROUTER_SOCK}")
    print(f"  Duration : {duration}s")
    print(f"{CYAN}{'='*55}{RESET}\n")

    # Connect to arduino-router
    try:
        sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        sock.settimeout(CALL_TIMEOUT)
        sock.connect(ROUTER_SOCK)
        print(f"{GREEN}[OK] Connected to arduino-router{RESET}")
    except Exception as e:
        print(f"{RED}[FAIL] Cannot connect to arduino-router: {e}{RESET}")
        print(f"       Is the Arduino UNO Q powered and the motor app running?")
        return False

    # Ping STM32
    try:
        r = rpc_call(sock, "ping")
        if r == 1:
            print(f"{GREEN}[OK] STM32 ping OK{RESET}\n")
        else:
            print(f"{YELLOW}[WARN] Unexpected ping result: {r}{RESET}\n")
    except Exception as e:
        print(f"{RED}[FAIL] STM32 not responding: {e}{RESET}")
        sock.close()
        return False

    stats = {
        "polls": 0, "sentences": 0, "errors": 0,
        "gga": 0,   "rmc": 0,      "fix": False,
        "lat": None, "lon": None, "alt": None,
        "sats": None, "hdop": None, "speed_kmh": None,
        "last_sentence": "",
    }

    print(f"Polling gps_nmea() every 500ms for {duration}s...\n")
    print(f"{'─'*55}")

    start = time.time()
    prev_sentence = ""

    try:
        while (time.time() - start) < duration:
            stats["polls"] += 1
            try:
                sentence = rpc_call(sock, "gps_nmea")

                # Skip if empty or same as last (GPS updates at 1 Hz)
                if not sentence or sentence == prev_sentence:
                    time.sleep(0.5)
                    continue

                prev_sentence = sentence
                stats["sentences"] += 1
                stats["last_sentence"] = sentence

                if show_raw:
                    print(f"  RAW: {sentence}")

                # Parse NMEA
                try:
                    msg = pynmea2.parse(sentence.strip())

                    if isinstance(msg, pynmea2.GGA):
                        stats["gga"] += 1
                        qual = int(msg.gps_qual) if msg.gps_qual else 0
                        if qual > 0:
                            stats["fix"]  = True
                            stats["lat"]  = msg.latitude
                            stats["lon"]  = msg.longitude
                            stats["alt"]  = msg.altitude
                            stats["sats"] = msg.num_sats
                            stats["hdop"] = msg.horizontal_dil
                            print(
                                f"{GREEN}[GGA ✓] Lat={msg.latitude:.6f}° "
                                f"Lon={msg.longitude:.6f}° "
                                f"Alt={msg.altitude}m "
                                f"Sats={msg.num_sats}{RESET}"
                            )
                        else:
                            print(f"{YELLOW}[GGA] No fix (quality={qual}){RESET}")

                    elif isinstance(msg, pynmea2.RMC):
                        stats["rmc"] += 1
                        if msg.status == "A":
                            spd = float(msg.spd_over_grnd or 0) * 1.852
                            stats["speed_kmh"] = spd
                            print(
                                f"{GREEN}[RMC ✓] Active "
                                f"Speed={spd:.2f} km/h "
                                f"Course={msg.true_course}°{RESET}"
                            )
                        else:
                            print(f"{YELLOW}[RMC] Void — no fix yet{RESET}")

                except pynmea2.ParseError as e:
                    stats["errors"] += 1
                    if show_raw:
                        print(f"{YELLOW}  Parse error: {e}{RESET}")

            except TimeoutError:
                print(f"{YELLOW}  [TIMEOUT] gps_nmea() took too long{RESET}")
            except Exception as e:
                print(f"{RED}  [ERROR] {e}{RESET}")

            time.sleep(0.5)

    except KeyboardInterrupt:
        print(f"\n{YELLOW}Interrupted.{RESET}")
    finally:
        sock.close()

    # ── Summary ──────────────────────────────────────────────────────────────
    print(f"\n{'─'*55}")
    print(f"{CYAN}GPS Test Summary:{RESET}")
    print(f"  Polls made          : {stats['polls']}")
    print(f"  Unique sentences    : {stats['sentences']}")
    print(f"  Parse errors        : {stats['errors']}")
    print(f"  GGA sentences       : {stats['gga']}")
    print(f"  RMC sentences       : {stats['rmc']}")

    if stats["fix"]:
        print(f"\n{GREEN}  ✓ GPS FIX OBTAINED!{RESET}")
        print(f"  Latitude   : {stats['lat']:.6f}°")
        print(f"  Longitude  : {stats['lon']:.6f}°")
        if stats["alt"]:  print(f"  Altitude   : {stats['alt']} m")
        if stats["sats"]: print(f"  Satellites : {stats['sats']}")
        if stats["hdop"]: print(f"  HDOP       : {stats['hdop']}")
        if stats["speed_kmh"] is not None:
            print(f"  Speed      : {stats['speed_kmh']:.2f} km/h")
    elif stats["sentences"] > 0:
        print(f"\n{YELLOW}  ⚠ Receiving NMEA data but no GPS fix yet.{RESET}")
        print(f"     → Move the antenna near a window or outdoors.")
        print(f"     → Last sentence: {stats['last_sentence']}")
    else:
        print(f"\n{RED}  ✗ No NMEA sentences received.{RESET}")
        print(f"     → Check D12(RX) wired to NEO-6M TX")
        print(f"     → Verify NEO-6M is powered (VCC=3.3V/5V, GND)")
        print(f"     → Confirm motor app is running: arduino-app-cli app list")

    print(f"{'─'*55}\n")
    return stats["fix"] or stats["sentences"] > 0


def main():
    parser = argparse.ArgumentParser(description="NEO-6M GPS Test via arduino-router RPC")
    parser.add_argument("--duration", type=int, default=30, help="Test duration in seconds")
    parser.add_argument("--raw", action="store_true", help="Print raw NMEA sentences")
    args = parser.parse_args()

    success = test_gps(args.duration, args.raw)
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
