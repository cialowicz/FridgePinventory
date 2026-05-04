"""Motion-detection state machine extracted from main.run for testability.

The state machine has three modes:
  - active   : a recent motion event keeps us reacting quickly
  - tracking : motion has stopped but we're still polling at normal cadence
  - idle     : extended inactivity, slow polling

Caller drives the loop by calling step() with the current time and the
motion-sensor reading. step() returns a Decision describing what to do.
"""

import math
from dataclasses import dataclass
from typing import Optional


ACTIVE = "active"
TRACKING = "tracking"
IDLE = "idle"


@dataclass
class Decision:
    new_motion: bool                # True if this step crossed inactive -> active
    sleep_seconds: float
    enter_idle: bool                # True if this step crossed tracking -> idle


class MotionLoop:
    def __init__(self, *,
                 motion_check_interval: float,
                 idle_delay: float,
                 active_delay: float,
                 cooldown_seconds: float = 2.0,
                 idle_after_seconds: float = 30.0,
                 deactivate_after_misses: int = 5) -> None:
        self.motion_check_interval = motion_check_interval
        self.idle_delay = idle_delay
        self.active_delay = active_delay
        self.cooldown_seconds = cooldown_seconds
        self.idle_after_seconds = idle_after_seconds
        self.deactivate_after_misses = deactivate_after_misses

        self.mode: str = TRACKING
        self.consecutive_misses: int = 0
        self.last_motion_time: Optional[float] = None
        self.last_check_time: float = -math.inf

    def _check_interval(self) -> float:
        return self.idle_delay if self.mode == IDLE else self.motion_check_interval

    def step(self, now: float, read_motion) -> Decision:
        """Advance the state machine one tick. read_motion is a callable
        returning bool — it is invoked at most once per step()."""
        if (now - self.last_check_time) < self._check_interval():
            sleep_seconds = (
                self.active_delay if self.mode == ACTIVE else self._check_interval()
            )
            return Decision(
                new_motion=False,
                sleep_seconds=sleep_seconds,
                enter_idle=False,
            )

        self.last_check_time = now
        in_cooldown = (self.last_motion_time is not None
                       and (now - self.last_motion_time) <= self.cooldown_seconds)
        motion = False if in_cooldown else bool(read_motion())

        if motion:
            new_motion = self.mode != ACTIVE
            self.mode = ACTIVE
            self.consecutive_misses = 0
            self.last_motion_time = now
            return Decision(new_motion=new_motion,
                            sleep_seconds=self.active_delay,
                            enter_idle=False)

        enter_idle = False
        if self.mode == ACTIVE:
            self.consecutive_misses += 1
            if self.consecutive_misses >= self.deactivate_after_misses:
                self.mode = TRACKING
                self.consecutive_misses = 0
        elif self.mode == TRACKING:
            if (self.last_motion_time is None
                    or (now - self.last_motion_time) > self.idle_after_seconds):
                self.mode = IDLE
                enter_idle = True

        sleep_seconds = (self.active_delay if self.mode == ACTIVE
                         else self.idle_delay if self.mode == IDLE
                         else self.motion_check_interval)
        return Decision(new_motion=False, sleep_seconds=sleep_seconds, enter_idle=enter_idle)
