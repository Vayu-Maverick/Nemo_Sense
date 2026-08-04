import cv2
import numpy as np

class LidarMapRenderer:
    def __init__(self, window_name="Netra LIDAR/CAD Map", width=512, height=512):
        self.window_name = window_name
        self.width = width
        self.height = height
        
        # Grid parameters
        self.grid_size = 8 # 8x8 grid
        self.cell_w = self.width // self.grid_size
        self.cell_h = self.height // self.grid_size
        
    def render(self, vision_result, motor_action="none"):
        # Create a black background image
        img = np.zeros((self.height, self.width, 3), dtype=np.uint8)
        
        # Rover position at bottom center
        rover_x = self.width // 2
        rover_y = self.height - 30

        # Draw Camera Field of View (FOV) cone (approx 60 degrees)
        fov_left = int(rover_x - np.tan(np.radians(30)) * self.height)
        fov_right = int(rover_x + np.tan(np.radians(30)) * self.height)
        cone_pts = np.array([
            [rover_x, rover_y],
            [fov_left, 0],
            [fov_right, 0]
        ], np.int32)
        cv2.fillPoly(img, [cone_pts], (20, 20, 30))
        cv2.polylines(img, [cone_pts], True, (50, 50, 80), 2)

        # Draw grid lines inside the FOV for depth reference (every 1 meter up to 4 meters)
        for d in range(1, 5):
            y_line = self.height - int((d / 4.0) * self.height)
            cv2.line(img, (0, y_line), (self.width, y_line), (50, 50, 50), 1)
            cv2.putText(img, f"{d}m", (10, y_line - 5), cv2.FONT_HERSHEY_SIMPLEX, 0.4, (100, 100, 100), 1)

        # Draw Vision obstacles
        if vision_result is not None and hasattr(vision_result, 'obstacles'):
            for obs in vision_result.obstacles:
                # Map distance (max 4m on map)
                dist_m = min(obs.distance_m, 4.0)
                y = self.height - int((dist_m / 4.0) * self.height)
                
                # Map zone to X within the cone
                # At distance y, the cone width is:
                cone_width_at_y = 2 * (rover_y - y) * np.tan(np.radians(30))
                
                if obs.zone == "left":
                    x = int(rover_x - cone_width_at_y * 0.3)
                elif obs.zone == "right":
                    x = int(rover_x + cone_width_at_y * 0.3)
                else: # center
                    x = rover_x
                    
                cv2.circle(img, (x, max(20, y)), 15, (0, 0, 255), -1)
                cv2.putText(img, f"{obs.label} ({obs.distance_m:.1f}m)", (x + 20, max(20, y)), 
                            cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 255), 1)

        # Draw Rover
        cv2.circle(img, (rover_x, rover_y), 20, (0, 255, 0), -1)
        cv2.putText(img, "CAMERA", (rover_x - 30, rover_y + 40), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 2)
        
        # Draw current decision Action
        cv2.putText(img, f"ACTION: {motor_action.upper()}", (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 1.0, (255, 255, 255), 2)
        
        # Output the image
        try:
            cv2.imshow(self.window_name, img)
            cv2.waitKey(1)
        except Exception as e:
            # Running on a headless device without a display (like autonomous robot mode)
            pass
        
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
            try:
                cv2.imshow("Camera Feed", cam_img)
                cv2.waitKey(1)
            except Exception:
                pass
