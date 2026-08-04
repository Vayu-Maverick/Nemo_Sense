import subprocess

candidates = [
    '172.16.2.201', '172.16.3.114', '172.16.3.112', '172.16.4.137', 
    '172.16.6.16', '172.16.6.179', '172.16.6.210', '172.16.7.113'
]

found_arduino = None

for ip in candidates:
    print(f"Testing {ip}...")
    try:
        # BatchMode=yes prevents prompt for password
        res = subprocess.run(
            ["ssh", "-o", "ConnectTimeout=2", "-o", "StrictHostKeyChecking=no", "-o", "BatchMode=yes", f"root@{ip}", "uname -a"],
            capture_output=True,
            text=True,
            timeout=3
        )
        if res.returncode == 0:
            output = res.stdout.lower()
            print(f"Connected to {ip}: {res.stdout.strip()}")
            if "debian" in output or "dragonwing" in output or "arduino" in output or "linux" in output:
                print(f"Found Arduino Q on {ip}!")
                found_arduino = ip
                break
    except Exception as e:
        print(f"Error testing {ip}: {e}")

if found_arduino:
    print(f"\nSUCCESS: Arduino Q is at {found_arduino}")
else:
    print("\nCould not connect to any candidates using passwordless SSH (SSH keys).")
    print("If your Arduino requires a password, please specify it or type it when prompted.")
