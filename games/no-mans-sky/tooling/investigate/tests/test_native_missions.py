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
    return runtime


def native_missions_module():
    path = Path(__file__).parents[3] / "mods/search-probes/src/search_probes/native_missions.py"
    spec = importlib.util.spec_from_file_location("native_missions_route_test", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def selection_runtime(records, *, capacity=None, selected=None):
    runtime = mission_runtime()
    vector_capacity = len(records) if capacity is None else capacity
    memory = {0x1001C0: struct.pack("<IIQ", vector_capacity, len(records), 0x200000)}
    for index, record in enumerate(records):
        address = 0x300000 + index * 0x1000
        memory[0x200000 + index * 8] = struct.pack("<Q", address)
        memory[address + 8] = record["mission"].ljust(16, b"\0")
        memory[address + 0x100] = record.get("seed", struct.pack("<QB7x", 0, 1))
        memory[address + 0x1C] = struct.pack("<I", record.get("stages", 2))
        memory[address + 0x48] = struct.pack("<i", record.get("progress", 0))
    memory[0x100250] = struct.pack("<i", -1)
    runtime._read = lambda address, size: memory[address][:size]
    selected_calls = []

    def select(manager, mission, restart):
        selected_calls.append((manager, mission, restart))
        if selected is not None:
            memory[0x100250] = struct.pack("<i", selected)

    runtime._select = select
    return runtime, selected_calls


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
    runtime, _calls = selection_runtime(
        [{"mission": b"SQN_SS11_NAV", "progress": 0}]
    )
    read = runtime._read

    def guarded_read(address, size):
        if address == 0x100180:
            pytest.fail("active target must be rejected before queue access")
        return read(address, size)

    runtime._read = guarded_read
    with pytest.raises(RuntimeError, match="Abandon it in the Log"):
        runtime.require_available(b"SQN_SS11_NAV")


def test_pending_requests_use_exact_identity_and_both_native_queues():
    runtime = mission_runtime()
    data = {
        0x1001C0: struct.pack("<IIQ", 0, 0, 0),
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


def test_native_start_uses_valid_zero_seed_and_selects_the_target():
    runtime = mission_runtime()
    calls = []

    def start(manager, identity, seed, restart, selected):
        calls.append(
            (manager, ctypes.string_at(identity, 16), ctypes.string_at(seed, 16), restart, selected)
        )
        return True

    runtime._start = start
    runtime.start(b"SQN_SS11_NAV")
    assert calls == [
        (0x100000, b"SQN_SS11_NAV".ljust(16, b"\0"), struct.pack("<QB7x", 0, 1), False, True)
    ]
    runtime._start = lambda *args: False
    with pytest.raises(RuntimeError, match="declined"):
        runtime.start(b"SQN_SS11_NAV")


def test_valid_zero_seed_is_distinct_from_legacy_invalid_zero_seed():
    runtime = mission_runtime()
    identity, seed = runtime._identity(b"SQN_SS11_NAV")

    assert ctypes.string_at(ctypes.addressof(identity), 16) == b"SQN_SS11_NAV".ljust(16, b"\0")
    assert bytes(seed) == struct.pack("<QB7x", 0, 1)
    assert bytes(seed) != bytes(16)


def test_active_finds_the_same_valid_zero_seed_identity_as_select():
    runtime, _calls = selection_runtime(
        [{"mission": b"SQN_SS11_NAV", "progress": 0}]
    )
    assert runtime.active(b"SQN_SS11_NAV")


def test_active_ignores_completed_or_different_seed_instances():
    runtime, _calls = selection_runtime(
        [
            {"mission": b"SQN_SS11_NAV", "progress": 2, "stages": 2},
            {
                "mission": b"SQN_SS11_NAV",
                "progress": 0,
                "seed": struct.pack("<QB7x", 1, 1),
            },
        ]
    )

    assert not runtime.active(b"SQN_SS11_NAV")


def test_active_rejects_duplicate_matching_instances():
    runtime, _calls = selection_runtime(
        [
            {"mission": b"SQN_SS11_NAV", "progress": 0},
            {"mission": b"SQN_SS11_NAV", "progress": 1},
        ]
    )

    with pytest.raises(RuntimeError, match="multiple active"):
        runtime.active(b"SQN_SS11_NAV")


def test_completed_mission_reuses_valid_zero_seed_without_duplicate_entry():
    runtime = mission_runtime()
    entries = []
    valid_seed = struct.pack("<QB7x", 0, 1)

    def native_start(manager, identity, seed, restart, selected):
        mission = ctypes.string_at(identity, 16).split(b"\0", 1)[0]
        incoming_seed = ctypes.string_at(seed, 16)
        for entry in entries:
            if entry["mission"] == mission and entry["seed"] == incoming_seed:
                if not entry["completed"] and not restart:
                    return False
                entry["completed"] = False
                return True
        entries.append({"mission": mission, "seed": valid_seed, "completed": False})
        return True

    runtime._start = native_start
    runtime.start(b"SQN_SS11_NAV")
    entries[0]["completed"] = True
    runtime.start(b"SQN_SS11_NAV")

    assert len(entries) == 1
    assert entries[0]["mission"] == b"SQN_SS11_NAV"
    assert entries[0]["seed"] == valid_seed
    assert not entries[0]["completed"]

    legacy_identity = ctypes.create_string_buffer(b"SQN_SS11_NAV", 16)
    legacy_seed = (ctypes.c_ubyte * 16)()
    native_start(
        0x100000,
        ctypes.addressof(legacy_identity),
        ctypes.addressof(legacy_seed),
        False,
        True,
    )
    assert len(entries) == 2
    assert entries[1]["seed"] == valid_seed


def test_select_chooses_only_the_one_active_matching_mission_instance():
    runtime, calls = selection_runtime(
        [
            {"mission": b"OTHER", "progress": 0},
            {"mission": b"SQN_SS11_NAV", "progress": 2},
            {"mission": b"SQN_SS11_NAV", "progress": 0},
        ],
        selected=2,
    )

    runtime.select(b"SQN_SS11_NAV")

    assert calls == [(0x100000, 0x302000, False)]


def test_select_rejects_duplicate_active_matching_instances():
    runtime, _calls = selection_runtime(
        [
            {"mission": b"SQN_SS11_NAV", "progress": 0},
            {"mission": b"SQN_SS11_NAV", "progress": 1},
        ],
        selected=0,
    )
    with pytest.raises(RuntimeError, match="exactly one active"):
        runtime.select(b"SQN_SS11_NAV")


def test_select_rejects_invalid_vector_shape_and_pointer():
    runtime, _calls = selection_runtime([{"mission": b"SQN_SS11_NAV"}], capacity=0, selected=0)
    with pytest.raises(RuntimeError, match="unsupported shape"):
        runtime.select(b"SQN_SS11_NAV")

    runtime, _calls = selection_runtime([{"mission": b"SQN_SS11_NAV"}], selected=0)
    runtime._read = lambda address, size: (
        struct.pack("<IIQ", 1, 1, 0x1000) if address == 0x1001C0 else b""
    )
    with pytest.raises(RuntimeError, match="unavailable"):
        runtime.select(b"SQN_SS11_NAV")


def test_select_rejects_native_selection_failure():
    runtime, _calls = selection_runtime([{"mission": b"SQN_SS11_NAV", "progress": 0}], selected=-1)
    with pytest.raises(RuntimeError, match="did not select"):
        runtime.select(b"SQN_SS11_NAV")
