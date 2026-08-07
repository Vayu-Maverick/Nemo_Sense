from __future__ import annotations
import cv2
import time
import logging
import sys

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("webcam_power_test")

CAMERA_WIDTH = 320
CAMERA_HEIGHT = 320
CAMERA_FPS = 10

def open_camera():
    """Scan and open the webcam, similar to vision.py."""
    logger.info("Scanning for USB Webcam to deliver power and keep active...")
    for index in range(6):
        try:
            # Try V4L2 first (optimised for Linux)
            cap = cv2.VideoCapture(index, cv2.CAP_V4L2)
            if not cap.isOpened():
                # Fallback to default
                cap = cv2.VideoCapture(index)
                
            if cap.isOpened():
                ret, _ = cap.read()
                if ret:
                    cap.set(cv2.CAP_PROP_FRAME_WIDTH, CAMERA_WIDTH)
                    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, CAMERA_HEIGHT)
                    cap.set(cv2.CAP_PROP_FPS, CAMERA_FPS)
                    logger.info("Camera %d opened successfully. Power delivered.", index)
                    return cap
                cap.release()
        except Exception as e:
            logger.debug("Failed to open camera %d: %s", index, e)
            
    logger.error("No working camera found.")
    return None

def main():
    cap = open_camera()
    if cap is None:
        sys.exit(1)
        
    logger.info("Starting continuous capture loop to keep USB port active. Press Ctrl+C to stop.")
    
    frames_captured = 0
    start_time = time.time()
    last_log_time = start_time
    
    try:
        while True:
            ret, frame = cap.read()
            if not ret:
                logger.error("Failed to read frame! Camera might have disconnected or lost power.")
                break
                
            frames_captured += 1
            current_time = time.time()
            
            # Print a heartbeat every 5 seconds
            if current_time - last_log_time >= 5.0:
                fps = frames_captured / (current_time - start_time)
                logger.info("Webcam is ACTIVE and POWERED. Captured %d frames so far. (Avg %.1f FPS)", frames_captured, fps)
                last_log_time = current_time
                
            # Sleep a tiny bit to prevent 100% CPU usage, keeping it close to the target FPS
            time.sleep(1.0 / (CAMERA_FPS * 2))
            
    except KeyboardInterrupt:
        logger.info("Stopping webcam power test...")
    finally:
        cap.release()
        logger.info("Webcam released.")

if __name__ == "__main__":
    main()
