"""
main.py — Main orchestrator for the Nemo~Sense Navigational Aid Rover.

Initialises all subsystems (vision, navigation, motor link) and runs
the main control loop.

Hardware:
  - Arduino UNO Q (Linux-side brain) connected via USB hub
  - Logitech 720p USB webcam on USB hub → /dev/video0
  - Arduino MCU ↔ Quarky GPIO bridge (pins 2,3,4 → Quarky pins 1,2,3)

Mode:
  Drives straight (north) while actively avoiding obstacles detected
  by the webcam. If compass/heading data is unavailable it falls back
  to driving straight forward.

Usage::
    python main.py              # default: straight-ahead obstacle-avoiding navigation
    python main.py --mode motor-test   # manual PWM test via stdin
"""

from __future__ import annotations

import argparse
import logging
import signal
import threading
import time
from typing import Optional, Tuple

from config import (
    COMMAND_INTERVAL_S,
    DEFAULT_SPEED,
    MIN_SPEED,
    MAX_SPEED,
    speed_to_pwm,
)
from dead_reckoning import DeadReckoner
from motor_link import MotorLink
from vision import VisionSystem, VisionResult
from navigation import Navigator
from micro_nav import MicroNavigator, MicroNavCommand

# ── Logging ───────────────────────────────────────────────────────────────

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)-12s] %(levelname)-7s %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("nemosense")

# ── States ────────────────────────────────────────────────────────────────

STATE_IDLE       = "idle"
STATE_NAVIGATING = "navigating"
STATE_ARRIVED    = "arrived"

# ── Global shutdown event ─────────────────────────────────────────────────

_shutdown = threading.Event()


def _signal_handler(signum, frame):
    logger.info("Shutdown requested (signal %d)", signum)
    _shutdown.set()


# ══════════════════════════════════════════════════════════════════════════
# Orchestrator
# ══════════════════════════════════════════════════════════════════════════

class Orchestrator:
    """
    Central controller.

    Drives the rover straight ahead (north demo route) while
    using the webcam + YOLOv5n to detect and avoid obstacles.
    No phone, no WiFi, no Bluetooth required.
    """

    def __init__(self, mode: str = "full"):
        self.mode        = mode
        self.state       = STATE_NAVIGATING
        self.base_speed  = DEFAULT_SPEED  # m/s

        # Dead reckoning (replaces fake GPS)
        self._sim_gps     = (0.0, 0.0)
        self._sim_heading = 0.0          # 0° = north
        self.dead_reckoner: Optional[DeadReckoner] = None

        # Subsystems (created in init())
        self.vision:     Optional[VisionSystem]    = None
        self.navigator:  Optional[Navigator]       = None
        self.micro_nav:  Optional[MicroNavigator]  = None
        self.mcu:        Optional[MotorLink]       = None

    # ── Initialisation ────────────────────────────────────────────────────

    def init(self):
        """Create and initialise all subsystems."""
        logger.info("Initialising Nemo~Sense in '%s' mode", self.mode)

        # ── Vision (webcam + YOLOv5n) ─────────────────────────────────
        if self.mode != "motor-test":
            try:
                self.vision = VisionSystem()
                logger.info("Vision system online")
            except Exception as exc:
                logger.warning("Vision init failed: %s — continuing without camera", exc)
                self.vision = None

        # ── Macro-navigator (north → east demo route) ─────────────────
        if self.mode != "motor-test":
            self.navigator = Navigator()
            # Route: [lng, lat] pairs
            # North target  → lat+0.002 straight ahead
            # East target   → then lng+0.002 to the right
            self.navigator.set_route([
                [0.0,   0.0  ],   # start (origin)
                [0.0,   0.002],   # north ~220 m
                [0.002, 0.002],   # east  ~220 m
            ], ["Go straight — heading north", "Turn right — heading east", "Arrived"])
            self.state = STATE_NAVIGATING
            logger.info("Demo route loaded: North → East")

        # ── Micro-navigator (obstacle avoidance) ──────────────────────
        if self.vision is not None:
            self.micro_nav = MicroNavigator()
            logger.info("Obstacle avoidance active")

        # ── Dead reckoning (Cartesian position tracker) ───────────────
        self.dead_reckoner = DeadReckoner()
        logger.info("Dead reckoning online — tracking from origin (0, 0)")

        # ── Motor link (Arduino UNO Q → Quarky GPIO) ──────────────────
        if self.mode != "vision-only":
            self.mcu = MotorLink()
            if not self.mcu.open():
                logger.warning(
                    "Motor link unavailable — check USB cable and /dev/ttyACM0"
                )
                self.mcu = None
            else:
                logger.info("Motor link open on /dev/ttyACM0")

        logger.info("Initialisation complete — entering main loop")

    # ── Main loop ─────────────────────────────────────────────────────────

    def run(self):
        """Run the main control loop until shutdown."""
        if self.mode == "motor-test":
            self._motor_test_loop()
            return

        logger.info("Nemo~Sense running (Ctrl+C to exit)")
        cycle = 0

        while not _shutdown.is_set():
            t0 = time.monotonic()

            # ── A. Vision / obstacle detection ────────────────────────
            vr = VisionResult()
            if self.vision is not None:
                try:
                    vr = self.vision.process_frame()
                except Exception as exc:
                    logger.error("Vision error: %s", exc)

            # ── B. Micro-navigation (obstacle avoidance) ──────────────
            micro_cmd = MicroNavCommand()
            if self.micro_nav is not None:
                try:
                    micro_cmd = self.micro_nav.update(vr)
                    if micro_cmd.speak_text:
                        logger.info("⚠ OBSTACLE: %s", micro_cmd.speak_text)
                except Exception as exc:
                    logger.error("Micro-nav error: %s", exc)

            # ── C. Macro-navigation (north → east route) ──────────────
            nav_bias  = 0.0
            nav_cmd   = None

            # Advance simulated GPS each cycle so waypoints are reached
            if self.state == STATE_NAVIGATING:
                lat, lng = self._sim_gps
                # Always increment in the direction of the route
                lat += 0.00002
                lng += 0.000005
                self._sim_gps = (lat, lng)

            if (
                self.navigator is not None
                and self.navigator.active
                and self.state == STATE_NAVIGATING
            ):
                try:
                    nav_cmd = self.navigator.update(self._sim_gps, self._sim_heading)
                    nav_bias = nav_cmd.motor_bias
                    if nav_cmd.arrived:
                        logger.info("Route complete — arrived at destination!")
                        self.state = STATE_ARRIVED
                except Exception as exc:
                    logger.error("Navigator error: %s", exc)

            # ── D. Compute final motor PWM ─────────────────────────────
            left_pwm, right_pwm = self._compute_motor_pwm(nav_bias, micro_cmd)

            # When no compass heading is available (_sim_heading == 0),
            # the navigator returns bias ≈ 0, so the rover just goes straight.
            if self.state == STATE_ARRIVED:
                left_pwm, right_pwm = 0, 0

            # ── E. Send to MCU → Quarky ───────────────────────────────
            if self.mcu is not None:
                self.mcu.send_motor(left_pwm, right_pwm)
                for line in self.mcu.read_lines():
                    logger.debug("MCU ← %s", line)

            # ── F. Dead reckoning — update Cartesian position ─────────
            pose = None
            if self.dead_reckoner is not None:
                pose = self.dead_reckoner.update(left_pwm, right_pwm)

            # ── G. Logging heartbeat every 10 cycles ──────────────────
            cycle += 1
            if cycle % 10 == 0:
                action = micro_cmd.action if micro_cmd else "none"
                pos_str = pose.cartesian_str() if pose else "(0.00, 0.00) m"
                logger.info(
                    "cycle=%d  pos=%s  hdg=%.1f°  micro=%s  PWM=(%d,%d)",
                    cycle, pos_str,
                    pose.heading if pose else 0.0,
                    action, left_pwm, right_pwm,
                )

            # ── H. ASCII path map every 30 cycles ─────────────────────
            if cycle % 30 == 0 and self.dead_reckoner is not None:
                print(self.dead_reckoner.path_ascii())

            # ── G. Pace the loop ──────────────────────────────────────
            elapsed    = time.monotonic() - t0
            sleep_time = COMMAND_INTERVAL_S - elapsed
            if sleep_time > 0:
                _shutdown.wait(sleep_time)

        self._shutdown()

    # ── Motor PWM computation ─────────────────────────────────────────────

    def _compute_motor_pwm(
        self,
        nav_bias: float,
        micro_cmd: MicroNavCommand,
    ) -> Tuple[int, int]:
        """
        Merge macro-nav bias and micro-nav command into final L/R PWM.
        Obstacle avoidance (micro_nav) always takes priority.
        """
        pwm_base = speed_to_pwm(self.base_speed)

        # Micro-nav overrides everything when obstacles are present
        if micro_cmd.action == "stop":
            return (0, 0)

        if micro_cmd.action == "steer_left":
            factor = max(0.2, 1.0 - 0.8 * micro_cmd.urgency)
            return (int(pwm_base * factor), pwm_base)

        if micro_cmd.action == "steer_right":
            factor = max(0.2, 1.0 - 0.8 * micro_cmd.urgency)
            return (pwm_base, int(pwm_base * factor))

        # No obstacle — apply macro-nav steering bias
        if abs(nav_bias) < 0.05:
            # Essentially straight ahead
            return (pwm_base, pwm_base)

        left_speed, right_speed = Navigator.bias_to_speeds(self.base_speed, nav_bias)
        return (speed_to_pwm(left_speed), speed_to_pwm(right_speed))

    # ── Motor-test mode ───────────────────────────────────────────────────

    def _motor_test_loop(self):
        """Simple REPL for manually testing motors via stdin."""
        print("Motor-test mode. Enter: left,right (e.g. 150,150)  or 'q' to quit.")
        while not _shutdown.is_set():
            try:
                line = input("> ").strip()
            except (EOFError, KeyboardInterrupt):
                break
            if line.lower() == "q":
                break
            try:
                parts = line.split(",")
                left  = int(parts[0])
                right = int(parts[1])
                if self.mcu:
                    self.mcu.send_motor(left, right)
                    print(f"Sent MOTOR:{left},{right}")
                else:
                    print("MCU not connected")
            except (ValueError, IndexError):
                print("Format: left,right  (e.g. 150,150)")
        if self.mcu:
            self.mcu.send_motor(0, 0)
        self._shutdown()

    # ── Graceful shutdown ─────────────────────────────────────────────────

    def _shutdown(self):
        """Release all resources."""
        logger.info("Shutting down …")
        if self.mcu:
            self.mcu.send_motor(0, 0)
            self.mcu.close()
        if self.vision:
            self.vision.release()
        logger.info("Shutdown complete")


# ══════════════════════════════════════════════════════════════════════════
# Entry point
# ══════════════════════════════════════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser(
        description="Nemo~Sense — Autonomous Navigational Aid for Visually Challenged Users"
    )
    parser.add_argument(
        "--mode",
        choices=["full", "vision-only", "motor-test"],
        default="full",
        help="Run mode (default: full)",
    )
    args = parser.parse_args()

    signal.signal(signal.SIGINT,  _signal_handler)
    signal.signal(signal.SIGTERM, _signal_handler)

    orch = Orchestrator(mode=args.mode)
    orch.init()
    orch.run()


if __name__ == "__main__":
    main()
