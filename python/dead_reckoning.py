"""
dead_reckoning.py — Cartesian position tracker for Nemo~Sense.

Estimates the rover's (x, y) position in metres from the starting point
using only motor PWM values and elapsed time. No GPS or IMU required.

Coordinate system:
    +Y = forward (north at start)
    +X = right   (east  at start)
    Origin (0, 0) = wherever the rover was when it powered on

Algorithm (differential-drive dead reckoning):
    1. Convert L/R PWM → L/R wheel speeds (m/s) via inverse of speed_to_pwm()
    2. Forward speed  v = (v_left + v_right) / 2
    3. Angular rate   ω = (v_right - v_left) / WHEEL_BASE_M   (rad/s)
    4. Update heading θ += ω × dt
    5. Update position:
           x += v × sin(θ) × dt
           y += v × cos(θ) × dt

Accuracy notes:
    - Assumes both wheels have the same diameter and no slip.
    - Heading drifts over time without a compass (normal for dead reckoning).
    - Good for tracking tens of metres; error accumulates beyond ~50 m.
"""

from __future__ import annotations

import math
import time
import logging
from dataclasses import dataclass, field
from typing import List, Tuple

from config import (
    SPEED_TO_PWM_K,
    SPEED_TO_PWM_B,
    PWM_MIN,
    PWM_MAX,
)

logger = logging.getLogger("nemosense.dr")

# ── Physical constants (tune these for your Quarky) ──────────────────────
WHEEL_BASE_M = 0.12     # distance between left and right wheels in metres
                        # Quarky is ~12 cm wide — adjust if yours differs
MIN_PWM_MOVE = 40       # PWM values below this = wheel not turning (stall)


# ── Position snapshot ─────────────────────────────────────────────────────

@dataclass
class Pose:
    """Rover pose in the Cartesian plane."""
    x:       float = 0.0   # metres east  (+) / west  (-) from start
    y:       float = 0.0   # metres north (+) / south (-) from start
    heading: float = 0.0   # degrees, 0 = north, clockwise positive
    distance_total: float = 0.0  # total odometry distance (metres)

    def __str__(self) -> str:
        hdg_arrow = _heading_arrow(self.heading)
        return (
            f"x={self.x:+.2f}m  y={self.y:+.2f}m  "
            f"hdg={self.heading:.1f}° {hdg_arrow}  "
            f"total={self.distance_total:.2f}m"
        )

    def cartesian_str(self) -> str:
        """Pretty Cartesian display for terminal."""
        return f"({self.x:+.2f}, {self.y:+.2f}) m"


def _heading_arrow(deg: float) -> str:
    arrows = ["↑N", "↗", "→E", "↘", "↓S", "↙", "←W", "↖"]
    idx = int((deg + 22.5) / 45.0) % 8
    return arrows[idx]


# ── Dead Reckoner ─────────────────────────────────────────────────────────

class DeadReckoner:
    """
    Tracks rover position on a 2-D Cartesian plane.

    Usage::

        dr = DeadReckoner()
        # inside the main loop, after computing motor PWM:
        pose = dr.update(left_pwm, right_pwm)
        print(pose)
    """

    def __init__(self, wheel_base_m: float = WHEEL_BASE_M):
        self._wb   = wheel_base_m
        self._pose = Pose()
        self._last_t = time.monotonic()
        self._history: List[Tuple[float, float]] = [(0.0, 0.0)]
        logger.info("Dead reckoning started at origin (0, 0)")

    # ── Public API ────────────────────────────────────────────────────────

    def update(self, left_pwm: int, right_pwm: int) -> Pose:
        """
        Call once per control loop with the current motor PWM values.
        Returns the updated Pose.
        """
        now = time.monotonic()
        dt  = now - self._last_t
        self._last_t = now

        if dt <= 0 or dt > 1.0:
            # Skip stale or implausible deltas
            return self._pose

        v_left  = self._pwm_to_speed(left_pwm)
        v_right = self._pwm_to_speed(right_pwm)

        v_fwd   = (v_left + v_right) / 2.0          # m/s forward
        omega   = (v_right - v_left) / self._wb      # rad/s turn rate

        # Update heading (convert to degrees, keep in [0, 360))
        theta_rad = math.radians(self._pose.heading)
        theta_rad += omega * dt
        self._pose.heading = math.degrees(theta_rad) % 360.0

        # Update Cartesian position
        dx = v_fwd * math.sin(theta_rad) * dt
        dy = v_fwd * math.cos(theta_rad) * dt
        self._pose.x += dx
        self._pose.y += dy
        self._pose.distance_total += abs(v_fwd) * dt

        # Record history every ~0.5 m for path logging
        last_x, last_y = self._history[-1]
        dist_since_last = math.hypot(self._pose.x - last_x, self._pose.y - last_y)
        if dist_since_last >= 0.5:
            self._history.append((round(self._pose.x, 2), round(self._pose.y, 2)))
            logger.info("Path waypoint: %s", self._pose.cartesian_str())

        return self._pose

    def reset(self):
        """Reset to origin — call this if the rover is repositioned."""
        self._pose = Pose()
        self._history = [(0.0, 0.0)]
        self._last_t = time.monotonic()
        logger.info("Dead reckoning reset to origin")

    @property
    def pose(self) -> Pose:
        return self._pose

    @property
    def path(self) -> List[Tuple[float, float]]:
        """All recorded (x, y) waypoints since last reset."""
        return list(self._history)

    def path_ascii(self, width: int = 41, height: int = 21) -> str:
        """
        Render the rover's path as a small ASCII Cartesian plot.

        Example output:
            +Y (north)
            ^
            |   *
            |  *
            | *
            +--------> +X (east)
        """
        if not self._history:
            return "(no path yet)"

        xs = [p[0] for p in self._history]
        ys = [p[1] for p in self._history]
        x_min, x_max = min(xs + [0.0]), max(xs + [0.0])
        y_min, y_max = min(ys + [0.0]), max(ys + [0.0])

        # Add 10% padding
        x_pad = max((x_max - x_min) * 0.1, 0.5)
        y_pad = max((y_max - y_min) * 0.1, 0.5)
        x_min -= x_pad; x_max += x_pad
        y_min -= y_pad; y_max += y_pad

        grid = [[" "] * width for _ in range(height)]

        def to_col(x):
            return int((x - x_min) / (x_max - x_min) * (width - 1))

        def to_row(y):
            return int((1.0 - (y - y_min) / (y_max - y_min)) * (height - 1))

        # Draw axes
        origin_col = to_col(0.0)
        origin_row = to_row(0.0)
        for r in range(height):
            if 0 <= origin_col < width:
                grid[r][origin_col] = "│"
        for c in range(width):
            if 0 <= origin_row < height:
                grid[origin_row][c] = "─"
        if 0 <= origin_row < height and 0 <= origin_col < width:
            grid[origin_row][origin_col] = "┼"

        # Draw path
        for i, (px, py) in enumerate(self._history):
            c, r = to_col(px), to_row(py)
            if 0 <= r < height and 0 <= c < width:
                grid[r][c] = "●" if i == len(self._history) - 1 else "·"

        # Draw start marker
        sc, sr = to_col(0.0), to_row(0.0)
        if 0 <= sr < height and 0 <= sc < width:
            grid[sr][sc] = "S"

        lines = ["  +Y (north)"]
        for row in grid:
            lines.append("  " + "".join(row))
        lines.append("  " + " " * origin_col + "+X (east)")
        lines.append(f"  Rover: {self._pose.cartesian_str()}  hdg={self._pose.heading:.1f}°")
        return "\n".join(lines)

    # ── Internal ──────────────────────────────────────────────────────────

    @staticmethod
    def _pwm_to_speed(pwm: int) -> float:
        """
        Inverse of speed_to_pwm():  speed = (PWM - B) / K
        Returns 0 if below stall threshold or zero PWM.
        Handles negative PWM as reverse (negative speed).
        """
        if abs(pwm) < MIN_PWM_MOVE:
            return 0.0
        sign  = 1.0 if pwm > 0 else -1.0
        speed = (abs(pwm) - SPEED_TO_PWM_B) / SPEED_TO_PWM_K
        return sign * max(0.0, speed)
