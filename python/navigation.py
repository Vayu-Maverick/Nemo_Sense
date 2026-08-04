"""
navigation.py — Macro-level GPS waypoint navigation for the Netra rover.

Receives a route (list of [lng, lat] waypoints and text instructions) from
the phone, tracks progress, and produces a differential motor bias to steer
the rover toward each successive waypoint.
"""

from __future__ import annotations

import logging
import math
from dataclasses import dataclass
from typing import List, Optional, Tuple

from config import WAYPOINT_REACHED_RADIUS_M, EARTH_RADIUS_M

logger = logging.getLogger(__name__)


@dataclass
class NavigationCommand:
    """Output of one navigation update cycle."""
    motor_bias: float = 0.0       # -1.0 (hard left) … 0.0 (straight) … +1.0 (hard right)
    next_instruction: str = ""    # human-readable turn instruction
    distance_to_next: float = 0.0 # metres to the next waypoint
    arrived: bool = False         # True when entire route is done


class Navigator:
    """
    GPS waypoint follower.

    Usage::

        nav = Navigator()
        nav.set_route(
            waypoints=[[72.57, 23.02], [72.58, 23.03]],
            instructions=["Head north", "Turn right"],
        )
        cmd = nav.update(current_gps=(23.022, 72.571), current_heading=90.0)
    """

    def __init__(self, waypoint_radius: float = WAYPOINT_REACHED_RADIUS_M):
        self._waypoints: List[Tuple[float, float]] = []   # (lat, lng)
        self._instructions: List[str] = []
        self._current_idx: int = 0
        self._active: bool = False
        self._waypoint_radius = waypoint_radius

    # ── Route management ──────────────────────────────────────────────────

    def set_route(
        self,
        waypoints: List[List[float]],
        instructions: Optional[List[str]] = None,
    ):
        """
        Set a new route.

        Parameters
        ----------
        waypoints : list of [lng, lat]
            Ordered list of waypoints.  Note: the phone sends [lng, lat].
        instructions : list of str, optional
            Human-readable turn-by-turn instructions (one per waypoint).
        """
        # Convert [lng, lat] → (lat, lng) internally for haversine
        self._waypoints = [(wp[1], wp[0]) for wp in waypoints]
        self._instructions = instructions or [""] * len(self._waypoints)
        # Pad instructions if fewer than waypoints
        while len(self._instructions) < len(self._waypoints):
            self._instructions.append("")
        self._current_idx = 0
        self._active = True
        logger.info(
            "Route set: %d waypoints, starting at index 0", len(self._waypoints)
        )

    def clear_route(self):
        """Cancel the current route."""
        self._waypoints.clear()
        self._instructions.clear()
        self._current_idx = 0
        self._active = False

    @property
    def active(self) -> bool:
        return self._active and len(self._waypoints) > 0

    # ── Haversine helpers ─────────────────────────────────────────────────

    @staticmethod
    def calculate_distance(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
        """
        Haversine distance in metres between two (lat, lng) points.
        """
        rlat1 = math.radians(lat1)
        rlat2 = math.radians(lat2)
        dlat = math.radians(lat2 - lat1)
        dlng = math.radians(lng2 - lng1)

        a = (
            math.sin(dlat / 2.0) ** 2
            + math.cos(rlat1) * math.cos(rlat2) * math.sin(dlng / 2.0) ** 2
        )
        c = 2.0 * math.atan2(math.sqrt(a), math.sqrt(1.0 - a))
        return EARTH_RADIUS_M * c

    @staticmethod
    def calculate_bearing(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
        """
        Initial bearing (degrees, 0 = north, clockwise) from point 1 → 2.
        """
        rlat1 = math.radians(lat1)
        rlat2 = math.radians(lat2)
        dlng = math.radians(lng2 - lng1)

        x = math.sin(dlng) * math.cos(rlat2)
        y = (
            math.cos(rlat1) * math.sin(rlat2)
            - math.sin(rlat1) * math.cos(rlat2) * math.cos(dlng)
        )
        bearing = math.degrees(math.atan2(x, y))
        return (bearing + 360.0) % 360.0

    # ── Core update ───────────────────────────────────────────────────────

    def update(
        self,
        current_gps: Tuple[float, float],
        current_heading: float,
    ) -> NavigationCommand:
        """
        Compute navigation command based on current position and compass
        heading.

        Parameters
        ----------
        current_gps : (lat, lng)
        current_heading : degrees, 0 = north, clockwise

        Returns
        -------
        NavigationCommand
        """
        cmd = NavigationCommand()

        if not self.active:
            cmd.arrived = True
            return cmd

        target_lat, target_lng = self._waypoints[self._current_idx]
        cur_lat, cur_lng = current_gps

        # Distance to current waypoint
        dist = self.calculate_distance(cur_lat, cur_lng, target_lat, target_lng)
        cmd.distance_to_next = round(dist, 1)

        # Check if waypoint is reached
        if dist <= self._waypoint_radius:
            logger.info(
                "Waypoint %d reached (%.1f m)", self._current_idx, dist
            )
            self._current_idx += 1
            if self._current_idx >= len(self._waypoints):
                # Entire route done
                self._active = False
                cmd.arrived = True
                cmd.next_instruction = "You have arrived."
                logger.info("Route complete — arrived at destination")
                return cmd
            # Recalculate for new target
            target_lat, target_lng = self._waypoints[self._current_idx]
            dist = self.calculate_distance(cur_lat, cur_lng, target_lat, target_lng)
            cmd.distance_to_next = round(dist, 1)

        # Instruction for current waypoint
        cmd.next_instruction = self._instructions[self._current_idx]

        # Desired bearing to waypoint
        desired_bearing = self.calculate_bearing(
            cur_lat, cur_lng, target_lat, target_lng
        )

        # Heading error: positive = target is to the right
        error = desired_bearing - current_heading
        # Normalise to [-180, 180]
        if error > 180.0:
            error -= 360.0
        elif error < -180.0:
            error += 360.0

        # Convert heading error to motor bias [-1, +1]
        # Clamp: ±90° or more → full turn
        bias = max(-1.0, min(1.0, error / 90.0))
        cmd.motor_bias = round(bias, 3)

        return cmd

    # ── Differential drive conversion (utility) ──────────────────────────

    @staticmethod
    def bias_to_speeds(
        base_speed: float, bias: float
    ) -> Tuple[float, float]:
        """
        Convert a base forward speed and a bias to (left, right) speeds.

        bias = 0   → straight
        bias > 0   → turn right  (slow right motor)
        bias < 0   → turn left   (slow left motor)

        Returns speeds in the same unit as *base_speed*.
        """
        left = base_speed * (1.0 - max(0.0, bias))
        right = base_speed * (1.0 + min(0.0, bias))
        return (left, right)
