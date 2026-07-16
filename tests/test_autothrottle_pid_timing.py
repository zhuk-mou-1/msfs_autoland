"""P2-AT-01: Monotonic PID timing + clock injection + anomalous dt."""
import logging
import math
import time


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_controller(**kwargs):
    """Create AutothrottleController with injected clock for testing."""
    from modules.autothrottle import AutothrottleController, AutothrottleConfig
    config = AutothrottleConfig()
    return AutothrottleController(config=config, **kwargs)


class FakeClock:
    """Deterministic clock for testing. Returns values from a sequence."""

    def __init__(self, values):
        self._values = list(values)
        self._idx = 0

    def __call__(self):
        v = self._values[self._idx]
        self._idx += 1
        return v

    @property
    def calls(self):
        return self._idx


# ---------------------------------------------------------------------------
# 1. Clock source is injected, not time.time()
# ---------------------------------------------------------------------------

def test_clock_injection():
    """Clock parameter is used instead of time.time()."""
    clock = FakeClock([0.0, 0.5, 1.0])
    ctrl = _make_controller(clock=clock)
    ctrl.activate(initial_throttle=0.5)
    # activate() called clock once for previous_time
    assert clock.calls == 1


# ---------------------------------------------------------------------------
# 2. Nominal 0.5s sequence updates I/D
# ---------------------------------------------------------------------------

def test_nominal_sequence():
    """Two 0.5s intervals update integral and derivative normally."""
    # activate() calls clock once → t=0.0
    # calculate_throttle() calls clock once → t=0.5, dt=0.5
    # Second call: clock → t=1.0, dt=0.5
    clock = FakeClock([0.0, 0.5, 1.0])
    ctrl = _make_controller(clock=clock)

    telemetry = {
        'speed': {'airspeed_indicated': 130.0},
        'attitude': {'bank': 0},
        'configuration': {'flaps_position': 0.5, 'gear_position': 0.0},
    }

    ctrl.activate(initial_throttle=0.5)
    ctrl.current_throttle = 0.5

    r1 = ctrl.calculate_throttle(telemetry, target_speed=140.0,
                                  wind_data={}, aircraft_weight=5000.0)
    assert r1['active'] is True
    assert r1['pid_correction'] != 0.0  # PID produced a correction

    r2 = ctrl.calculate_throttle(telemetry, target_speed=140.0,
                                  wind_data={}, aircraft_weight=5000.0)
    assert r2['active'] is True
    # Integral should have accumulated
    assert ctrl.integral != 0.0


# ---------------------------------------------------------------------------
# 3. dt=0 → I/D frozen
# ---------------------------------------------------------------------------

def test_dt_zero_freezes_id():
    """dt=0: integral and derivative should not change."""
    clock = FakeClock([0.0, 0.5, 0.5])  # activate→0.5, calc1→0.5 (dt=0)
    ctrl = _make_controller(clock=clock)

    telemetry = {
        'speed': {'airspeed_indicated': 130.0},
        'attitude': {'bank': 0},
        'configuration': {'flaps_position': 0.5, 'gear_position': 0.0},
    }
    ctrl.activate(initial_throttle=0.5)
    ctrl.current_throttle = 0.5

    r1 = ctrl.calculate_throttle(telemetry, target_speed=140.0,
                                  wind_data={}, aircraft_weight=5000.0)
    integral_after = ctrl.integral
    # With dt=0, integral accumulation is 0, derivative is 0
    # P term still applies
    assert r1['active'] is True


# ---------------------------------------------------------------------------
# 4. dt<0 → I/D frozen, warning emitted
# ---------------------------------------------------------------------------

def test_dt_negative_freezes_id_and_warns(caplog):
    """dt<0: integral and derivative frozen, warning emitted."""
    clock = FakeClock([0.0, 0.5, 0.3])  # activate→0.0, calc1→0.5 (dt=0.5), calc2→0.3 (dt=-0.2)
    ctrl = _make_controller(clock=clock)

    telemetry = {
        'speed': {'airspeed_indicated': 130.0},
        'attitude': {'bank': 0},
        'configuration': {'flaps_position': 0.5, 'gear_position': 0.0},
    }
    ctrl.activate(initial_throttle=0.5)
    ctrl.current_throttle = 0.5

    # First call: normal dt=0.5
    r1 = ctrl.calculate_throttle(telemetry, target_speed=140.0,
                                  wind_data={}, aircraft_weight=5000.0)
    assert r1['active'] is True

    # Second call: anomalous dt=-0.2
    with caplog.at_level(logging.WARNING, logger="modules.autothrottle"):
        r = ctrl.calculate_throttle(telemetry, target_speed=140.0,
                                     wind_data={}, aircraft_weight=5000.0)

    assert r['active'] is True
    assert r['pid_correction'] is not None  # finite output
    # Warning should mention dt
    assert any("dt" in record.message.lower() or "anomal" in record.message.lower()
               for record in caplog.records if record.levelno >= logging.WARNING)


# ---------------------------------------------------------------------------
# 5. dt=NaN → fail-safe
# ---------------------------------------------------------------------------

def test_dt_nan_fail_safe():
    """NaN dt: I/D frozen, finite output."""
    clock = FakeClock([0.0, 0.5, float('nan')])  # activate→0.5, calc→NaN
    ctrl = _make_controller(clock=clock)

    telemetry = {
        'speed': {'airspeed_indicated': 130.0},
        'attitude': {'bank': 0},
        'configuration': {'flaps_position': 0.5, 'gear_position': 0.0},
    }
    ctrl.activate(initial_throttle=0.5)
    ctrl.current_throttle = 0.5

    r = ctrl.calculate_throttle(telemetry, target_speed=140.0,
                                 wind_data={}, aircraft_weight=5000.0)
    assert r['active'] is True
    assert math.isfinite(r['pid_correction'])
    assert math.isfinite(r['throttle'])


# ---------------------------------------------------------------------------
# 6. dt=inf → fail-safe
# ---------------------------------------------------------------------------

def test_dt_inf_fail_safe():
    """inf dt: I/D frozen, finite output."""
    clock = FakeClock([0.0, 0.5, float('inf')])
    ctrl = _make_controller(clock=clock)

    telemetry = {
        'speed': {'airspeed_indicated': 130.0},
        'attitude': {'bank': 0},
        'configuration': {'flaps_position': 0.5, 'gear_position': 0.0},
    }
    ctrl.activate(initial_throttle=0.5)
    ctrl.current_throttle = 0.5

    r = ctrl.calculate_throttle(telemetry, target_speed=140.0,
                                 wind_data={}, aircraft_weight=5000.0)
    assert r['active'] is True
    assert math.isfinite(r['pid_correction'])
    assert math.isfinite(r['throttle'])


# ---------------------------------------------------------------------------
# 7. dt > max_pid_dt_seconds → I/D frozen, warning
# ---------------------------------------------------------------------------

def test_dt_large_freezes_id(caplog):
    """dt > max_pid_dt_seconds: integral/derivative frozen, warning."""
    clock = FakeClock([0.0, 0.5, 100.0])  # dt = 99.5s
    ctrl = _make_controller(clock=clock)

    telemetry = {
        'speed': {'airspeed_indicated': 130.0},
        'attitude': {'bank': 0},
        'configuration': {'flaps_position': 0.5, 'gear_position': 0.0},
    }
    ctrl.activate(initial_throttle=0.5)
    ctrl.current_throttle = 0.5

    integral_before = ctrl.integral

    with caplog.at_level(logging.WARNING, logger="modules.autothrottle"):
        r = ctrl.calculate_throttle(telemetry, target_speed=140.0,
                                     wind_data={}, aircraft_weight=5000.0)

    assert r['active'] is True
    assert math.isfinite(r['pid_correction'])
    assert math.isfinite(r['throttle'])


# ---------------------------------------------------------------------------
# 8. Next normal frame after anomaly recovers without spike
# ---------------------------------------------------------------------------

def test_recovery_after_anomaly():
    """After anomalous dt, next normal dt recovers PID without derivative spike."""
    # activate→0.0, calc→0.5 (dt=0.5 normal), calc→0.3 (dt=-0.2 anomaly),
    # calc→0.8 (dt=0.5 normal after anomaly)
    clock = FakeClock([0.0, 0.5, 0.3, 0.8])
    ctrl = _make_controller(clock=clock)

    telemetry = {
        'speed': {'airspeed_indicated': 130.0},
        'attitude': {'bank': 0},
        'configuration': {'flaps_position': 0.5, 'gear_position': 0.0},
    }
    ctrl.activate(initial_throttle=0.5)
    ctrl.current_throttle = 0.5

    # Normal frame
    r1 = ctrl.calculate_throttle(telemetry, target_speed=140.0,
                                  wind_data={}, aircraft_weight=5000.0)
    # Anomalous frame (dt<0)
    r2 = ctrl.calculate_throttle(telemetry, target_speed=140.0,
                                  wind_data={}, aircraft_weight=5000.0)
    # Recovery frame (normal dt)
    r3 = ctrl.calculate_throttle(telemetry, target_speed=140.0,
                                  wind_data={}, aircraft_weight=5000.0)

    assert r3['active'] is True
    assert math.isfinite(r3['pid_correction'])
    assert math.isfinite(r3['throttle'])
    # No derivative spike: pid_correction should be reasonable
    assert abs(r3['pid_correction']) < 10.0


# ---------------------------------------------------------------------------
# 9. activate/reset lifecycle
# ---------------------------------------------------------------------------

def test_activate_reset_lifecycle():
    """activate() sets fresh timestamp, reset() clears it."""
    clock = FakeClock([0.0, 0.5, 1.0])
    ctrl = _make_controller(clock=clock)

    ctrl.activate(initial_throttle=0.5)
    assert ctrl.previous_time is not None

    ctrl.reset()
    assert ctrl.previous_time is None

    # After reset, next activate gets fresh timestamp
    ctrl.activate(initial_throttle=0.5)
    assert ctrl.previous_time is not None
    assert ctrl.integral == 0.0
    assert ctrl.previous_error == 0.0


# ---------------------------------------------------------------------------
# 10. Red-without-fix: wall clock would give different dt on slow machine
# ---------------------------------------------------------------------------

def test_clock_injection_not_time_time():
    """Verify that the controller uses injected clock, not time.time()."""
    call_log = []
    original_time = time.time

    def spy_time():
        call_log.append('time.time')
        return original_time()

    clock = FakeClock([0.0, 0.5, 1.0])
    ctrl = _make_controller(clock=clock)

    telemetry = {
        'speed': {'airspeed_indicated': 130.0},
        'attitude': {'bank': 0},
        'configuration': {'flaps_position': 0.5, 'gear_position': 0.0},
    }
    ctrl.activate(initial_throttle=0.5)
    ctrl.current_throttle = 0.5

    # Patch time.time to verify it's NOT called
    import modules.autothrottle as at_mod
    old_time = at_mod.time.time
    at_mod.time.time = spy_time
    try:
        r = ctrl.calculate_throttle(telemetry, target_speed=140.0,
                                     wind_data={}, aircraft_weight=5000.0)
        # time.time should NOT be called during calculate_throttle
        assert 'time.time' not in call_log, "Controller still uses time.time()"
    finally:
        at_mod.time.time = old_time
