import sys

ino_path = r'C:\Users\Admin\.gemini\antigravity\scratch\netra\arduino\motor_controller\motor_controller.ino'
with open(ino_path, 'r', encoding='utf-8') as f:
    content = f.read()

# Remove the whole hardware selector and just use Serial
new_header = """// ---------------------------------------------------------
// HARDWARE SELECTOR (Auto-Detect)
// We use standard Hardware Serial (Serial) for all boards,
// as the Python script sends raw text (MOTOR:left,right) via USB CDC.
// ---------------------------------------------------------
#define bridge Serial
"""

# Find where the old header starts
start_idx = content.find("// ---------------------------------------------------------")
if start_idx != -1:
    end_idx = content.find("#endif", start_idx)
    if end_idx != -1:
        # Also find the next #endif (because I added two of them)
        end_idx2 = content.find("#endif", end_idx + 6)
        if end_idx2 != -1:
            content = content[:start_idx] + new_header + content[end_idx2 + 6:]

# Just in case, ensure bridge is used correctly or replace bridge. with Serial.
content = content.replace("bridge.", "Serial.")

with open(ino_path, 'w', encoding='utf-8') as f:
    f.write(content)

print("Cleaned up motor_controller.ino to use pure Serial.")
