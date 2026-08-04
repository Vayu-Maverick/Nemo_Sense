"""
micro_nav.py — Reactive obstacle-avoidance layer for the Netra rover.

Operates at the frame rate of the vision pipeline (~3-5 Hz).  Takes a
VisionResult and produces a MicroNavCommand that can override macro-level
GPS navigation when obstacles are detected.

Decision priority:
  1. ALL zones blocked at emergency threshold → STOP
  2. CENTER blocked → steer toward the clearer side
  3. Single side blocked → steer away from it
  4. All clear → let macro-nav control (action = "none")
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Optional

from config import DEPTH_DANGER_THRESHOLD, DEPTH_EMERGENCY_THRESHOLD
from vision import VisionResult

# Import FusedResult only if available (WiFi sensing may not be installed)
try:
    from sensor_fusion import FusedResult
except ImportError:
    FusedResult = None  # type: ignore

logger = logging.getLogger(__name__)


@dataclass
class MicroNavCommand:
    """Output of one reactive-avoidance cycle."""
    action: str = "none"      # none | steer_left | steer_right | stop
    urgency: float = 0.0      # 0.0 (far) … 1.0 (imminent collision)
    speak_text: str = ""       # text for phone TTS (empty if nothing to say)


class MicroNavigator:
    """
    Reactive obstacle-avoidance controller.

    Usage::

        micro = MicroNavigator()
        cmd = micro.update(vision_result)
        if cmd.action != "none":
            # override macro-nav with micro-nav steering
    """

    def __init__(
        self,
        danger_threshold: float = DEPTH_DANGER_THRESHOLD,
        emergency_threshold: float = DEPTH_EMERGENCY_THRESHOLD,
    ):
        self._danger = danger_threshold
        self._emergency = emergency_threshold

        # Track the last spoken action so we don't spam TTS every frame.
        self._last_spoken_action: str = "none"

    # ── Core update ───────────────────────────────────────────────────────

    def update(self, vr: VisionResult) -> MicroNavCommand:
        """
        Evaluate the current VisionResult and decide a reactive command.

        Parameters
        ----------
        vr : VisionResult
            Latest output from VisionSystem.process_frame().

        Returns
        -------
        MicroNavCommand
        """
        return self._evaluate_zones(vr.zone_min_dist, vr.obstacles)

    def update_fused(self, fused: 'FusedResult') -> MicroNavCommand:
        """
        Evaluate a FusedResult (vision + WiFi) for reactive obstacle avoidance.
        Uses the higher-confidence fused distances instead of vision-only.

        Falls back to standard update() if FusedResult is not available.
        """
        if FusedResult is None or not isinstance(fused, FusedResult):
            # Fallback: create a minimal VisionResult from fused data
            return self._evaluate_zones(
                fused.zone_min_dist, fused.obstacles
            )

        return self._evaluate_zones(
            fused.zone_min_dist, fused.obstacles
        )

    # ── Shared zone evaluation ────────────────────────────────────────────

    def _evaluate_zones(
        self, zone_min_dist: dict, obstacles: list
    ) -> MicroNavCommand:
        """
        Core reactive avoidance logic shared by update() and update_fused().

        Parameters
        ----------
        zone_min_dist : dict
            Mapping of ``{"left": float, "center": float, "right": float}``.
        obstacles : list
            Sequence of obstacle objects with ``.zone``, ``.distance_m``,
            and ``.label`` attributes.
        """
        cmd = MicroNavCommand()

        left_d = zone_min_dist["left"]
        center_d = zone_min_dist["center"]
        right_d = zone_min_dist["right"]

        # ── 1. ALL zones blocked at emergency distance → STOP ─────────────
        if (
            left_d < self._emergency
            and center_d < self._emergency
            and right_d < self._emergency
        ):
            cmd.action = "stop"
            cmd.urgency = 1.0
            cmd.speak_text = self._maybe_speak(
                "stop",
                "Path blocked — stopping.",
            )
            return cmd

        # ── 2. No obstacles within danger distance → ALL CLEAR ────────────
        closest = min(left_d, center_d, right_d)
        if closest > self._danger:
            cmd.action = "none"
            cmd.urgency = 0.0
            # Reset spoken state so next obstacle gets announced
            self._last_spoken_action = "none"
            return cmd

        # ── 3. CENTER blocked → steer to clearer side ─────────────────────
        if center_d < self._danger:
            # Find the closest centre obstacle label for the TTS message
            center_label = self._closest_label_in_list(obstacles, "center")

            if left_d >= right_d:
                cmd.action = "steer_left"
                cmd.speak_text = self._maybe_speak(
                    "steer_left",
                    f"Obstacle ahead — steering left to avoid {center_label}.",
                )
            else:
                cmd.action = "steer_right"
                cmd.speak_text = self._maybe_speak(
                    "steer_right",
                    f"Obstacle ahead — steering right to avoid {center_label}.",
                )
            cmd.urgency = self._compute_urgency(center_d)
            return cmd

        # ── 4. LEFT blocked → steer right ────────────────────────────────
        if left_d < self._danger:
            left_label = self._closest_label_in_list(obstacles, "left")
            cmd.action = "steer_right"
            cmd.urgency = self._compute_urgency(left_d)
            cmd.speak_text = self._maybe_speak(
                "steer_right",
                f"Obstacle on left — steering right to avoid {left_label}.",
            )
            return cmd

        # ── 5. RIGHT blocked → steer left ────────────────────────────────
        if right_d < self._danger:
            right_label = self._closest_label_in_list(obstacles, "right")
            cmd.action = "steer_left"
            cmd.urgency = self._compute_urgency(right_d)
            cmd.speak_text = self._maybe_speak(
                "steer_left",
                f"Obstacle on right — steering left to avoid {right_label}.",
            )
            return cmd

        # Fallback (shouldn't be reached)
        cmd.action = "none"
        return cmd

    # ── Helpers ───────────────────────────────────────────────────────────

    def _compute_urgency(self, distance: float) -> float:
        """
        Map a distance to an urgency value in [0, 1].
        At danger threshold → 0, at emergency threshold → 1.
        """
        if distance >= self._danger:
            return 0.0
        if distance <= self._emergency:
            return 1.0
        span = self._danger - self._emergency
        if span < 0.01:
            return 1.0
        return 1.0 - (distance - self._emergency) / span

    def _maybe_speak(self, action: str, text: str) -> str:
        """
        Return *text* only if the action has changed since last speak.
        Prevents the same message from being sent every frame (~200 ms).
        """
        if action != self._last_spoken_action:
            self._last_spoken_action = action
            return text
        return ""

    @staticmethod
    def _closest_label_in_zone(vr: VisionResult, zone: str) -> str:
        """Find the label of the closest obstacle in a given zone."""
        return MicroNavigator._closest_label_in_list(vr.obstacles, zone)

    @staticmethod
    def _closest_label_in_list(obstacles: list, zone: str) -> str:
        """Find the label of the closest obstacle in a given zone."""
        best_dist = float("inf")
        best_label = "an obstacle"
        for obs in obstacles:
            obs_zone = getattr(obs, "zone", None) or (obs.get("zone") if isinstance(obs, dict) else None)
            obs_dist = getattr(obs, "distance_m", None) or (obs.get("dist") if isinstance(obs, dict) else float("inf"))
            obs_label = getattr(obs, "label", "obstacle") if not isinstance(obs, dict) else obs.get("label", "obstacle")
            if obs_zone == zone and obs_dist < best_dist:
                best_dist = obs_dist
                best_label = f"a {obs_label}"
        return best_label
