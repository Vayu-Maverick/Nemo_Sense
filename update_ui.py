import sys
import re

vision_path = r'C:\Users\Admin\.gemini\antigravity\scratch\netra\python\vision.py'
with open(vision_path, 'r', encoding='utf-8') as f:
    v_content = f.read()

# Add frame to VisionResult
if "frame: Optional[np.ndarray] = None" not in v_content:
    v_content = v_content.replace(
"""    frame_time_ms: float = 0.0
    source: str = "unknown"             # "webcam" | "ble_phone" | "simulated\"""",
"""    frame_time_ms: float = 0.0
    source: str = "unknown"             # "webcam" | "ble_phone" | "simulated"
    frame: Optional[np.ndarray] = None"""
    )

# Assign frame in process_frame
if "result.frame = frame.copy()" not in v_content:
    v_content = v_content.replace(
"""        result.source = source
        orig_h, orig_w = frame.shape[:2]""",
"""        result.source = source
        result.frame = frame.copy()
        orig_h, orig_w = frame.shape[:2]"""
    )

with open(vision_path, 'w', encoding='utf-8') as f:
    f.write(v_content)

lidar_path = r'C:\Users\Admin\.gemini\antigravity\scratch\netra\python\lidar_map.py'
with open(lidar_path, 'r', encoding='utf-8') as f:
    l_content = f.read()

old_imshow = """        # Show image
        cv2.imshow(self.window_name, img)
        cv2.waitKey(1)"""

new_imshow = """        # Show image
        cv2.imshow(self.window_name, img)
        
        # Also show camera feed if available
        if vision_result is not None and hasattr(vision_result, 'frame') and vision_result.frame is not None:
            cam_img = vision_result.frame.copy()
            # Draw bounding boxes
            if hasattr(vision_result, 'obstacles'):
                for obs in vision_result.obstacles:
                    x1, y1, x2, y2 = obs.bbox
                    cv2.rectangle(cam_img, (x1, y1), (x2, y2), (0, 0, 255), 2)
                    label_text = f"{obs.label} {obs.distance_m:.1f}m"
                    cv2.putText(cam_img, label_text, (x1, y1 - 5), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 255), 2)
            cv2.imshow("Camera Feed", cam_img)
            
        cv2.waitKey(1)"""

if old_imshow in l_content:
    l_content = l_content.replace(old_imshow, new_imshow)
    with open(lidar_path, 'w', encoding='utf-8') as f:
        f.write(l_content)
        
print("Updated UI successfully!")
