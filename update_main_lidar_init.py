import sys

file_path = r'C:\Users\Admin\.gemini\antigravity\scratch\netra\python\main.py'
with open(file_path, 'r', encoding='utf-8') as f:
    content = f.read()

# Replace the Lidar init to be independent of WiFi
old_wifi_init = """        # WiFi Sensing — in all modes with vision
        if WIFI_SENSING_ENABLED and self.mode != "motor-test":
            try:
                from wifi_sensing import WiFiSensingEngine
                from sensor_fusion import SensorFusion
                from lidar_map import LidarMapRenderer
                self.wifi_engine = WiFiSensingEngine()
                self.wifi_engine.register_node("rover", "rover", "")
                self.wifi_engine.register_node("phone", "phone", "")
                self.wifi_engine.register_node("router", "router", "")
                self.sensor_fusion = SensorFusion()
                self.lidar_renderer = LidarMapRenderer()
                logger.info("WiFi sensing engine & LIDAR initialised (3-node)")
            except Exception as exc:
                logger.warning("WiFi sensing init failed: %s", exc)
                self.wifi_engine = None
                self.sensor_fusion = None"""

new_wifi_init = """        # WiFi Sensing
        if WIFI_SENSING_ENABLED and self.mode != "motor-test":
            try:
                from wifi_sensing import WiFiSensingEngine
                from sensor_fusion import SensorFusion
                self.wifi_engine = WiFiSensingEngine()
                self.wifi_engine.register_node("rover", "rover", "")
                self.wifi_engine.register_node("phone", "phone", "")
                self.wifi_engine.register_node("router", "router", "")
                self.sensor_fusion = SensorFusion()
                logger.info("WiFi sensing engine initialised")
            except Exception as exc:
                logger.warning("WiFi sensing init failed: %s", exc)
                self.wifi_engine = None
                self.sensor_fusion = None
                
        # Lidar/Top-down Map Renderer — in all modes with vision
        if self.mode != "motor-test":
            try:
                from lidar_map import LidarMapRenderer
                self.lidar_renderer = LidarMapRenderer()
                logger.info("LIDAR/Top-down map initialised")
            except Exception as exc:
                logger.warning("LIDAR renderer init failed: %s", exc)
                self.lidar_renderer = None"""

content = content.replace(old_wifi_init, new_wifi_init)

with open(file_path, 'w', encoding='utf-8') as f:
    f.write(content)

print("Updated main.py LIDAR initialization.")
