"""
speed_learner.py — Adaptive speed controller for the Netra rover.

Monitors the phone's accelerometer data (received via Bluetooth) to detect
user intent signals:

  * Leash tug:     sudden negative X-acceleration spike → slow down 20 %
  * Smooth walk:   low-variance acceleration over 3 s    → speed up 2 %
  * Stopped:       near-zero magnitude for > 3 s         → target speed = 0

An exponential moving average smooths the target, and a ramp limiter caps
the rate of change.  The comfort speed is persisted to a JSON file so it
carries across power cycles.
"""

from __future__ import annotations

import json
import logging
import math
import os
import time
from collections import deque

from config import (
    MIN_SPEED,
    MAX_SPEED,
    DEFAULT_SPEED,
    TUG_ACCEL_THRESHOLD,
    SMOOTH_WINDOW_S,
    STOPPED_DURATION_S,
    EMA_ALPHA,
    SPEED_RAMP_RATE,
    COMFORT_SPEED_FILE,
)

logger = logging.getLogger(__name__)

class SpeedLearner:
    """
    Adaptive speed controller driven by phone accelerometer data.

    Usage::

        sl = SpeedLearner()
        sl.update(accel_data={"x": 0.1, "y": -0.03, "z": 9.78},
                  current_motor_speed=0.3)
        target = sl.get_target_speed()
    """

    def __init__(self):
        # ── Comfort speed (persisted) ─────────────────────────────────────
        self._comfort_speed: float = self._load_comfort_speed()
        self._target_speed: float = self._comfort_speed

        # ── Acceleration history for variance analysis ────────────────────
        # Each entry: (timestamp, magnitude)
        self._accel_history: deque = deque()

        # ── Stopped detection ─────────────────────────────────────────────
        self._stopped_since: float | None = None
        # Magnitude threshold for "not moving" (m/s², gravity-subtracted)
        self._stopped_mag_threshold = 0.3

        # ── Timing ────────────────────────────────────────────────────────
        self._last_update_time: float = time.monotonic()

    # ── Public API ────────────────────────────────────────────────────────

    def update(
        self,
        accel_data: dict | None,
        current_motor_speed: float,
    ):
        """
        Feed new accelerometer data and let the controller adjust.

        Parameters
        ----------
        accel_data : dict with keys "x", "y", "z" (m/s²), or None
        current_motor_speed : current base speed in m/s (for reference only)
        """
        now = time.monotonic()
        dt = now - self._last_update_time
        self._last_update_time = now

        if accel_data is None:
            return  # no data this cycle

        ax = float(accel_data.get("x", 0.0))
        ay = float(accel_data.get("y", 0.0))
        az = float(accel_data.get("z", 0.0))

        # Gravity-subtracted magnitude (phone roughly vertical, g ≈ 9.81)
        mag = math.sqrt(ax * ax + ay * ay + az * az)
        grav_sub = abs(mag - 9.81)

        # Record for windowed variance analysis
        self._accel_history.append((now, grav_sub))
        # Trim old entries outside the smooth window
        cutoff = now - SMOOTH_WINDOW_S
        while self._accel_history and self._accel_history[0][0] < cutoff:
            self._accel_history.popleft()

        # ── 1. Leash tug detection ───────────────────────────────────────
        # A tug is a sudden negative X spike (user pulling the leash back).
        if ax < -TUG_ACCEL_THRESHOLD:
            new_target = self._target_speed * 0.80  # reduce by 20 %
            logger.info("Tug detected (ax=%.2f), target %.2f → %.2f", ax, self._target_speed, new_target)
            self._target_speed = max(MIN_SPEED, new_target)
            self._stopped_since = None
            self._apply_ema_and_ramp(dt)
            return

        # ── 2. Stopped detection ─────────────────────────────────────────
        if grav_sub < self._stopped_mag_threshold:
            if self._stopped_since is None:
                self._stopped_since = now
            elif (now - self._stopped_since) >= STOPPED_DURATION_S:
                self._target_speed = 0.0
                logger.debug("User stopped for >%.0fs, target → 0", STOPPED_DURATION_S)
                self._apply_ema_and_ramp(dt)
                return
        else:
            self._stopped_since = None

        # ── 3. Smooth walking detection ──────────────────────────────────
        if len(self._accel_history) >= 5:
            mags = [m for _, m in self._accel_history]
            variance = self._variance(mags)
            if variance < 0.5:
                # Very smooth gait → gradually increase
                new_target = self._target_speed * 1.02  # +2 %
                self._target_speed = min(MAX_SPEED, new_target)

        # ── 4. Apply EMA and ramp ────────────────────────────────────────
        self._apply_ema_and_ramp(dt)

    def get_target_speed(self) -> float:
        """Return the current adaptively-computed target speed (m/s)."""
        return self._comfort_speed

    def save(self):
        """Persist the comfort speed to disk."""
        self._save_comfort_speed(self._comfort_speed)

    # ── Internal helpers ──────────────────────────────────────────────────

    def _apply_ema_and_ramp(self, dt: float):
        """
        Smooth the comfort speed toward _target_speed using an EMA, then
        clamp the rate of change.
        """
        # EMA update
        new_comfort = (1.0 - EMA_ALPHA) * self._comfort_speed + EMA_ALPHA * self._target_speed

        # Ramp-rate limit
        max_change = SPEED_RAMP_RATE * dt
        delta = new_comfort - self._comfort_speed
        if abs(delta) > max_change:
            delta = max_change if delta > 0 else -max_change
        self._comfort_speed += delta

        # Clamp
        if self._comfort_speed < 0.0:
            self._comfort_speed = 0.0
        elif self._comfort_speed > MAX_SPEED:
            self._comfort_speed = MAX_SPEED

        # Enforce minimum nonzero speed
        if 0.0 < self._comfort_speed < MIN_SPEED:
            self._comfort_speed = MIN_SPEED

    @staticmethod
    def _variance(values: list) -> float:
        """Simple variance of a list of floats."""
        n = len(values)
        if n < 2:
            return 0.0
        mean = sum(values) / n
        return sum((v - mean) ** 2 for v in values) / (n - 1)

    # ── Persistence ───────────────────────────────────────────────────────

    def _load_comfort_speed(self) -> float:
        """Load persisted comfort speed, falling back to DEFAULT_SPEED."""
        try:
            if os.path.isfile(COMFORT_SPEED_FILE):
                with open(COMFORT_SPEED_FILE, "r") as fh:
                    data = json.load(fh)
                speed = float(data.get("comfort_speed", DEFAULT_SPEED))
                logger.info("Loaded comfort speed: %.2f m/s", speed)
                return max(MIN_SPEED, min(MAX_SPEED, speed))
        except Exception as exc:
            logger.warning("Could not load comfort speed: %s", exc)
        return DEFAULT_SPEED

    @staticmethod
    def _save_comfort_speed(speed: float):
        """Persist comfort speed to a JSON file."""
        try:
            with open(COMFORT_SPEED_FILE, "w") as fh:
                json.dump({"comfort_speed": round(speed, 4)}, fh)
        except Exception as exc:
            logger.warning("Could not save comfort speed: %s", exc)
