import sys

vision_path = r'C:\Users\Admin\.gemini\antigravity\scratch\netra\python\vision.py'
with open(vision_path, 'r', encoding='utf-8') as f:
    content = f.read()

old_open = """    def _open_camera(self):
        \"\"\"Try USB webcam (incl. USB hub), fall back to simulator.\"\"\"
        cap = _scan_for_webcam(max_index=0)
        if cap is not None:
            self._cap = cap
            self._simulated = False
        else:
            self._cap = SimulatedCamera(CAMERA_WIDTH, CAMERA_HEIGHT, CAMERA_FPS)
            self._simulated = True"""

new_open = """    def _open_camera(self):
        \"\"\"Try USB webcam (incl. USB hub), fall back to simulator.\"\"\"
        # FORCING SIMULATED CAMERA because Windows camera drivers are hanging!
        logger.warning("Forcing simulated camera to avoid Windows driver hang.")
        self._cap = SimulatedCamera(CAMERA_WIDTH, CAMERA_HEIGHT, CAMERA_FPS)
        self._simulated = True"""

if old_open in content:
    content = content.replace(old_open, new_open)
    with open(vision_path, 'w', encoding='utf-8') as f:
        f.write(content)
    print("Forced simulated camera successfully!")
else:
    print("Could not find the target code to replace.")
