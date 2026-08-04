"""
wifi_sensing.py — WiFi RSSI/CSI sensing engine for the Netra Guide Rover.

Uses 3 WiFi nodes (Arduino UNO Q, Phone, Router) to create a radio-frequency
obstacle map. Measures RSSI between nodes to detect signal attenuation caused
by obstacles (people, walls, furniture).

Key concepts:
  - Path-loss model: RSSI → distance conversion
  - Shadow-fade detection: sudden RSSI drops indicate obstacle presence
  - Multi-node triangulation: cross-reference RSSI from all node pairs
  - Kalman filtering: smooth noisy WiFi measurements
"""

from __future__ import annotations

import logging
import math
import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

from config import (
    WIFI_SENSING_ENABLED,
    WIFI_RSSI_REFERENCE,
    WIFI_PATH_LOSS_EXPONENT,
    WIFI_SHADOW_FADE_THRESHOLD_DB,
    WIFI_BEACON_INTERVAL_S,
    WIFI_KALMAN_PROCESS_NOISE,
    WIFI_KALMAN_MEASUREMENT_NOISE,
    WIFI_OCCUPANCY_GRID_SIZE,
)

logger = logging.getLogger(__name__)


# ── Inline 1-D Kalman filter ─────────────────────────────────────────────

class SimpleKalman:
    """Minimal 1-D Kalman filter for smoothing noisy distance estimates."""

    def __init__(
        self,
        process_noise: float = 0.1,
        measurement_noise: float = 1.0,
        initial_estimate: float = 0.0,
    ):
        self.q = process_noise          # process noise covariance
        self.r = measurement_noise      # measurement noise covariance
        self.x = initial_estimate       # state estimate
        self.p = 1.0                    # error covariance

    def update(self, measurement: float) -> float:
        """Feed a raw measurement and return the filtered estimate."""
        # Predict step
        self.p += self.q
        # Update step
        k = self.p / (self.p + self.r)  # Kalman gain
        self.x += k * (measurement - self.x)
        self.p *= (1 - k)
        return self.x


# ── Data classes ──────────────────────────────────────────────────────────

@dataclass
class WiFiNode:
    """Represents a single WiFi node in the sensing network."""
    node_id: str
    node_type: str                          # "rover" | "phone" | "router"
    mac_address: str
    last_rssi: float = 0.0                  # dBm
    last_update_time: float = 0.0           # epoch seconds
    position_estimate: Tuple[float, float] = (0.0, 0.0)  # (x, y) in cm relative to rover


@dataclass
class WiFiMeasurement:
    """A single RSSI (and optional CSI) reading between two nodes."""
    source_node_id: str
    target_node_id: str
    rssi_dbm: float
    frequency_mhz: int = 2412              # default to 2.4 GHz ch 1
    timestamp: float = 0.0
    csi_amplitudes: Optional[List[float]] = None


@dataclass
class WiFiSensingResult:
    """Output of one WiFi sensing cycle."""
    zone_presence: Dict[str, float] = field(default_factory=lambda: {
        "left": 0.0, "center": 0.0, "right": 0.0,
    })
    zone_distance: Dict[str, float] = field(default_factory=lambda: {
        "left": float("inf"), "center": float("inf"), "right": float("inf"),
    })
    signal_quality: float = 0.0             # 0–1 overall measurement quality
    obstacle_detected: bool = False
    surroundings_rssi_map: List[List[float]] = field(default_factory=list)
    node_distances: Dict[str, float] = field(default_factory=dict)
    raw_measurements: List[WiFiMeasurement] = field(default_factory=list)


# ── Main engine ───────────────────────────────────────────────────────────

class WiFiSensingEngine:
    """
    Core WiFi sensing engine.

    Lifecycle:
      1. register_node() for each of the 3 nodes
      2. calibrate_baseline() once at startup (no obstacles present)
      3. Loop:  add_measurement() → process() → WiFiSensingResult
    """

    def __init__(self) -> None:
        self._nodes: Dict[str, WiFiNode] = {}
        self._kalman_filters: Dict[str, SimpleKalman] = {}
        self._baseline_rssi: Dict[str, float] = {}       # pair_key → dBm
        self._measurements: List[WiFiMeasurement] = []
        self._calibrated = False
        logger.info("WiFiSensingEngine initialised (enabled=%s)", WIFI_SENSING_ENABLED)

    # ── Node management ───────────────────────────────────────────────────

    def register_node(
        self,
        node_id: str,
        node_type: str,
        mac_address: str,
    ) -> None:
        """Register a WiFi node (rover / phone / router)."""
        self._nodes[node_id] = WiFiNode(
            node_id=node_id,
            node_type=node_type,
            mac_address=mac_address,
        )
        logger.info("Registered WiFi node '%s' type=%s mac=%s", node_id, node_type, mac_address)

    # ── Measurement ingestion ─────────────────────────────────────────────

    def add_measurement(self, measurement: WiFiMeasurement) -> None:
        """Feed a new RSSI reading into the engine."""
        if measurement.timestamp == 0.0:
            measurement.timestamp = time.time()
        self._measurements.append(measurement)

        # Update node state
        if measurement.source_node_id in self._nodes:
            self._nodes[measurement.source_node_id].last_rssi = measurement.rssi_dbm
            self._nodes[measurement.source_node_id].last_update_time = measurement.timestamp

        logger.debug(
            "WiFi meas %s→%s  RSSI=%.1f dBm",
            measurement.source_node_id,
            measurement.target_node_id,
            measurement.rssi_dbm,
        )

    # ── Calibration ───────────────────────────────────────────────────────

    def calibrate_baseline(self, duration_s: float = 10.0) -> None:
        """
        Record baseline RSSI for each node pair with no obstacles present.

        Should be called once at power-on in an unobstructed environment.
        If no measurements are available yet, use the config reference RSSI.
        """
        logger.info("Calibrating WiFi baseline for %.1f s …", duration_s)

        # Group recent measurements by pair
        pair_readings: Dict[str, List[float]] = {}
        now = time.time()
        for m in self._measurements:
            if now - m.timestamp <= duration_s:
                key = self._pair_key(m.source_node_id, m.target_node_id)
                pair_readings.setdefault(key, []).append(m.rssi_dbm)

        if pair_readings:
            for key, readings in pair_readings.items():
                self._baseline_rssi[key] = sum(readings) / len(readings)
                logger.info("Baseline  %s → %.1f dBm  (%d samples)",
                            key, self._baseline_rssi[key], len(readings))
        else:
            # No data yet — fall back to config reference
            logger.warning("No measurements during calibration window; using config reference")
            for key in self._all_pair_keys():
                self._baseline_rssi[key] = WIFI_RSSI_REFERENCE

        self._calibrated = True
        logger.info("WiFi baseline calibration complete (%d pairs)", len(self._baseline_rssi))

    # ── Main processing pipeline ──────────────────────────────────────────

    def process(self) -> WiFiSensingResult:
        """Run the full sensing pipeline and return a result."""
        result = WiFiSensingResult()

        if not WIFI_SENSING_ENABLED or not self._nodes:
            return result

        # Use the default baseline if calibrate_baseline was never called
        if not self._calibrated:
            for key in self._all_pair_keys():
                self._baseline_rssi.setdefault(key, WIFI_RSSI_REFERENCE)
            self._calibrated = True

        # Collect latest measurement per pair
        latest: Dict[str, WiFiMeasurement] = {}
        for m in self._measurements:
            key = self._pair_key(m.source_node_id, m.target_node_id)
            if key not in latest or m.timestamp > latest[key].timestamp:
                latest[key] = m

        if not latest:
            return result

        result.raw_measurements = list(latest.values())

        # ── Per-pair distance estimation ──────────────────────────────────
        obstacle_flags: List[bool] = []
        for key, m in latest.items():
            baseline = self._baseline_rssi.get(key, WIFI_RSSI_REFERENCE)
            raw_dist = self._rssi_to_distance(
                m.rssi_dbm, baseline, WIFI_PATH_LOSS_EXPONENT,
            )
            smoothed_dist = self._update_kalman(key, raw_dist)
            result.node_distances[key] = round(smoothed_dist, 2)

            fade = self._detect_shadow_fade(
                m.rssi_dbm, baseline, WIFI_SHADOW_FADE_THRESHOLD_DB,
            )
            obstacle_flags.append(fade)

        result.obstacle_detected = any(obstacle_flags)

        # ── Zone mapping ──────────────────────────────────────────────────
        zone_data = self._triangulate_zones(latest)
        result.zone_presence = zone_data["presence"]
        result.zone_distance = zone_data["distance"]

        # ── Signal quality ────────────────────────────────────────────────
        result.signal_quality = self._compute_signal_quality(latest)

        # ── Occupancy grid ────────────────────────────────────────────────
        result.surroundings_rssi_map = self._build_occupancy_grid()

        # Evict stale measurements (keep last 2 seconds)
        cutoff = time.time() - 2.0
        self._measurements = [m for m in self._measurements if m.timestamp > cutoff]

        return result

    # ── Path-loss model ───────────────────────────────────────────────────

    @staticmethod
    def _rssi_to_distance(
        rssi: float,
        reference_rssi: float,
        path_loss_exp: float,
    ) -> float:
        """
        Convert RSSI to distance using the log-distance path-loss model.

            d = 10 ^ ((reference_rssi − rssi) / (10 × n))

        where *n* is the path-loss exponent.
        """
        if path_loss_exp <= 0:
            return 1.0
        exponent = (reference_rssi - rssi) / (10.0 * path_loss_exp)
        dist = math.pow(10.0, exponent)
        return max(0.1, min(dist, 50.0))  # clamp 0.1–50 m

    # ── Shadow-fade detection ─────────────────────────────────────────────

    @staticmethod
    def _detect_shadow_fade(
        current_rssi: float,
        baseline_rssi: float,
        threshold: float,
    ) -> bool:
        """
        Return True when the RSSI has dropped by more than *threshold* dB
        below the baseline, indicating an obstacle is attenuating the signal.
        """
        return (baseline_rssi - current_rssi) > threshold

    # ── Triangulation / zone mapping ──────────────────────────────────────

    def _triangulate_zones(
        self,
        measurements: Dict[str, WiFiMeasurement],
    ) -> Dict[str, dict]:
        """
        Map multi-node RSSI measurements to left / center / right zones.

        Heuristic mapping:
          - rover↔router link:  predominantly *center* zone
          - phone↔router link:  predominantly *left* zone (phone is on user)
          - rover↔phone link:   predominantly *right* zone
        Obstacle presence per zone scales with shadow-fade magnitude.
        """
        zone_presence: Dict[str, float] = {"left": 0.0, "center": 0.0, "right": 0.0}
        zone_distance: Dict[str, float] = {
            "left": float("inf"), "center": float("inf"), "right": float("inf"),
        }

        # Mapping of pair keys to their primary zone influence
        pair_zone_map = self._get_pair_zone_map()

        for key, m in measurements.items():
            baseline = self._baseline_rssi.get(key, WIFI_RSSI_REFERENCE)
            fade_db = baseline - m.rssi_dbm
            dist = self._rssi_to_distance(m.rssi_dbm, baseline, WIFI_PATH_LOSS_EXPONENT)

            zone = pair_zone_map.get(key, "center")
            # Presence confidence: sigmoid-like curve on fade magnitude
            if fade_db > 0:
                presence = min(1.0, fade_db / (WIFI_SHADOW_FADE_THRESHOLD_DB * 2.0))
            else:
                presence = 0.0

            zone_presence[zone] = max(zone_presence[zone], presence)
            zone_distance[zone] = min(zone_distance[zone], dist)

        return {"presence": zone_presence, "distance": zone_distance}

    # ── Kalman filter ─────────────────────────────────────────────────────

    def _update_kalman(self, node_pair_key: str, raw_distance: float) -> float:
        """Smooth the raw distance for a node pair using a Kalman filter."""
        if node_pair_key not in self._kalman_filters:
            self._kalman_filters[node_pair_key] = SimpleKalman(
                process_noise=WIFI_KALMAN_PROCESS_NOISE,
                measurement_noise=WIFI_KALMAN_MEASUREMENT_NOISE,
                initial_estimate=raw_distance,
            )
        return self._kalman_filters[node_pair_key].update(raw_distance)

    # ── Occupancy grid ────────────────────────────────────────────────────

    def _build_occupancy_grid(self) -> List[List[float]]:
        """
        Build an N×N occupancy grid from all current measurements.

        Grid layout (rover at bottom-centre):
            row 0 = farthest from rover (ahead-left … ahead-right)
            row N-1 = closest to rover
        Each cell is a probability 0.0 (free) … 1.0 (occupied).
        """
        n = WIFI_OCCUPANCY_GRID_SIZE
        grid: List[List[float]] = [[0.0] * n for _ in range(n)]

        # Collect latest per-pair shadow-fade magnitudes
        latest: Dict[str, WiFiMeasurement] = {}
        for m in self._measurements:
            key = self._pair_key(m.source_node_id, m.target_node_id)
            if key not in latest or m.timestamp > latest[key].timestamp:
                latest[key] = m

        pair_zone_map = self._get_pair_zone_map()
        zone_col_ranges = {
            "left":   range(0, n // 3),
            "center": range(n // 3, 2 * n // 3),
            "right":  range(2 * n // 3, n),
        }

        for key, m in latest.items():
            baseline = self._baseline_rssi.get(key, WIFI_RSSI_REFERENCE)
            fade_db = baseline - m.rssi_dbm
            if fade_db <= 0:
                continue

            occupancy = min(1.0, fade_db / (WIFI_SHADOW_FADE_THRESHOLD_DB * 2.0))
            dist = self._rssi_to_distance(m.rssi_dbm, baseline, WIFI_PATH_LOSS_EXPONENT)

            # Map distance to row (0 = far, n-1 = near)
            max_range = 4.0  # metres
            row = n - 1 - int(min(dist / max_range, 1.0) * (n - 1))
            row = max(0, min(n - 1, row))

            zone = pair_zone_map.get(key, "center")
            for col in zone_col_ranges.get(zone, range(n // 3, 2 * n // 3)):
                grid[row][col] = max(grid[row][col], occupancy)

        return grid

    # ── Node status ───────────────────────────────────────────────────────

    def get_node_status(self) -> Dict[str, dict]:
        """Return status of all registered nodes (for dashboard / logging)."""
        now = time.time()
        status: Dict[str, dict] = {}
        for nid, node in self._nodes.items():
            age = now - node.last_update_time if node.last_update_time > 0 else -1.0
            status[nid] = {
                "type": node.node_type,
                "mac": node.mac_address,
                "last_rssi": node.last_rssi,
                "age_s": round(age, 1),
                "alive": 0 < age < 5.0,
                "position": node.position_estimate,
            }
        return status

    # ── Internal helpers ──────────────────────────────────────────────────

    @staticmethod
    def _pair_key(a: str, b: str) -> str:
        """Canonical key for a node pair (order-independent)."""
        return f"{min(a, b)}↔{max(a, b)}"

    def _all_pair_keys(self) -> List[str]:
        """Return pair keys for every unique combination of registered nodes."""
        ids = sorted(self._nodes.keys())
        keys: List[str] = []
        for i in range(len(ids)):
            for j in range(i + 1, len(ids)):
                keys.append(self._pair_key(ids[i], ids[j]))
        return keys

    def _get_pair_zone_map(self) -> Dict[str, str]:
        """
        Map each node-pair key to the zone it most influences.

        Convention (based on physical placement):
          rover↔router  → center  (straight-ahead link)
          phone↔router  → left    (phone on user's left side / pocket)
          phone↔rover   → right   (cross-link)
        Falls back to 'center' for unknown pairs.
        """
        zone_map: Dict[str, str] = {}
        rover_ids  = [n.node_id for n in self._nodes.values() if n.node_type == "rover"]
        phone_ids  = [n.node_id for n in self._nodes.values() if n.node_type == "phone"]
        router_ids = [n.node_id for n in self._nodes.values() if n.node_type == "router"]

        for r in rover_ids:
            for rt in router_ids:
                zone_map[self._pair_key(r, rt)] = "center"
        for p in phone_ids:
            for rt in router_ids:
                zone_map[self._pair_key(p, rt)] = "left"
        for p in phone_ids:
            for r in rover_ids:
                zone_map[self._pair_key(p, r)] = "right"

        return zone_map

    def _compute_signal_quality(
        self,
        latest: Dict[str, WiFiMeasurement],
    ) -> float:
        """
        Compute an overall signal quality score 0–1.

        Based on recency of measurements and RSSI plausibility.
        """
        if not latest:
            return 0.0
        now = time.time()
        scores: List[float] = []
        for m in latest.values():
            age = now - m.timestamp
            recency = max(0.0, 1.0 - age / 5.0)          # 0 if >5 s old
            rssi_ok = 1.0 if -90 < m.rssi_dbm < -10 else 0.5  # plausible range
            scores.append(recency * rssi_ok)
        return sum(scores) / len(scores) if scores else 0.0
