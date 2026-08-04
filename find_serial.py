import subprocess, time

# Quick non-blocking test — just check if port opens and reads anything
ports = ["/dev/ttyHS1", "/dev/ttyGS0", "/dev/ttyMSM0", "/dev/ttyS1", "/dev/ttyS0"]

for p in ports:
    try:
        # Use stty to set baud without hanging
        r = subprocess.run(["stty", "-F", p, "115200", "raw"], capture_output=True, timeout=2)
        if r.returncode == 0:
            print(f"{p} -> OPENED OK (baud set)")
        else:
            err = r.stderr.decode().strip()
            print(f"{p} -> stty error: {err}")
    except Exception as e:
        print(f"{p} -> {e}")
