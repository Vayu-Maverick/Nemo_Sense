"""
test_motors.py — Tests motor control via Arduino_RouterBridge RPC protocol.

The arduino-router exposes the STM32 RPC functions over a Unix socket at:
  /var/run/arduino-router.sock

We call the 'motor' RPC function directly using msgpack.
"""
import socket
import struct
import time
import sys
import os

# arduino-router listens on a Unix domain socket
SOCKET_PATH = "/var/run/arduino-router.sock"

def pack_rpc_call(method: str, *args):
    """Pack a msgpack RPC call: [type=0, msgid, method, args]"""
    import msgpack
    msg_id = int(time.time() * 1000) % 65535
    return msgpack.packb([0, msg_id, method, list(args)], use_bin_type=True)

def send_rpc(sock, method: str, *args):
    """Send an RPC call and read the response."""
    import msgpack
    data = pack_rpc_call(method, *args)
    sock.sendall(data)
    time.sleep(0.1)
    try:
        resp = sock.recv(4096)
        if resp:
            unpacked = msgpack.unpackb(resp, raw=False)
            return unpacked
    except Exception:
        pass
    return None

def connect_socket():
    """Connect to arduino-router unix socket."""
    sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    sock.settimeout(3.0)
    sock.connect(SOCKET_PATH)
    return sock

def run_test():
    print("=" * 55)
    print("  Nemo~Sense Motor Test (RouterBridge RPC)")
    print("=" * 55)

    print(f"\nConnecting to arduino-router at {SOCKET_PATH} ...")
    try:
        sock = connect_socket()
        print("Connected!")
    except Exception as e:
        print(f"FAILED: {e}")
        print("\nIs the arduino-router service running?")
        print("Check: systemctl status arduino-router")
        sys.exit(1)

    # Ping first
    print("\n[1] PING ...")
    resp = send_rpc(sock, "ping")
    print(f"    Response: {resp}")

    start = time.time()
    duration = 120  # 2 minutes
    cycle = 1

    print(f"\n[2] Starting 2-minute motor test...\n")

    while (time.time() - start) < duration:
        remaining = int(duration - (time.time() - start))
        print(f"[Cycle {cycle}] {remaining}s remaining")

        print("  -> FORWARD (left=1, right=1)")
        send_rpc(sock, "motor", 1, 1)
        time.sleep(2)

        print("  -> RIGHT (left=1, right=0)")
        send_rpc(sock, "motor", 1, 0)
        time.sleep(2)

        print("  -> LEFT (left=0, right=1)")
        send_rpc(sock, "motor", 0, 1)
        time.sleep(2)

        print("  -> STOP")
        send_rpc(sock, "stop_motors")
        time.sleep(1)

        cycle += 1

    print("\nTest complete. Stopping motors.")
    send_rpc(sock, "stop_motors")
    sock.close()

if __name__ == "__main__":
    try:
        import msgpack
    except ImportError:
        print("Installing msgpack...")
        os.system(f"{sys.executable} -m pip install msgpack")
        import msgpack
    run_test()
