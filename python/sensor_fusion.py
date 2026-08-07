"""
sensor_fusion.py — Vision + WiFi sensor fusion for the Netra Guide Rover.

Combines camera-based obstacle detection (VisionResult) with WiFi radio
sensing (WiFiSensingResult) to produce a higher-confidence obstacle map
with better depth estimation.

Fusion strategy:
  - Vision provides: object identity, bounding boxes, heuristic depth
  - WiFi provides: presence confidence, coarse distance, through-wall detection
  - Both agree → high confidence, weighted average depth
  - Vision only → use heuristic depth, moderate confidence
  - WiFi only → report 'unknown obstacle', WiFi-estimated distance
  - Disagreement → conservative (take closer distance)
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field

import numpy as np

from config import (
    FUSION_VISION_WEIGHT,
    FUSION_WIFI_WEIGHT,
    DEPTH_DANGER_THRESHOLD,
    DEPTH_EMERGENCY_THRESHOLD,
    WIFI_OCCUPANCY_GRID_SIZE,
    WIFI_OCCUPANCY_CELL_SIZE_M,
)
from vision import VisionResult, ObstacleInfo
from wifi_sensing import WiFiSensingResult

logger = logging.getLogger(__name__)

# ── Data classes ──────────────────────────────────────────────────────────

@dataclass
class FusedObstacle:
    """Single obstacle after vision + WiFi fusion."""
    label: str
    confidence: float                           # fused confidence 0–1
    distance_m: float                           # best distance estimate (m)
    zone: str                                   # "left" | "center" | "right"
    bbox: Optional[tuple[int, int, int, int]] = None  # pixel bbox if from vision
    source: str = "fused"                       # "vision" | "wifi" | "fused"
    depth_confidence: float = 0.0               # 0–1 trust in the distance value

@dataclass
class FusedResult:
    """Aggregated result of one sensor-fusion cycle."""
    obstacles: list[FusedObstacle] = field(default_factory=list)
    closest_distance: float = float("inf")
    recommended_action: str = "clear"           # clear | steer_left | steer_right | stop
    zone_min_dist: dict[str, float] = field(default_factory=lambda: {
        "left": float("inf"), "center": float("inf"), "right": float("inf"),
    })
    surroundings_map: "SurroundingsMap" | None = None
    vision_confidence: float = 0.0              # 0–1
    wifi_confidence: float = 0.0                # 0–1
    frame_time_ms: float = 0.0
    source: str = "fused"

# ── Surroundings map ─────────────────────────────────────────────────────

class SurroundingsMap:
    """
    N×N occupancy grid centred on the rover.

    Each cell holds a probability 0.0 (free) … 1.0 (occupied).
    Default grid is 8×8 at 0.5 m per cell → covers 4 m × 4 m.
    The rover sits at cell (rows-1, cols//2), i.e. bottom-centre.
    """

    def __init__(
        self,
        size: int = WIFI_OCCUPANCY_GRID_SIZE,
        cell_size_m: float = WIFI_OCCUPANCY_CELL_SIZE_M,
    ) -> None:
        self.size = size
        self.cell_size_m = cell_size_m
        self.grid: np.ndarray = np.zeros((size, size), dtype=np.float64)
        self.rover_cell: tuple[int, int] = (size - 1, size // 2)

    # ── Vision projection ─────────────────────────────────────────────────

    def update_from_vision(self, vision_result: VisionResult) -> None:
        """Project detected obstacles into the occupancy grid."""
        zone_col_map = self._zone_col_ranges()
        for obs in vision_result.obstacles:
            row = self._distance_to_row(obs.distance_m)
            cols = zone_col_map.get(obs.zone, zone_col_map["center"])
            for c in cols:
                self.grid[row, c] = min(1.0, max(self.grid[row, c], obs.confidence))

    # ── WiFi merge ────────────────────────────────────────────────────────

    def update_from_wifi(self, wifi_result: WiFiSensingResult) -> None:
        """Merge WiFi-derived occupancy probabilities into the grid."""
        wifi_grid = wifi_result.surroundings_rssi_map
        if not wifi_grid:
            return
        rows = min(len(wifi_grid), self.size)
        for r in range(rows):
            cols = min(len(wifi_grid[r]), self.size)
            for c in range(cols):
                self.grid[r, c] = min(1.0, max(self.grid[r, c], wifi_grid[r][c]))

    # ── Zone summary ──────────────────────────────────────────────────────

    def get_zone_summary(self) -> dict[str, float]:
        """Return closest occupied distance for left / center / right zones."""
        zone_cols = self._zone_col_ranges()
        summary: dict[str, float] = {}
        for zone, cols in zone_cols.items():
            min_dist = float("inf")
            for r in range(self.size):
                for c in cols:
                    if self.grid[r, c] > 0.3:  # occupancy threshold
                        dist = self._row_to_distance(r)
                        min_dist = min(min_dist, dist)
            summary[zone] = min_dist
        return summary

    # ── ASCII visualisation ───────────────────────────────────────────────

    def render_ascii(self) -> str:
        """Text visualisation of the grid for logging / debug."""
        chars = " ░▒▓█"
        lines: list[str] = []
        for r in range(self.size):
            row_chars: list[str] = []
            for c in range(self.size):
                if (r, c) == self.rover_cell:
                    row_chars.append("R")
                else:
                    idx = int(self.grid[r, c] * (len(chars) - 1))
                    idx = max(0, min(len(chars) - 1, idx))
                    row_chars.append(chars[idx])
            lines.append("".join(row_chars))
        return "\n".join(lines)

    # ── Internal helpers ──────────────────────────────────────────────────

    def _zone_col_ranges(self) -> dict[str, range]:
        n = self.size
        return {
            "left":   range(0, n // 3),
            "center": range(n // 3, 2 * n // 3),
            "right":  range(2 * n // 3, n),
        }

    def _distance_to_row(self, distance_m: float) -> int:
        """Convert a distance in metres to a grid row (0 = far, n-1 = near)."""
        max_range = self.size * self.cell_size_m
        frac = min(distance_m / max_range, 1.0)
        row = self.size - 1 - int(frac * (self.size - 1))
        return max(0, min(self.size - 1, row))

    def _row_to_distance(self, row: int) -> float:
        """Convert a grid row back to an approximate distance in metres."""
        max_range = self.size * self.cell_size_m
        frac = (self.size - 1 - row) / max(self.size - 1, 1)
        return frac * max_range

# ── Sensor fusion engine ─────────────────────────────────────────────────

class SensorFusion:
    """
    Fuses VisionResult and WiFiSensingResult into a single FusedResult.

    Weights are adjustable; defaults come from config.py.
    """

    def __init__(
        self,
        vision_weight: float = FUSION_VISION_WEIGHT,
        wifi_weight: float = FUSION_WIFI_WEIGHT,
    ) -> None:
        self.vision_weight = vision_weight
        self.wifi_weight = wifi_weight
        logger.info(
            "SensorFusion initialised  vision_w=%.2f  wifi_w=%.2f",
            vision_weight, wifi_weight,
        )

    # ── Main fuse method ──────────────────────────────────────────────────

    def fuse(
        self,
        vision_result: VisionResult,
        wifi_result: WiFiSensingResult,
    ) -> FusedResult:
        """Fuse a single cycle of vision + WiFi data."""
        t0 = time.monotonic()
        result = FusedResult()

        # Confidence assessment
        result.vision_confidence, result.wifi_confidence = self._compute_confidence(
            vision_result, wifi_result,
        )

        # ── Build surroundings map ────────────────────────────────────────
        smap = SurroundingsMap()
        smap.update_from_vision(vision_result)
        smap.update_from_wifi(wifi_result)
        result.surroundings_map = smap

        # ── Merge per-zone distances ──────────────────────────────────────
        result.zone_min_dist = self._merge_zone_distances(
            vision_result.zone_min_dist,
            wifi_result.zone_distance,
        )

        # ── Produce fused obstacle list ───────────────────────────────────
        # Start with vision obstacles (they have labels + bboxes)
        vision_zones_covered: set = set()
        for obs in vision_result.obstacles:
            wifi_zone_dist = wifi_result.zone_distance.get(obs.zone, float("inf"))
            wifi_zone_pres = wifi_result.zone_presence.get(obs.zone, 0.0)

            if wifi_zone_pres > 0.3:
                # Both agree — fuse depth and boost confidence
                fused_dist = (
                    self.vision_weight * obs.distance_m
                    + self.wifi_weight * wifi_zone_dist
                )
                fused_conf = min(1.0, obs.confidence + wifi_zone_pres * 0.3)
                source = "fused"
                depth_conf = 0.85
            else:
                # Vision only
                fused_dist = obs.distance_m
                fused_conf = obs.confidence * 0.85  # slight penalty
                source = "vision"
                depth_conf = 0.6

            result.obstacles.append(FusedObstacle(
                label=obs.label,
                confidence=round(fused_conf, 3),
                distance_m=round(fused_dist, 2),
                zone=obs.zone,
                bbox=obs.bbox,
                source=source,
                depth_confidence=depth_conf,
            ))
            vision_zones_covered.add(obs.zone)

        # WiFi-only detections in zones not covered by vision
        for zone in ("left", "center", "right"):
            if zone in vision_zones_covered:
                continue
            pres = wifi_result.zone_presence.get(zone, 0.0)
            dist = wifi_result.zone_distance.get(zone, float("inf"))
            if pres > 0.3 and dist < 10.0:
                result.obstacles.append(FusedObstacle(
                    label="unknown_obstacle",
                    confidence=round(pres * 0.7, 3),
                    distance_m=round(dist, 2),
                    zone=zone,
                    bbox=None,
                    source="wifi",
                    depth_confidence=0.4,
                ))

        # ── Closest distance & action ─────────────────────────────────────
        if result.obstacles:
            result.closest_distance = min(o.distance_m for o in result.obstacles)
        result.closest_distance = min(
            result.closest_distance,
            min(result.zone_min_dist.values()),
        )
        result.recommended_action = self._determine_action(result.zone_min_dist)
        result.source = "fused"

        result.frame_time_ms = (time.monotonic() - t0) * 1000.0
        logger.debug(
            "Fusion done in %.1f ms — %d obstacles, action=%s",
            result.frame_time_ms, len(result.obstacles), result.recommended_action,
        )
        return result

    # ── Zone distance merging ─────────────────────────────────────────────

    def _merge_zone_distances(
        self,
        vision_zones: dict[str, float],
        wifi_zones: dict[str, float],
    ) -> dict[str, float]:
        """
        Merge per-zone minimum distances from vision and WiFi.

        Strategy:
          - Both finite → weighted average (but clamp to the closer one)
          - One infinite → use the finite value
          - Both infinite → inf
        """
        merged: dict[str, float] = {}
        for zone in ("left", "center", "right"):
            v = vision_zones.get(zone, float("inf"))
            w = wifi_zones.get(zone, float("inf"))
            if v == float("inf") and w == float("inf"):
                merged[zone] = float("inf")
            elif v == float("inf"):
                merged[zone] = w
            elif w == float("inf"):
                merged[zone] = v
            else:
                # Conservative: weighted average but never farther than the closer
                avg = self.vision_weight * v + self.wifi_weight * w
                merged[zone] = min(avg, min(v, w))
        return merged

    # ── Action determination ──────────────────────────────────────────────

    @staticmethod
    def _determine_action(fused_zones: dict[str, float]) -> str:
        """Pick a navigation action based on fused zone distances."""
        left_d = fused_zones.get("left", float("inf"))
        center_d = fused_zones.get("center", float("inf"))
        right_d = fused_zones.get("right", float("inf"))
        closest = min(left_d, center_d, right_d)

        if closest > DEPTH_DANGER_THRESHOLD:
            return "clear"

        if (left_d < DEPTH_EMERGENCY_THRESHOLD
                and center_d < DEPTH_EMERGENCY_THRESHOLD
                and right_d < DEPTH_EMERGENCY_THRESHOLD):
            return "stop"

        if center_d < DEPTH_DANGER_THRESHOLD:
            return "steer_left" if left_d > right_d else "steer_right"
        if left_d < DEPTH_DANGER_THRESHOLD:
            return "steer_right"
        if right_d < DEPTH_DANGER_THRESHOLD:
            return "steer_left"

        return "clear"

    # ── Confidence computation ────────────────────────────────────────────

    @staticmethod
    def _compute_confidence(
        vision_result: VisionResult,
        wifi_result: WiFiSensingResult,
    ) -> tuple[float, float]:
        """
        Evaluate how much we trust each sensor this cycle.

        Returns (vision_confidence, wifi_confidence) each in [0, 1].
        """
        # Vision: based on detection count and frame source
        if vision_result.obstacles:
            avg_conf = sum(o.confidence for o in vision_result.obstacles) / len(
                vision_result.obstacles
            )
            v_conf = min(1.0, avg_conf * 1.1)
        else:
            v_conf = 0.3 if vision_result.source != "simulated" else 0.1

        # WiFi: based on signal quality
        w_conf = wifi_result.signal_quality

        return round(v_conf, 3), round(w_conf, 3)
