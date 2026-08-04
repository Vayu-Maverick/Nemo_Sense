import sys

ino_path = r'C:\Users\Admin\.gemini\antigravity\scratch\netra\arduino\motor_controller\motor_controller.ino'
with open(ino_path, 'r', encoding='utf-8') as f:
    content = f.read()

# Replace header
old_header = "#include <Arduino_RouterBridge.h>"
new_header = """// ---------------------------------------------------------
// HARDWARE SELECTOR
// Set IS_UNO_Q_SBC to 1 if using the Arduino UNO Q (Linux).
// Set IS_UNO_Q_SBC to 0 if using a standard Arduino (Uno, Nano) over USB.
// ---------------------------------------------------------
#define IS_UNO_Q_SBC 0

#if IS_UNO_Q_SBC
#include <Arduino_RouterBridge.h>
#else
// Standard Arduino uses Hardware Serial for communication
#endif"""
content = content.replace(old_header, new_header)

# Replace bridge definition
old_bridge = "static RouterBridgeClass& bridge = RouterBridge;"
new_bridge = """#if IS_UNO_Q_SBC
static RouterBridgeClass& bridge = RouterBridge;
#else
#define bridge Serial
#endif"""
content = content.replace(old_bridge, new_bridge)

# Replace bridge.begin()
old_begin = "    bridge.begin();"
new_begin = """#if IS_UNO_Q_SBC
    bridge.begin();
#else
    bridge.begin(115200); // Standard serial baud rate matching Python config
#endif"""
content = content.replace(old_begin, new_begin)

with open(ino_path, 'w', encoding='utf-8') as f:
    f.write(content)

print("Updated motor_controller.ino successfully.")
