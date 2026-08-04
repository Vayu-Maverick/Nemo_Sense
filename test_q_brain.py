import sys
import types
import json

# Mock out cv2, serial, and bluetooth for the test
mock_cv2 = types.ModuleType("cv2")
mock_cv2.dnn = types.ModuleType("dnn")
mock_cv2.VideoCapture = lambda x: None
sys.modules["cv2"] = mock_cv2

mock_serial = types.ModuleType("serial")
sys.modules["serial"] = mock_serial

mock_socket = types.ModuleType("socket")
sys.modules["socket"] = mock_socket

# Now import the logic
import q_brain
import numpy as np

print("--- Running GuideSense Mock Test ---")

# Mock the MotorController
class MockMotorController:
    def __init__(self, port, baud):
        self.port = port
        self.baud = baud
    def connect(self):
        print(f"[MCU] Connected to Mock MCU on {self.port}")
    def send_command(self, left, right):
        print(f"[MCU] Motor Command: L={left}, R={right}")
    def stop(self):
        print("[MCU] Motor Stopped")

q_brain.MotorController = MockMotorController

# Mock the Bluetooth Server
class MockBluetoothServer:
    def __init__(self):
        self.latest_command = None
    def start(self):
        print("[BT] Mock BT Server Started")
        self.running = True
        self.client_sock = True # Fake socket
    def send_message(self, msg_dict):
        print(f"[BT] Sent to Phone: {json.dumps(msg_dict)}")

q_brain.BluetoothServer = MockBluetoothServer

# Mock VisionSystem
class MockVisionSystem:
    def __init__(self, model_path):
        print(f"[Vision] Loaded model {model_path}")
    def detect(self, frame):
        # Fake returning an obstacle on the left, but far away
        return [{"zone": "left", "proximity": 0.2}]

q_brain.VisionSystem = MockVisionSystem

# We don't actually want the main loop to run forever, so we simulate the logic
motor = q_brain.MotorController('COM1', 9600)
motor.connect()

bt = q_brain.BluetoothServer()
bt.start()

vision = MockVisionSystem("dummy.onnx")

print("\n--- Simulation Step 1: Navigating without close obstacles ---")
bt.latest_command = {"type": "command", "action": "navigate"}

# Run the logic that would be inside the while loop
cmd = bt.latest_command
bt.latest_command = None
navigating = True
if cmd and cmd.get("action") == "navigate":
    bt.send_message({"type": "speak", "text": "Starting navigation."})

obstacles = vision.detect(np.zeros((640,640,3)))
closest = max(obstacles, key=lambda x: x['proximity'])

if closest['proximity'] > q_brain.DANGER_DISTANCE:
    motor.stop()
    bt.send_message({"type": "speak", "text": "Obstacle very close. Please wait."})
else:
    print("[Logic] Path clear. Moving forward.")
    motor.send_command(150, 150)

print("\n--- Simulation Step 2: Obstacle gets too close! ---")
# Manually trigger a close obstacle
obstacles = [{"zone": "center", "proximity": 0.8}] # 0.8 > DANGER_DISTANCE (0.5)
closest = max(obstacles, key=lambda x: x['proximity'])

if closest['proximity'] > q_brain.DANGER_DISTANCE:
    print("[Logic] Obstacle detected above danger threshold!")
    motor.stop()
    bt.send_message({"type": "speak", "text": "Obstacle very close. Please wait."})
else:
    motor.send_command(150, 150)

print("\n--- Simulation Step 3: Stop Command from Phone ---")
bt.latest_command = {"type": "command", "action": "stop"}
cmd = bt.latest_command
if cmd and cmd.get("action") == "stop":
    navigating = False
    motor.stop()
    bt.send_message({"type": "speak", "text": "Stopping."})

print("\n--- Test Complete ---")
