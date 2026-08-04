import sys

file_path = r'C:\Users\Admin\.gemini\antigravity\scratch\netra\python\main.py'
with open(file_path, 'r', encoding='utf-8') as f:
    content = f.read()

# 1. Imports
content = content.replace(
"""if WIFI_SENSING_ENABLED:
    from wifi_sensing import WiFiSensingEngine, WiFiMeasurement
    from sensor_fusion import SensorFusion, FusedResult""",
"""if WIFI_SENSING_ENABLED:
    from wifi_sensing import WiFiSensingEngine, WiFiMeasurement
    from sensor_fusion import SensorFusion, FusedResult
    from lidar_map import LidarMapRenderer"""
)

# 2. Init variables
content = content.replace(
"""        self.wifi_engine: Optional[WiFiSensingEngine] = None  # type: ignore
        self.sensor_fusion: Optional[SensorFusion] = None  # type: ignore""",
"""        self.wifi_engine: Optional[WiFiSensingEngine] = None  # type: ignore
        self.sensor_fusion: Optional[SensorFusion] = None  # type: ignore
        self.lidar_renderer = None
        self._sim_gps = (0.0, 0.0)
        self._sim_heading = 0.0"""
)

# 3. Init objects
content = content.replace(
"""                from wifi_sensing import WiFiSensingEngine
                from sensor_fusion import SensorFusion
                self.wifi_engine = WiFiSensingEngine()
                self.wifi_engine.register_node("rover", "rover", "")
                self.wifi_engine.register_node("phone", "phone", "")
                self.wifi_engine.register_node("router", "router", "")
                self.sensor_fusion = SensorFusion()
                logger.info("WiFi sensing engine initialised (3-node)")""",
"""                from wifi_sensing import WiFiSensingEngine
                from sensor_fusion import SensorFusion
                from lidar_map import LidarMapRenderer
                self.wifi_engine = WiFiSensingEngine()
                self.wifi_engine.register_node("rover", "rover", "")
                self.wifi_engine.register_node("phone", "phone", "")
                self.wifi_engine.register_node("router", "router", "")
                self.sensor_fusion = SensorFusion()
                self.lidar_renderer = LidarMapRenderer()
                logger.info("WiFi sensing engine & LIDAR initialised (3-node)")"""
)

# 4. Main loop init (Hardcoded route)
content = content.replace(
"""        # ── Main control loop ─────────────────────────────────────────────
        logger.info("Entering main loop (Ctrl+C to exit)")
        cycle = 0
        status_interval = 5  # send BT status every N cycles""",
"""        # ── Main control loop ─────────────────────────────────────────────
        logger.info("Entering main loop (Ctrl+C to exit)")
        cycle = 0
        status_interval = 5  # send BT status every N cycles
        
        # Hardcoded North -> East Navigation
        if self.navigator is not None:
            self.navigator.set_route([
                {"lat": 0.0, "lng": 0.0},
                {"lat": 0.001, "lng": 0.0}, # North
                {"lat": 0.001, "lng": 0.001} # East
            ], [])
            self.state = STATE_NAVIGATING
            logger.info("Hardcoded Route: North -> East set")"""
)

# 5. Disable phone sensor GPS and simulate GPS
content = content.replace(
"""            # ── B. Sensor data from phone ─────────────────────────────────
            sensor = None
            if self.bt is not None:
                sensor = self.bt.get_latest_sensor_data()

            current_gps = None
            current_heading = 0.0
            accel_data = None

            if sensor is not None:
                gps_d = sensor.get("gps")
                if gps_d:
                    current_gps = (gps_d.get("lat", 0.0), gps_d.get("lng", 0.0))
                current_heading = sensor.get("heading", 0.0)
                accel_data = sensor.get("accel")""",
"""            # ── B. Sensor data from phone ─────────────────────────────────
            sensor = None
            if self.bt is not None:
                sensor = self.bt.get_latest_sensor_data()

            # Ignore phone GPS; use simulated GPS to enforce hardcoded route
            current_gps = self._sim_gps
            current_heading = self._sim_heading
            accel_data = None

            if sensor is not None:
                accel_data = sensor.get("accel")
                
            # Simulate movement if navigating
            if self.state == STATE_NAVIGATING:
                lat, lng = current_gps
                if current_heading < 45 or current_heading > 315:
                    lat += 0.00001
                elif 45 <= current_heading <= 135:
                    lng += 0.00001
                self._sim_gps = (lat, lng)"""
)

# 6. Render LIDAR map
content = content.replace(
"""            # ── D. Micro navigation (override) ────────────────────────────
            micro_cmd = MicroNavCommand()
            if self.micro_nav is not None:
                if fused_result is not None:
                    micro_cmd = self.micro_nav.update_fused(fused_result)
                else:
                    micro_cmd = self.micro_nav.update(vr)
                # Speak obstacle warnings
                if micro_cmd.speak_text and self.bt:
                    self.bt.send_speak(micro_cmd.speak_text)""",
"""            # ── D. Micro navigation (override) ────────────────────────────
            micro_cmd = MicroNavCommand()
            if self.micro_nav is not None:
                if fused_result is not None:
                    micro_cmd = self.micro_nav.update_fused(fused_result)
                else:
                    micro_cmd = self.micro_nav.update(vr)
                # Speak obstacle warnings
                if micro_cmd.speak_text and self.bt:
                    self.bt.send_speak(micro_cmd.speak_text)
                    
            if self.lidar_renderer is not None:
                try:
                    self.lidar_renderer.render(fused_result, micro_cmd.action)
                except Exception as e:
                    logger.error("LIDAR render error: %s", e)"""
)

# 7. Ignore BT navigate commands
content = content.replace(
"""            if action == "navigate":
                waypoints = msg.get("waypoints", [])
                instructions = msg.get("instructions", [])
                destination = msg.get("destination", "destination")
                if self.navigator and waypoints:
                    self.navigator.set_route(waypoints, instructions)
                    self.state = STATE_NAVIGATING
                    logger.info("State → navigating to '%s'", destination)
                    self.bt.send_speak(f"Navigating to {destination}.")
                    self.bt.send_state_change(STATE_NAVIGATING)
                else:
                    self.bt.send_speak("No route available.")""",
"""            if action == "navigate":
                # Ignore phone navigate commands to enforce hardcoded route
                if self.bt:
                    self.bt.send_speak("Phone navigation ignored. Hardcoded North-East route active.")
                logger.info("Ignored phone navigation command.")"""
)

with open(file_path, 'w', encoding='utf-8') as f:
    f.write(content)

print("Updated main.py successfully!")
