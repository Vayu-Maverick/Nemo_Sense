import sys

file_path = r'C:\Users\Admin\.gemini\antigravity\scratch\netra\python\main.py'
with open(file_path, 'r', encoding='utf-8') as f:
    content = f.read()

# Replace the Lidar map render call
old_render = """            if self.lidar_renderer is not None:
                try:
                    self.lidar_renderer.render(fused_result, micro_cmd.action)
                except Exception as e:
                    logger.error("LIDAR render error: %s", e)"""

new_render = """            if self.lidar_renderer is not None:
                try:
                    # Pass vr (VisionResult) instead of fused_result since WiFi is disabled
                    self.lidar_renderer.render(vr, micro_cmd.action)
                except Exception as e:
                    logger.error("LIDAR render error: %s", e)"""

content = content.replace(old_render, new_render)

with open(file_path, 'w', encoding='utf-8') as f:
    f.write(content)

print("Updated main.py LIDAR render call successfully.")
