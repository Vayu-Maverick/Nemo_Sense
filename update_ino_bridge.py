import sys

ino_path = r'C:\Users\Admin\.gemini\antigravity\scratch\netra\arduino\motor_controller\motor_controller.ino'
with open(ino_path, 'r', encoding='utf-8') as f:
    content = f.read()

# The compiler says RouterBridgeClass is wrong and suggests BridgeClass. 
# The global object is Bridge.
old_bridge = """#if IS_UNO_Q_SBC
static RouterBridgeClass& bridge = RouterBridge;
#else
#define bridge Serial
#endif"""

new_bridge = """#if IS_UNO_Q_SBC
// The library exposes 'Bridge' of type 'BridgeClass'
#define bridge Bridge
#else
#define bridge Serial
#endif"""

content = content.replace(old_bridge, new_bridge)

with open(ino_path, 'w', encoding='utf-8') as f:
    f.write(content)

print("Fixed BridgeClass typo in motor_controller.ino")
