"""
Tests for P0 safety fixes: A-DISP-1, A-CONF-1, A-CONF-4, B-AT-1.

A-DISP-1: SimConnect event dispatch compatibility
A-CONF-1: Flaps via discrete events (FLAPS_UP/1/2/3)
A-CONF-4: Deterministic AP_VS_ON (not toggle AP_VS_HOLD)
B-AT-1:   Continuous flaps fraction in autothrottle
"""

import pytest
from unittest.mock import MagicMock

from modules.control import MSFSControl, SDK_ONLY_EVENTS
from modules.autothrottle import AutothrottleController, AutothrottleConfig


# ── Shared execution trace ───────────────────────────────────────
# Both FakeEvent (catalogued) and RecordingEvent (SDK-only) append
# to this list so we can verify cross-type execution order.

NO_ARG = object()
_trace: list[tuple[str, object]] = []


def reset_trace():
    _trace.clear()


# ── FakeEvents: models real AircraftEvents API (find + callable) ──


class FakeEvent:
    """Simulates SimConnect.EventList.Event — callable, records calls."""

    def __init__(self, name: str):
        self.name = name
        self.calls: list = []

    def __call__(self, value=None):
        self.calls.append(value)
        _trace.append((self.name, NO_ARG if value is None else value))


class FakeAircraftEvents:
    """Simulates real AircraftEvents: find() returns callable Event objects.

    Does NOT have .event() method — matching real SimConnect v0.4.26 API.
    """

    def __init__(self, catalog: dict[str, FakeEvent] | None = None):
        self._catalog: dict[str, FakeEvent] = catalog or {}
        self.sm = MagicMock()  # for SDK-only Event construction
        self.find_calls: list[str] = []

    def find(self, name: str):
        self.find_calls.append(name)
        return self._catalog.get(name)


def _make_ae_with_catalog(event_names: list[str]) -> FakeAircraftEvents:
    """Create FakeAircraftEvents with a catalog of named FakeEvents."""
    catalog = {name: FakeEvent(name) for name in event_names}
    return FakeAircraftEvents(catalog)


# ── Recording fake for dynamic Event (BLOCKER 2) ────────────────

_SENTINEL = object()


class RecordingEvent:
    """Recording stand-in for SimConnect.EventList.Event.

    Tracks constructor args, individual calls (no-arg vs explicit),
    and call values for verifying execution order with catalogued events.
    """

    _instances: list["RecordingEvent"] = []

    def __init__(self, deff, sm, _dec=""):
        self.deff = deff
        self.sm = sm
        self._dec = _dec
        self.call_count = 0
        self.call_values: list = []
        self.noarg_calls = 0
        RecordingEvent._instances.append(self)

    def __call__(self, value=_SENTINEL):
        self.call_count += 1
        name = self.deff.decode("ascii") if isinstance(self.deff, bytes) else self.deff
        if value is _SENTINEL:
            self.noarg_calls += 1
            self.call_values.append(None)
            _trace.append((name, NO_ARG))
        else:
            self.call_values.append(value)
            _trace.append((name, value))

    @classmethod
    def reset(cls):
        cls._instances.clear()


# ── A-DISP-1: dispatcher tests ──────────────────────────────────


class TestADISP1Dispatcher:
    """A-DISP-1: SimConnect event dispatch via find() + SDK-only fallback."""

    def test_catalogued_event_no_param(self):
        """Catalogued event called without parameter."""
        ae = _make_ae_with_catalog(["GEAR_DOWN"])
        ctrl = MSFSControl(ae)
        ctrl._send_event("GEAR_DOWN")
        assert ae._catalog["GEAR_DOWN"].calls == [None]

    def test_catalogued_event_with_param(self):
        """Catalogued event called with value."""
        ae = _make_ae_with_catalog(["THROTTLE_SET"])
        ctrl = MSFSControl(ae)
        ctrl._send_event("THROTTLE_SET", 8192)
        assert ae._catalog["THROTTLE_SET"].calls == [8192]

    def test_explicit_zero_not_noarg(self):
        """Explicit parameter 0 does not become no-arg call."""
        ae = _make_ae_with_catalog(["FLAPS_UP"])
        ctrl = MSFSControl(ae)
        ctrl._send_event("FLAPS_UP", 0)
        assert ae._catalog["FLAPS_UP"].calls == [0]

    def test_unknown_non_allowlisted_raises(self):
        """Unknown event not in allowlist → ValueError, no low-level call."""
        ae = FakeAircraftEvents({})
        ctrl = MSFSControl(ae)
        with pytest.raises(ValueError, match="Unknown SimConnect event"):
            ctrl._send_event("TYPO_EVENT")
        assert ae.sm.send_event.called is False

    def test_non_callable_find_result(self):
        """find() returns non-callable → TypeError."""
        ae = FakeAircraftEvents({"BROKEN": "not_callable"})
        ctrl = MSFSControl(ae)
        with pytest.raises(TypeError, match="is not callable"):
            ctrl._send_event("BROKEN")

    def test_sdk_only_event_creates_and_calls(self, monkeypatch):
        """AP_VS_ON: find() returns None, Event created, called without arg."""
        RecordingEvent.reset()
        monkeypatch.setattr("modules.control.Event", RecordingEvent)
        ae = FakeAircraftEvents({})
        ctrl = MSFSControl(ae)
        ctrl._send_event("AP_VS_ON")
        # Event was created and cached
        assert "AP_VS_ON" in ctrl._dynamic_events
        event = ctrl._dynamic_events["AP_VS_ON"]
        assert event.deff == b"AP_VS_ON"
        assert event.call_count == 1
        assert event.noarg_calls == 1

    def test_sdk_only_event_cached(self, monkeypatch):
        """SDK-only event: second call reuses cached Event (1 constructor, 2 calls)."""
        RecordingEvent.reset()
        monkeypatch.setattr("modules.control.Event", RecordingEvent)
        ae = FakeAircraftEvents({})
        ctrl = MSFSControl(ae)
        ctrl._send_event("AP_VS_ON")
        first_event = ctrl._dynamic_events["AP_VS_ON"]
        ctrl._send_event("AP_VS_ON")
        assert ctrl._dynamic_events["AP_VS_ON"] is first_event
        assert len(RecordingEvent._instances) == 1
        assert first_event.call_count == 2

    def test_sdk_only_no_sm_raises(self):
        """SDK-only fallback without ae.sm → RuntimeError."""
        ae = FakeAircraftEvents({})
        ae.sm = None
        ctrl = MSFSControl(ae)
        with pytest.raises(RuntimeError, match="AircraftEvents.sm unavailable"):
            ctrl._send_event("AP_VS_ON")

    def test_no_test_depends_on_event_method(self):
        """Verify FakeAircraftEvents does not have .event() method."""
        ae = FakeAircraftEvents({})
        assert not hasattr(ae, "event") or not callable(getattr(ae, "event", None))


# ── A-CONF-1: flaps discrete events ─────────────────────────────


class TestACONF1Flaps:
    """A-CONF-1: Flaps set via discrete events, not FLAPS_SET."""

    @pytest.mark.parametrize("position,event_name", [
        (0, "FLAPS_UP"),
        (1, "FLAPS_1"),
        (2, "FLAPS_2"),
        (3, "FLAPS_3"),
    ])
    def test_discrete_event_mapping(self, position, event_name):
        ae = _make_ae_with_catalog(["FLAPS_UP", "FLAPS_1", "FLAPS_2", "FLAPS_3"])
        ctrl = MSFSControl(ae)
        ctrl.set_flaps(position)
        assert ae._catalog[event_name].calls == [None]
        assert ae.find_calls[-1] == event_name

    def test_flaps_no_param(self):
        """Flaps events are called without parameter."""
        ae = _make_ae_with_catalog(["FLAPS_UP", "FLAPS_1", "FLAPS_2", "FLAPS_3"])
        ctrl = MSFSControl(ae)
        ctrl.set_flaps(2)
        assert ae._catalog["FLAPS_2"].calls == [None]

    def test_flaps_clamp_below(self):
        """Position < 0 clamps to 0 (FLAPS_UP)."""
        ae = _make_ae_with_catalog(["FLAPS_UP", "FLAPS_1", "FLAPS_2", "FLAPS_3"])
        ctrl = MSFSControl(ae)
        ctrl.set_flaps(-1)
        assert ae._catalog["FLAPS_UP"].calls == [None]

    def test_flaps_clamp_above(self):
        """Position > 3 clamps to 3 (FLAPS_3)."""
        ae = _make_ae_with_catalog(["FLAPS_UP", "FLAPS_1", "FLAPS_2", "FLAPS_3"])
        ctrl = MSFSControl(ae)
        ctrl.set_flaps(99)
        assert ae._catalog["FLAPS_3"].calls == [None]

    def test_flaps_set_not_called(self):
        """FLAPS_SET must NOT be called."""
        ae = _make_ae_with_catalog(["FLAPS_UP", "FLAPS_1", "FLAPS_2", "FLAPS_3", "FLAPS_SET"])
        ctrl = MSFSControl(ae)
        ctrl.set_flaps(2)
        assert ae._catalog["FLAPS_SET"].calls == []


# ── A-CONF-4: deterministic VS ──────────────────────────────────


class TestACONF4VerticalSpeed:
    """A-CONF-4: AP_VS_ON (deterministic), not AP_VS_HOLD (toggle)."""

    def test_vs_sdk_only_path(self, monkeypatch):
        """set_vertical_speed: AP_VS_ON is SDK-only (not in catalog),
        dynamic Event created and called without param, then catalogued
        AP_VS_VAR_SET_ENGLISH called with 1500.
        """
        RecordingEvent.reset()
        reset_trace()
        monkeypatch.setattr("modules.control.Event", RecordingEvent)
        # Catalog has AP_VS_VAR_SET_ENGLISH but NOT AP_VS_ON
        ae = _make_ae_with_catalog(["AP_VS_VAR_SET_ENGLISH"])
        ctrl = MSFSControl(ae)
        ctrl.set_vertical_speed(1500)
        # find() returns None for AP_VS_ON → SDK-only fallback
        assert ae.find_calls[0] == "AP_VS_ON"
        assert ae.find_calls[1] == "AP_VS_VAR_SET_ENGLISH"
        # Dynamic AP_VS_ON Event was created and called without param
        assert "AP_VS_ON" in ctrl._dynamic_events
        vs_event = ctrl._dynamic_events["AP_VS_ON"]
        assert vs_event.call_count == 1
        assert vs_event.noarg_calls == 1
        # Catalogued AP_VS_VAR_SET_ENGLISH called with 1500
        assert ae._catalog["AP_VS_VAR_SET_ENGLISH"].calls == [1500]
        # AP_VS_HOLD is never in play
        assert ae._catalog.get("AP_VS_HOLD") is None

    def test_vs_execution_order(self, monkeypatch):
        """Execution order: dynamic AP_VS_ON() → catalogued AP_VS_VAR_SET_ENGLISH(1500)."""
        RecordingEvent.reset()
        reset_trace()
        monkeypatch.setattr("modules.control.Event", RecordingEvent)
        ae = _make_ae_with_catalog(["AP_VS_VAR_SET_ENGLISH"])
        ctrl = MSFSControl(ae)
        ctrl.set_vertical_speed(1500)
        # Shared trace proves exact cross-type execution order
        assert _trace == [
            ("AP_VS_ON", NO_ARG),
            ("AP_VS_VAR_SET_ENGLISH", 1500),
        ]

    def test_vs_hold_not_called(self, monkeypatch):
        """AP_VS_HOLD must NOT be called."""
        RecordingEvent.reset()
        reset_trace()
        monkeypatch.setattr("modules.control.Event", RecordingEvent)
        ae = _make_ae_with_catalog(["AP_VS_VAR_SET_ENGLISH", "AP_VS_HOLD"])
        ctrl = MSFSControl(ae)
        ctrl.set_vertical_speed(1500)
        assert ae._catalog["AP_VS_HOLD"].calls == []


# ── NAV1/NAV2 SDK-only tests (BLOCKER 3) ───────────────────────


class TestNAVSDKOnly:
    """NAV1/NAV2 SDK-only: dynamic Event, integer Hz, caching."""

    @pytest.mark.parametrize("nav_index,event_name", [
        (1, "NAV1_RADIO_SET_HZ"),
        (2, "NAV2_RADIO_SET_HZ"),
    ])
    def test_nav_sdk_only_path(self, nav_index, event_name, monkeypatch):
        """find() returns None, Event created with bytes name, called with Hz."""
        RecordingEvent.reset()
        monkeypatch.setattr("modules.control.Event", RecordingEvent)
        ae = FakeAircraftEvents({})
        ctrl = MSFSControl(ae)
        ctrl.set_nav_frequency(nav_index, 110_300_000)
        # find() returned None → SDK-only fallback
        assert ae.find_calls[0] == event_name
        # Dynamic Event created with correct bytes name
        assert event_name in ctrl._dynamic_events
        event = ctrl._dynamic_events[event_name]
        assert event.deff == event_name.encode("ascii")
        # Event called with exact integer Hz
        assert event.call_count == 1
        assert event.call_values == [110_300_000]

    @pytest.mark.parametrize("nav_index,event_name", [
        (1, "NAV1_RADIO_SET_HZ"),
        (2, "NAV2_RADIO_SET_HZ"),
    ])
    def test_nav_cached(self, nav_index, event_name, monkeypatch):
        """Second call reuses cached Event: 1 constructor, 2 calls."""
        RecordingEvent.reset()
        monkeypatch.setattr("modules.control.Event", RecordingEvent)
        ae = FakeAircraftEvents({})
        ctrl = MSFSControl(ae)
        ctrl.set_nav_frequency(nav_index, 110_300_000)
        first_event = ctrl._dynamic_events[event_name]
        ctrl.set_nav_frequency(nav_index, 110_300_000)
        assert ctrl._dynamic_events[event_name] is first_event
        assert len(RecordingEvent._instances) == 1
        assert first_event.call_count == 2

    @pytest.mark.parametrize("nav_index,hz_event,bcd_event", [
        (1, "NAV1_RADIO_SET_HZ", "NAV1_RADIO_SET"),
        (2, "NAV2_RADIO_SET_HZ", "NAV2_RADIO_SET"),
    ])
    def test_nav_uses_hz_not_bcd(self, nav_index, hz_event, bcd_event, monkeypatch):
        """set_nav_frequency() uses only _HZ variant, never BCD variant."""
        RecordingEvent.reset()
        monkeypatch.setattr("modules.control.Event", RecordingEvent)
        # Put BCD event in catalog — it should NOT be looked up
        ae = _make_ae_with_catalog([bcd_event])
        ctrl = MSFSControl(ae)
        ctrl.set_nav_frequency(nav_index, 110_300_000)
        # _HZ event was resolved via SDK-only fallback
        assert ae.find_calls[0] == hz_event
        assert hz_event in ctrl._dynamic_events
        event = ctrl._dynamic_events[hz_event]
        assert event.call_values == [110_300_000]
        # BCD event was never looked up
        assert bcd_event not in ae.find_calls
        # BCD event was never called
        assert ae._catalog[bcd_event].calls == []


# ── B-AT-1: continuous flaps fraction ───────────────────────────


class TestBAT1Autothrottle:
    """B-AT-1: Continuous flaps fraction, no quantization."""

    def test_calibration_half(self):
        """flaps 0.5 → drag 0.30 (matches old round(2)×0.15)."""
        ctrl = AutothrottleController()
        result = ctrl.calculate_base_throttle(
            aircraft_weight=5000.0, flaps_fraction=0.5, gear_down=False
        )
        assert abs(result - (0.5 + 0.3)) < 1e-9

    def test_calibration_zero(self):
        """flaps 0.0 → drag 0.0."""
        ctrl = AutothrottleController()
        result = ctrl.calculate_base_throttle(
            aircraft_weight=5000.0, flaps_fraction=0.0, gear_down=False
        )
        assert abs(result - 0.5) < 1e-9

    def test_calibration_linearity(self):
        """flaps_fraction × flaps_drag_full_deployment is linear (no steps)."""
        ctrl = AutothrottleController()
        # Use 0.8 to stay under 1.0 clamp (0.5 + 0.8×0.6 = 0.98)
        result = ctrl.calculate_base_throttle(
            aircraft_weight=5000.0, flaps_fraction=0.8, gear_down=False
        )
        assert abs(result - (0.5 + 0.8 * 0.6)) < 1e-9

    def test_clamp_above(self):
        """flaps > 1.0 clamps to 1.0, result clamped to max_throttle."""
        ctrl = AutothrottleController()
        result = ctrl.calculate_base_throttle(
            aircraft_weight=5000.0, flaps_fraction=2.0, gear_down=False
        )
        # 0.5 + 1.0*0.6 = 1.1 → clamped to 1.0
        assert abs(result - 1.0) < 1e-9

    def test_clamp_below(self):
        """flaps < 0.0 clamps to 0.0."""
        ctrl = AutothrottleController()
        result = ctrl.calculate_base_throttle(
            aircraft_weight=5000.0, flaps_fraction=-0.5, gear_down=False
        )
        assert abs(result - 0.5) < 1e-9

    def test_intermediate_linear(self):
        """Intermediate values are linear (no step quantization)."""
        ctrl = AutothrottleController()
        r0 = ctrl.calculate_base_throttle(5000.0, 0.0, False)
        r_half = ctrl.calculate_base_throttle(5000.0, 0.5, False)
        # Linear: 0.5 should be r0 + 0.5 * drag_full = 0.5 + 0.3 = 0.8
        expected_half = r0 + 0.5 * 0.6
        assert abs(r_half - expected_half) < 1e-9

    def test_no_quantization_in_calculate_throttle(self):
        """calculate_throttle passes raw fraction, not int(round(*4))."""
        ctrl = AutothrottleController()
        ctrl.activate()
        # Monkey-patch calculate_base_throttle to capture args
        captured = {}
        original = ctrl.calculate_base_throttle

        def spy(aircraft_weight, flaps_fraction, gear_down):
            captured["flaps_fraction"] = flaps_fraction
            return original(aircraft_weight, flaps_fraction, gear_down)

        ctrl.calculate_base_throttle = spy

        telemetry = {
            "speed": {"airspeed_indicated": 140.0},
            "attitude": {"bank": 0},
            "configuration": {"flaps_position": 0.37, "gear_position": 1.0},
        }
        ctrl.calculate_throttle(telemetry, target_speed=140.0, wind_data={})
        # Must be 0.37, not int(round(0.37*4))=1
        assert captured["flaps_fraction"] == 0.37

    def test_config_field_renamed(self):
        """AutothrottleConfig uses flaps_drag_full_deployment, not flaps_drag_factor."""
        config = AutothrottleConfig()
        assert hasattr(config, "flaps_drag_full_deployment")
        assert not hasattr(config, "flaps_drag_factor")
        assert config.flaps_drag_full_deployment == 0.6


# ── B-AT-1: isolated calibration at max_throttle=2.0 (BLOCKER 5) ──


class TestBAT1IsolatedCalibration:
    """B-AT-1: Isolate flap correction 0.6 using max_throttle=2.0."""

    def test_full_deployment_drag(self):
        """fraction 1.0 → base 0.5 + drag 0.6 = 1.1 (no clamp at max_throttle=2.0)."""
        config = AutothrottleConfig(max_throttle=2.0)
        ctrl = AutothrottleController(config=config)
        result = ctrl.calculate_base_throttle(
            aircraft_weight=5000.0, flaps_fraction=1.0, gear_down=False
        )
        assert abs(result - 1.1) < 1e-9

    def test_isolated_drag_difference(self):
        """1.1 - 0.5 = 0.6 → proves correction factor exactly."""
        config = AutothrottleConfig(max_throttle=2.0)
        ctrl = AutothrottleController(config=config)
        r_zero = ctrl.calculate_base_throttle(
            aircraft_weight=5000.0, flaps_fraction=0.0, gear_down=False
        )
        r_full = ctrl.calculate_base_throttle(
            aircraft_weight=5000.0, flaps_fraction=1.0, gear_down=False
        )
        assert abs((r_full - r_zero) - 0.6) < 1e-9

    def test_fraction_0_drag(self):
        """fraction 0.0 → flap correction 0.0."""
        config = AutothrottleConfig(max_throttle=2.0)
        ctrl = AutothrottleController(config=config)
        result = ctrl.calculate_base_throttle(
            aircraft_weight=5000.0, flaps_fraction=0.0, gear_down=False
        )
        base = 0.5  # reference weight
        assert abs(result - base) < 1e-9

    def test_fraction_half_drag(self):
        """fraction 0.5 → flap correction 0.30."""
        config = AutothrottleConfig(max_throttle=2.0)
        ctrl = AutothrottleController(config=config)
        result = ctrl.calculate_base_throttle(
            aircraft_weight=5000.0, flaps_fraction=0.5, gear_down=False
        )
        assert abs(result - (0.5 + 0.30)) < 1e-9

    def test_fraction_08_drag(self):
        """fraction 0.8 → flap correction 0.48 (linearity)."""
        config = AutothrottleConfig(max_throttle=2.0)
        ctrl = AutothrottleController(config=config)
        result = ctrl.calculate_base_throttle(
            aircraft_weight=5000.0, flaps_fraction=0.8, gear_down=False
        )
        assert abs(result - (0.5 + 0.48)) < 1e-9

    def test_negative_fraction_clamped(self):
        """fraction < 0 → clamped to 0, correction 0.0."""
        config = AutothrottleConfig(max_throttle=2.0)
        ctrl = AutothrottleController(config=config)
        result = ctrl.calculate_base_throttle(
            aircraft_weight=5000.0, flaps_fraction=-0.5, gear_down=False
        )
        assert abs(result - 0.5) < 1e-9

    def test_over_one_fraction_clamped(self):
        """fraction > 1 → clamped to 1, correction 0.6."""
        config = AutothrottleConfig(max_throttle=2.0)
        ctrl = AutothrottleController(config=config)
        result = ctrl.calculate_base_throttle(
            aircraft_weight=5000.0, flaps_fraction=2.0, gear_down=False
        )
        assert abs(result - 1.1) < 1e-9

    def test_output_clamp_at_normal_max_throttle(self):
        """General output clamp at max_throttle=1.0."""
        ctrl = AutothrottleController()  # default max_throttle=1.0
        result = ctrl.calculate_base_throttle(
            aircraft_weight=5000.0, flaps_fraction=1.0, gear_down=False
        )
        assert abs(result - 1.0) < 1e-9


# ── Contract test against installed SimConnect library (BLOCKER 4) ──


class TestSimConnectContract:
    """Verify static API shape of installed SimConnect v0.4.26.

    Uses isolated subprocess to avoid conftest sys.modules mocks.
    """

    def test_event_import_path(self):
        """Verify Event is importable from SimConnect.EventList in clean process."""
        import subprocess
        import sys
        import textwrap

        script = textwrap.dedent("""\
            import sys
            try:
                from SimConnect.EventList import Event
            except ImportError:
                print("SKIP: SimConnect not installed")
                sys.exit(2)
            ok = True
            ok = ok and callable(Event)
            ok = ok and hasattr(Event, "__call__")
            # Check signature: Event(_deff, _sm, _dec='')
            import inspect
            sig = inspect.signature(Event)
            params = list(sig.parameters.keys())
            ok = ok and len(params) >= 2
            print("OK" if ok else "FAIL")
        """)
        result = subprocess.run(
            [sys.executable, "-c", script],
            capture_output=True, text=True, timeout=30,
        )
        if result.returncode == 2:
            pytest.skip("SimConnect not installed in CI environment")
        assert result.returncode == 0, f"subprocess failed: {result.stderr}"
        assert result.stdout.strip() == "OK", f"contract check: {result.stdout.strip()}"

    def test_sdk_only_events_defined(self):
        """SDK_ONLY_EVENTS contains exactly the 3 confirmed SDK-only names."""
        assert SDK_ONLY_EVENTS == frozenset({
            "AP_VS_ON", "NAV1_RADIO_SET_HZ", "NAV2_RADIO_SET_HZ",
        })
