"""Regression tests for architectural P0 fixes."""
import pytest
from modules.command_gateway import CommandGateway, CommandRejected, CommandSource
from modules.connection_optimizer import ConnectionOptimizer
from modules.control import MSFSControl
from modules.control_ownership import ControlOwner, ControlOwnership

from tests.test_p0_aconf1_aconf4_bat1 import FakeAircraftEvents, _make_ae_with_catalog


class FakeControl:
    def __init__(self): self.calls=[]
    def set_throttle(self,v): self.calls.append(("set_throttle",v))
    def set_vertical_speed(self,v): self.calls.append(("set_vertical_speed",v))
def external(): return ControlOwnership(ControlOwner.EXTERNAL,ControlOwner.EXTERNAL,ControlOwner.EXTERNAL)
def test_non_owner_rejected():
    with pytest.raises(CommandRejected): CommandGateway(FakeControl(),external).set_throttle(.5)
def test_external_owner_allowed():
    raw=FakeControl(); gateway=CommandGateway(raw,external)
    with gateway.source_scope(CommandSource.EXTERNAL): gateway.set_throttle(.5)
    assert raw.calls==[("set_throttle",.5)]
def test_safety_override_scoped():
    raw=FakeControl(); gateway=CommandGateway(raw,external)
    with gateway.source_scope(CommandSource.SAFETY): gateway.set_throttle(1.0); gateway.set_vertical_speed(1500)
    with pytest.raises(CommandRejected): gateway.set_throttle(1.0)

@pytest.mark.parametrize("method,value,event_name,expected",[
    ("set_throttle",2,"THROTTLE_SET",16384),
    ("set_throttle",-1,"THROTTLE_SET",0),
    ("set_rudder",2,"RUDDER_SET",16384),
    ("set_aileron",-2,"AILERON_SET",-16384),
])
def test_clamps(method,value,event_name,expected):
    ae=_make_ae_with_catalog([event_name])
    ctrl=MSFSControl(ae)
    getattr(ctrl,method)(value)
    assert ae._catalog[event_name].calls==[expected]

@pytest.mark.parametrize("bad",[None,float("nan"),float("inf"),-float("inf")])
def test_non_finite_rejected(bad):
    ae=FakeAircraftEvents({})
    MSFSControl(ae).set_throttle(bad)
    # No event should have been resolved
    assert ae.find_calls==[]

class Telemetry:
    def get_all_data(self): return {"position":{"latitude":0}}
class NoCommands:
    def __getattr__(self,name): raise AssertionError(f"diagnostic command: {name}")
class Wasm:
    connected=True
    def __init__(self): self.reads=[]
    def read_lvar(self,name): self.reads.append(name); return 1.0
    def write_lvar(self,*args): raise AssertionError("diagnostics must not write")
def test_simconnect_probe_read_only(monkeypatch):
    monkeypatch.setattr("modules.connection_optimizer.time.sleep",lambda _:None); o=ConnectionOptimizer(Telemetry(),NoCommands()); o.test_iterations=1; assert o._test_simconnect().available
def test_lvar_probe_read_only(monkeypatch):
    monkeypatch.setattr("modules.connection_optimizer.time.sleep",lambda _:None); w=Wasm(); o=ConnectionOptimizer(Telemetry(),NoCommands(),w); o.test_iterations=1; assert o._test_lvars().available and w.reads==["MOBIFLIGHT_TEST"]
