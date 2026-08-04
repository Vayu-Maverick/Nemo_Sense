import socket
import threading
import subprocess
import re

# Determine local IP
def get_local_ip():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(('8.8.8.8', 80))
        ip = s.getsockname()[0]
    except Exception:
        ip = '127.0.0.1'
    finally:
        s.close()
    return ip

local_ip = get_local_ip()
print(f"Local PC IP: {local_ip}")

# Parse subnet (e.g. 172.16.7.227 -> 172.16.7.0/24 or broader 172.16.2.0/24)
# We will scan the 172.16.0.0 to 172.16.15.254 range since it's a /22 or /19 network
ip_parts = list(map(int, local_ip.split('.')))

open_hosts = []

def scan_port(ip):
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(0.5)
        result = s.connect_ex((ip, 22))
        if result == 0:
            print(f"Found SSH open on {ip}")
            open_hosts.append(ip)
        s.close()
    except Exception:
        pass

threads = []
# We will scan subnets 172.16.0.x to 172.16.10.x to cover likely DHCP ranges
for subnet in range(0, 11):
    for host in range(1, 255):
        ip = f"172.16.{subnet}.{host}"
        t = threading.Thread(target=scan_port, args=(ip,))
        t.start()
        threads.append(t)
        if len(threads) >= 100:
            for thread in threads:
                thread.join()
            threads = []

for thread in threads:
    thread.join()

print("Scan complete.")
print("Hosts with open SSH (port 22):", open_hosts)
