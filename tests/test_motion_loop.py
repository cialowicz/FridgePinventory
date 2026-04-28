"""Unit tests for the MotionLoop state machine with a fake clock."""

from pi_inventory_system.motion_loop import ACTIVE, IDLE, TRACKING, MotionLoop


def make_loop(**overrides):
    defaults = dict(
        motion_check_interval=0.5,
        idle_delay=1.0,
        active_delay=0.1,
        cooldown_seconds=2.0,
        idle_after_seconds=10.0,
        deactivate_after_misses=3,
    )
    defaults.update(overrides)
    return MotionLoop(**defaults)


def test_motion_transitions_inactive_to_active():
    loop = make_loop()
    decision = loop.step(now=1.0, read_motion=lambda: True)
    assert decision.new_motion is True
    assert loop.mode == ACTIVE


def test_motion_loss_transitions_active_to_tracking():
    loop = make_loop(deactivate_after_misses=2)
    loop.step(now=1.0, read_motion=lambda: True)
    loop.step(now=2.0, read_motion=lambda: False)  # cooldown still active
    loop.step(now=4.0, read_motion=lambda: False)  # first miss
    loop.step(now=5.0, read_motion=lambda: False)  # second miss → tracking
    assert loop.mode == TRACKING


def test_idle_transition_after_inactivity():
    loop = make_loop(idle_after_seconds=5.0, deactivate_after_misses=1)
    loop.step(now=0.0, read_motion=lambda: True)
    loop.step(now=3.0, read_motion=lambda: False)  # cooldown
    loop.step(now=4.0, read_motion=lambda: False)  # active -> tracking
    decision = loop.step(now=20.0, read_motion=lambda: False)
    assert loop.mode == IDLE
    assert decision.enter_idle is True


def test_throttled_when_check_interval_not_elapsed():
    loop = make_loop()
    loop.step(now=1.0, read_motion=lambda: False)
    calls = []
    loop.step(now=1.1, read_motion=lambda: calls.append(1) or False)
    assert calls == []  # not yet time for another sensor read


def test_cooldown_blocks_repeated_reads():
    loop = make_loop(cooldown_seconds=2.0)
    loop.step(now=1.0, read_motion=lambda: True)
    calls = []
    loop.step(now=2.0, read_motion=lambda: calls.append(1) or True)
    assert calls == []  # cooldown should suppress sensor read


def test_repeated_motion_does_not_re_signal_new_motion():
    loop = make_loop(cooldown_seconds=0.0)
    first = loop.step(now=1.0, read_motion=lambda: True)
    second = loop.step(now=2.0, read_motion=lambda: True)
    assert first.new_motion is True
    assert second.new_motion is False
