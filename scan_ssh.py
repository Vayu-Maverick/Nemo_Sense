import paramiko
import sys

candidates = [
    '172.16.2.201', '172.16.3.114', '172.16.3.112', '172.16.4.137', 
    '172.16.6.16', '172.16.6.179', '172.16.6.210', '172.16.7.113'
]

password = "Physics@2799"
found = None

print("Scanning for Arduino UNO Q via SSH...")
for ip in candidates:
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    try:
        client.connect(ip, username="root", password=password, timeout=2.0, banner_timeout=2.0, auth_timeout=2.0)
        stdin, stdout, stderr = client.exec_command("uname -a")
        output = stdout.read().decode('utf-8').lower()
        if "linux" in output or "arduino" in output or "dragonwing" in output:
            print(f"FOUND ARDUINO at {ip}: {output.strip()}")
            found = ip
            client.close()
            break
        client.close()
    except Exception as e:
        pass

if found:
    print(f"TARGET_IP={found}")
    sys.exit(0)
else:
    print("TARGET_IP=NONE")
    sys.exit(1)
