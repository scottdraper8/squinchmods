import ctypes
import importlib.util
import struct
from pathlib import Path

import pytest


def mission_runtime():
    path = Path(__file__).parents[3] / "mods/search-probes/src/search_probes/native_missions.py"
    spec = importlib.util.spec_from_file_location("native_missions_test", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    runtime = module.NativeMissions.__new__(module.NativeMissions)
    runtime._manager = lambda: 0x100000
    runtime._active = lambda *args: False
    return runtime


def native_missions_module():
    path = Path(__file__).parents[3] / "mods/search-probes/src/search_probes/native_missions.py"
    spec = importlib.util.spec_from_file_location("native_missions_route_test", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_target_route_active_requires_one_owned_route_at_exact_address():
    target_route_active = native_missions_module().target_route_active
    events = [{"mission_context_id": "SQN_SS11_NAV", "address": "0x1234"}]
    assert target_route_active(events, b"SQN_SS11_NAV", 0x1234)
    assert not target_route_active(events, b"SQN_SS11_NAV", 0x1235)
    assert not target_route_active(events, b"OTHER", 0x1234)


def test_target_route_active_rejects_duplicate_owned_routes():
    target_route_active = native_missions_module().target_route_active
    events = [
        {"mission_context_id": "SQN_SS11_NAV", "address": "0x1234"},
        {"mission_context_id": "SQN_SS11_NAV", "address": "0x1234"},
    ]
    with pytest.raises(RuntimeError, match="multiple routes"):
        target_route_active(events, b"SQN_SS11_NAV", 0x1234)


def test_target_route_active_ignores_events_without_mission_context():
    target_route_active = native_missions_module().target_route_active
    assert not target_route_active([{"address": "0x1234"}], b"SQN_SS11_NAV", 0x1234)


def test_active_target_is_rejected_before_a_new_request():
    runtime = mission_runtime()
    runtime._active = lambda *args: True
    runtime._read = lambda *args: pytest.fail("active target must be rejected before queue access")
    with pytest.raises(RuntimeError, match="Abandon it in the Log"):
        runtime.require_available(b"SQN_SS11_NAV")


def test_pending_requests_use_exact_identity_and_both_native_queues():
    runtime = mission_runtime()
    data = {
        0x100180: struct.pack("<IIQ", 2, 1, 0x200000),
        0x100190: struct.pack("<IIQ", 2, 1, 0x300000),
        0x200000: b"UNRELATED\0".ljust(16, b"\0"),
        0x300000: b"SQN_SS11_NAV\0".ljust(16, b"\0"),
    }
    runtime._read = lambda address, size: data[address]
    assert runtime.pending(b"SQN_SS11_NAV")
    assert not runtime.pending(b"SQN_SS11_NA")
    with pytest.raises(RuntimeError, match="still starting"):
        runtime.require_available(b"SQN_SS11_NAV")


def test_corrupt_native_queue_is_rejected_without_dereferencing():
    runtime = mission_runtime()
    runtime._read = lambda *args: struct.pack("<IIQ", 1, 2, 0)
    with pytest.raises(RuntimeError, match="unsupported shape"):
        runtime.pending(b"SQN_SS11_NAV")


def test_native_start_uses_unseeded_identity_and_selects_the_target():
    runtime = mission_runtime()
    calls = []

    def start(manager, identity, seed, restart, selected):
        calls.append((manager, ctypes.string_at(identity, 16), ctypes.string_at(seed, 16),
                      restart, selected))
        return True

    runtime._start = start
    runtime.start(b"SQN_SS11_NAV")
    assert calls == [(0x100000, b"SQN_SS11_NAV".ljust(16, b"\0"), bytes(16), False, True)]
    runtime._start = lambda *args: False
    with pytest.raises(RuntimeError, match="declined"):
        runtime.start(b"SQN_SS11_NAV")
