from __future__ import annotations
import cv2
import time

print('Attempting to power on and open the webcam...')

# Open the default camera (index 0)
cap = cv2.VideoCapture(0)

if cap.isOpened():
    print('SUCCESS: Webcam is powered and open! The camera light should be ON.')
    print('Keeping the script alive so the camera stays powered. Press Ctrl+C to exit.')
    
    try:
        while True:
            # We just grab frames to keep the camera active, but don''t do any AI
            ret, frame = cap.read()
            if not ret:
                print('Lost connection to the webcam.')
                break
            time.sleep(0.1) # small delay to reduce CPU usage
    except KeyboardInterrupt:
        print('\nStopping...')
else:
    print('FAILED: Could not open the webcam. Check the USB connection and power.')

# Release the camera when done
cap.release()
print('Webcam powered off.')
