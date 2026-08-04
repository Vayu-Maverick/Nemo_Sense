"""
test_wifi_sensing.py — Tests for WiFi sensing and sensor fusion.

Usage:
    python test_wifi_sensing.py              # all tests with simulated data
    python test_wifi_sensing.py --live       # live test with hardware
"""

from __future__ import annotations

import math
import sys
import os
import time
import unittest

# Add the python package directory to the import path
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "python"))

from wifi_sensing import (
    SimpleKalman,
    WiFiMeasurement,
    WiFiNode,
    WiFiSensingEngine,
    WiFiSensingResult,
)
from sensor_fusion import (
    FusedObstacle,
    FusedResult,
    SensorFusion,
    SurroundingsMap,
)
from vision import ObstacleInfo, VisionResult


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_engine_with_nodes() -> WiFiSensingEngine:
    """Create an engine with all 3 standard nodes registered."""
    engine = WiFiSensingEngine()
    engine.register_node("rover", "rover", "AA:BB:CC:DD:EE:01")
    engine.register_node("phone", "phone", "AA:BB:CC:DD:EE:02")
    engine.register_node("router", "router", "AA:BB:CC:DD:EE:03")
    return engine


def _make_vision_result(
    obstacles: list[ObstacleInfo] | None = None,
    source: str = "simulated",
) -> VisionResult:
    """Build a VisionResult with optional obstacles."""
    result = VisionResult(source=source)
    if obstacles:
        for obs in obstacles:
            result.obstacles.append(obs)
            if obs.distance_m < result.zone_min_dist[obs.zone]:
                result.zone_min_dist[obs.zone] = obs.distance_m
            if obs.distance_m < result.closest_distance:
                result.closest_distance = obs.distance_m
    return result


def _make_wifi_result(
    zone_presence: dict | None = None,
    zone_distance: dict | None = None,
    signal_quality: float = 0.8,
    obstacle_detected: bool = False,
) -> WiFiSensingResult:
    """Build a WiFiSensingResult from scratch."""
    return WiFiSensingResult(
        zone_presence=zone_presence or {"left": 0.0, "center": 0.0, "right": 0.0},
        zone_distance=zone_distance or {
            "left": float("inf"),
            "center": float("inf"),
            "right": float("inf"),
        },
        signal_quality=signal_quality,
        obstacle_detected=obstacle_detected,
    )


# ---------------------------------------------------------------------------
# Test cases
# ---------------------------------------------------------------------------

class TestRSSIToDistance(unittest.TestCase):
    """1. Verify log-distance path-loss model conversion."""

    def test_at_reference(self):
        """At reference RSSI, distance should be ~1 metre."""
        dist = WiFiSensingEngine._rssi_to_distance(
            rssi=-40.0, reference_rssi=-40.0, path_loss_exp=2.7,
        )
        self.assertAlmostEqual(dist, 1.0, places=1)

    def test_weaker_signal_farther(self):
        """Weaker RSSI → greater distance."""
        near = WiFiSensingEngine._rssi_to_distance(-45.0, -40.0, 2.7)
        far = WiFiSensingEngine._rssi_to_distance(-60.0, -40.0, 2.7)
        self.assertGreater(far, near)

    def test_stronger_signal_closer(self):
        """Stronger RSSI → shorter distance."""
        dist = WiFiSensingEngine._rssi_to_distance(-30.0, -40.0, 2.7)
        self.assertLess(dist, 1.0)

    def test_extreme_clamp(self):
        """Very weak signal should be clamped to max distance."""
        dist = WiFiSensingEngine._rssi_to_distance(-100.0, -40.0, 2.7)
        self.assertLessEqual(dist, 50.0)


class TestKalmanFilter(unittest.TestCase):
    """2. Verify Kalman filter convergence."""

    def test_converges_to_constant(self):
        """Constant measurements should converge the estimate to that value."""
        kf = SimpleKalman(process_noise=0.1, measurement_noise=1.0, initial_estimate=0.0)
        for _ in range(50):
            est = kf.update(5.0)
        self.assertAlmostEqual(est, 5.0, delta=0.1)

    def test_smooths_noise(self):
        """Noisy measurements around a mean should produce a stable estimate."""
        import random
        random.seed(42)
        kf = SimpleKalman(process_noise=0.05, measurement_noise=2.0, initial_estimate=3.0)
        estimates = []
        for _ in range(100):
            noisy = 3.0 + random.gauss(0, 0.5)
            est = kf.update(noisy)
            estimates.append(est)
        # Final estimate should be near 3.0
        self.assertAlmostEqual(estimates[-1], 3.0, delta=0.3)
        # Variance of latter half should be smaller than raw noise
        latter = estimates[50:]
        var = sum((e - 3.0) ** 2 for e in latter) / len(latter)
        self.assertLess(var, 0.25)  # raw variance = 0.25


class TestShadowFadeDetection(unittest.TestCase):
    """3. Verify obstacle detection from RSSI drops."""

    def test_no_fade(self):
        """No drop → no obstacle."""
        self.assertFalse(
            WiFiSensingEngine._detect_shadow_fade(-40.0, -40.0, 6.0)
        )

    def test_small_fade_below_threshold(self):
        """Small drop below threshold → no obstacle."""
        self.assertFalse(
            WiFiSensingEngine._detect_shadow_fade(-44.0, -40.0, 6.0)
        )

    def test_fade_above_threshold(self):
        """Drop exceeding threshold → obstacle detected."""
        self.assertTrue(
            WiFiSensingEngine._detect_shadow_fade(-50.0, -40.0, 6.0)
        )

    def test_signal_stronger_than_baseline(self):
        """Signal stronger than baseline → no obstacle."""
        self.assertFalse(
            WiFiSensingEngine._detect_shadow_fade(-35.0, -40.0, 6.0)
        )


class TestTriangulation(unittest.TestCase):
    """4. Verify zone mapping from multi-node data."""

    def test_zone_assignment(self):
        """Measurements should map to correct zones based on node pair."""
        engine = _make_engine_with_nodes()
        # Manually set baselines
        engine._baseline_rssi = {
            engine._pair_key("phone", "router"): -40.0,
            engine._pair_key("rover", "router"): -40.0,
            engine._pair_key("phone", "rover"): -40.0,
        }
        engine._calibrated = True

        now = time.time()
        # Strong fade on rover↔router → center zone obstacle
        engine.add_measurement(WiFiMeasurement("rover", "router", -55.0, 2412, now))
        # No fade on phone↔router
        engine.add_measurement(WiFiMeasurement("phone", "router", -42.0, 2412, now))

        result = engine.process()
        # Center should have highest presence (big fade on rover↔router)
        self.assertGreater(result.zone_presence["center"], result.zone_presence["left"])
        self.assertTrue(result.obstacle_detected)

    def test_all_zones_quiet(self):
        """No significant fades → no obstacle presence."""
        engine = _make_engine_with_nodes()
        now = time.time()
        engine.add_measurement(WiFiMeasurement("rover", "router", -41.0, 2412, now))
        engine.add_measurement(WiFiMeasurement("phone", "router", -41.0, 2412, now))
        engine.add_measurement(WiFiMeasurement("phone", "rover", -41.0, 2412, now))
        engine.calibrate_baseline(duration_s=10.0)

        result = engine.process()
        for zone in ("left", "center", "right"):
            self.assertLess(result.zone_presence[zone], 0.3)


class TestSensorFusionBothAgree(unittest.TestCase):
    """5. Vision + WiFi both see obstacle → high confidence."""

    def test_fused_high_confidence(self):
        fusion = SensorFusion(vision_weight=0.7, wifi_weight=0.3)

        vision = _make_vision_result(obstacles=[
            ObstacleInfo("person", 0.85, 1.2, "center", (100, 50, 200, 300)),
        ])
        wifi = _make_wifi_result(
            zone_presence={"left": 0.1, "center": 0.8, "right": 0.1},
            zone_distance={"left": 5.0, "center": 1.5, "right": 5.0},
            signal_quality=0.9,
            obstacle_detected=True,
        )

        result = fusion.fuse(vision, wifi)
        self.assertTrue(len(result.obstacles) >= 1)
        center_obs = [o for o in result.obstacles if o.zone == "center"]
        self.assertTrue(len(center_obs) >= 1)
        self.assertEqual(center_obs[0].source, "fused")
        self.assertGreater(center_obs[0].confidence, 0.8)
        self.assertGreater(center_obs[0].depth_confidence, 0.7)


class TestSensorFusionVisionOnly(unittest.TestCase):
    """6. Only vision detects → moderate confidence."""

    def test_vision_only_moderate(self):
        fusion = SensorFusion()

        vision = _make_vision_result(obstacles=[
            ObstacleInfo("chair", 0.75, 2.0, "right", (220, 100, 300, 280)),
        ])
        wifi = _make_wifi_result()  # all zones clear

        result = fusion.fuse(vision, wifi)
        right_obs = [o for o in result.obstacles if o.zone == "right"]
        self.assertEqual(len(right_obs), 1)
        self.assertEqual(right_obs[0].source, "vision")
        # Confidence should be reduced compared to raw vision
        self.assertLess(right_obs[0].confidence, 0.75)


class TestSensorFusionWiFiOnly(unittest.TestCase):
    """7. Only WiFi detects → reports unknown obstacle."""

    def test_wifi_only_unknown(self):
        fusion = SensorFusion()

        vision = _make_vision_result()  # no detections
        wifi = _make_wifi_result(
            zone_presence={"left": 0.7, "center": 0.1, "right": 0.0},
            zone_distance={"left": 2.5, "center": float("inf"), "right": float("inf")},
            signal_quality=0.8,
            obstacle_detected=True,
        )

        result = fusion.fuse(vision, wifi)
        wifi_obs = [o for o in result.obstacles if o.source == "wifi"]
        self.assertTrue(len(wifi_obs) >= 1)
        self.assertEqual(wifi_obs[0].label, "unknown_obstacle")
        self.assertEqual(wifi_obs[0].zone, "left")
        self.assertAlmostEqual(wifi_obs[0].distance_m, 2.5, delta=0.1)


class TestSensorFusionDisagree(unittest.TestCase):
    """8. Take conservative (closer) distance when sensors disagree."""

    def test_takes_closer_distance(self):
        fusion = SensorFusion(vision_weight=0.7, wifi_weight=0.3)

        vision = _make_vision_result(obstacles=[
            ObstacleInfo("person", 0.8, 3.0, "center", (100, 50, 200, 300)),
        ])
        # WiFi says something is much closer in center
        wifi = _make_wifi_result(
            zone_presence={"left": 0.0, "center": 0.6, "right": 0.0},
            zone_distance={"left": float("inf"), "center": 1.0, "right": float("inf")},
            signal_quality=0.7,
            obstacle_detected=True,
        )

        result = fusion.fuse(vision, wifi)
        center_obs = [o for o in result.obstacles if o.zone == "center"]
        self.assertTrue(len(center_obs) >= 1)
        # Fused distance should be ≤ the closer of the two (WiFi says 1.0)
        # Weighted: 0.7*3.0 + 0.3*1.0 = 2.4, but clamped to min(2.4, min(3.0,1.0)) = 1.0
        self.assertLessEqual(result.zone_min_dist["center"], 1.0)


class TestSurroundingsMap(unittest.TestCase):
    """9. Verify grid generation from SurroundingsMap."""

    def test_initial_grid_empty(self):
        smap = SurroundingsMap(size=8, cell_size_m=0.5)
        self.assertEqual(smap.grid.shape, (8, 8))
        self.assertAlmostEqual(smap.grid.sum(), 0.0)

    def test_vision_updates_grid(self):
        smap = SurroundingsMap(size=8, cell_size_m=0.5)
        vision = _make_vision_result(obstacles=[
            ObstacleInfo("person", 0.9, 1.0, "center", (100, 50, 200, 300)),
        ])
        smap.update_from_vision(vision)
        self.assertGreater(smap.grid.sum(), 0.0)

    def test_ascii_render(self):
        smap = SurroundingsMap(size=8, cell_size_m=0.5)
        ascii_out = smap.render_ascii()
        lines = ascii_out.split("\n")
        self.assertEqual(len(lines), 8)
        # Rover marker should be present
        self.assertIn("R", ascii_out)

    def test_zone_summary_empty(self):
        smap = SurroundingsMap(size=8, cell_size_m=0.5)
        summary = smap.get_zone_summary()
        for zone in ("left", "center", "right"):
            self.assertEqual(summary[zone], float("inf"))


class TestOccupancyGrid(unittest.TestCase):
    """10. Verify 8×8 grid from RSSI data."""

    def test_grid_dimensions(self):
        """Occupancy grid should be 8×8."""
        engine = _make_engine_with_nodes()
        now = time.time()
        engine.add_measurement(WiFiMeasurement("rover", "router", -55.0, 2412, now))
        engine.calibrate_baseline(duration_s=0.0)
        # Re-add with a fade to populate the grid
        engine.add_measurement(WiFiMeasurement("rover", "router", -55.0, 2412, time.time()))

        result = engine.process()
        self.assertEqual(len(result.surroundings_rssi_map), 8)
        for row in result.surroundings_rssi_map:
            self.assertEqual(len(row), 8)

    def test_grid_has_occupancy_on_fade(self):
        """A strong fade should produce non-zero occupancy somewhere."""
        engine = _make_engine_with_nodes()
        now = time.time()
        # Baseline with no obstacle
        engine.add_measurement(WiFiMeasurement("rover", "router", -40.0, 2412, now - 1))
        engine.calibrate_baseline(duration_s=10.0)
        # Now add a measurement with a large fade
        engine.add_measurement(WiFiMeasurement("rover", "router", -60.0, 2412, time.time()))

        result = engine.process()
        flat = [cell for row in result.surroundings_rssi_map for cell in row]
        self.assertGreater(max(flat), 0.0, "Grid should have non-zero occupancy after fade")

    def test_no_fade_grid_empty(self):
        """No fade → grid should be all zeros."""
        engine = _make_engine_with_nodes()
        now = time.time()
        engine.add_measurement(WiFiMeasurement("rover", "router", -40.0, 2412, now))
        engine.calibrate_baseline(duration_s=10.0)
        # Same RSSI as baseline
        engine.add_measurement(WiFiMeasurement("rover", "router", -40.0, 2412, time.time()))

        result = engine.process()
        flat = [cell for row in result.surroundings_rssi_map for cell in row]
        self.assertAlmostEqual(sum(flat), 0.0)


# ---------------------------------------------------------------------------
# Runner
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    if "--live" in sys.argv:
        print("Live hardware test not yet implemented — run without --live for unit tests.")
        sys.exit(0)

    unittest.main(verbosity=2)
