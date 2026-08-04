import sys

ino_path = r'C:\Users\Admin\.gemini\antigravity\scratch\netra\arduino\motor_controller\motor_controller.ino'
with open(ino_path, 'r', encoding='utf-8') as f:
    content = f.read()

# Replace the hardcoded hardware selector with an automatic one
old_selector = """// ---------------------------------------------------------
// HARDWARE SELECTOR
// Set IS_UNO_Q_SBC to 1 if using the Arduino UNO Q (Linux).
// Set IS_UNO_Q_SBC to 0 if using a standard Arduino (Uno, Nano) over USB.
// ---------------------------------------------------------
#define IS_UNO_Q_SBC 0"""

new_selector = """// ---------------------------------------------------------
// HARDWARE SELECTOR (Auto-Detect)
// Automatically uses RouterBridge for UNO Q, and Serial for standard Arduinos
// ---------------------------------------------------------
#ifdef ARDUINO_UNO_Q
  #define IS_UNO_Q_SBC 1
#else
  #define IS_UNO_Q_SBC 0
#endif"""

content = content.replace(old_selector, new_selector)

with open(ino_path, 'w', encoding='utf-8') as f:
    f.write(content)

print("Updated motor_controller.ino to auto-detect the Arduino board.")
