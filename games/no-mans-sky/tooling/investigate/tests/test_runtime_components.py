import ast
import queue
import types
from pathlib import Path

import pytest
from search_probes import planet_data
from search_probes.navigation import Navigation
from search_probes.search_engine import SearchEngine
from search_probes.search_scheduler import SearchScheduler


def _guide_completion_method():
    source = (
        Path(__file__).parents[3]
        / "mods/search-probes/src/search_probes/resident_search_probe.py"
    )
    tree = ast.parse(source.read_text(encoding="utf-8"))
    resident = next(
        node
        for node in tree.body
        if isinstance(node, ast.ClassDef) and node.name == "ResidentSearchProbe"
    )
    method = next(
        node
        for node in resident.body
        if isinstance(node, ast.FunctionDef) and node.name == "_complete_guide_search"
    )

    class Presets:
        @staticmethod
        def guide_slot_mission(slot):
            return f"SQN_SS9_P{slot:02d}"

        @staticmethod
        def guide_slot_target_event(slot):
            return f"SE_SQN_SS9_T{slot:02d}"

        @staticmethod
        def guide_slot_ready_event(slot):
            return f"SE_SQN_SS9_R{slot:02d}"

    namespace = {"_PRESETS": Presets}
    module = ast.Module(body=[method], type_ignores=[])
    exec(compile(module, str(source), "exec"), namespace)
    return namespace["_complete_guide_search"]


class _GuideMissions:
    def __init__(self, active):
        self.is_active = active

    def active(self, mission_id):
        return self.is_active


class _GuideNavigation:
    def arm_native_navigation(self, **kwargs):
        raise AssertionError("abandoned or no-match Guide must not arm navigation")

    def remove_legacy_owned_routes(self, manager):
        raise AssertionError("abandoned or no-match Guide must not clean routes")


def _guide_probe(active):
    probe = types.SimpleNamespace(
        _guide_dispatches={
            "guide": {
                "id": "guide",
                "slot": 2,
                "name": "Earthlike",
                "event_context": bytes(0x18),
            }
        },
        _missions=_GuideMissions(active),
        _navigation=_GuideNavigation(),
        _engine=types.SimpleNamespace(
            require_current_reality=lambda *args, **kwargs: None,
            scan_event_manager=lambda: 0,
        ),
        statuses=[],
        events=[],
    )
    probe._set_guide_status = lambda *args, **kwargs: probe.statuses.append((args, kwargs))
    probe._emit = lambda *args, **kwargs: probe.events.append((args, kwargs))
    return probe


def test_guide_completion_does_not_publish_after_native_mission_abandonment():
    complete = _guide_completion_method()
    probe = _guide_probe(active=False)

    with pytest.raises(RuntimeError, match="abandoned"):
        complete(probe, {"id": "guide"}, [{"address": "0x1234"}])

    assert "guide" in probe._guide_dispatches
    assert probe.statuses == []
    assert probe.events == []


def test_guide_completion_active_no_match_clears_dispatch_without_navigation():
    complete = _guide_completion_method()
    probe = _guide_probe(active=True)

    assert complete(probe, {"id": "guide"}, []) == {"guide_navigation_published": False}
    assert probe._guide_dispatches == {}
    assert probe.statuses[0][0] == (
        "no_match",
        "No exact match for Earthlike. Abandon this probe in the Log.",
    )


def _engine() -> SearchEngine:
    engine = SearchEngine.__new__(SearchEngine)
    engine._capture_enabled = False
    engine._capture_planet_colours = False
    engine._capture_planet_weather = False
    engine._capture_planet_metadata = False
    engine._capture_planet_spawn_flags = False
    engine._capture_planet_spawns = False
    engine._capture_resolved_object_lists = False
    engine._resolved_object_planet_indices = frozenset()
    engine._captured_planet_details = []
    engine._planet_detail_capture_error = None
    return engine


def test_legacy_route_cleanup_is_scoped_to_owned_identities():
    assert Navigation.is_legacy_owned_route(b"SE_SQN_SS_LUSH_R08", b"")
    assert not Navigation.is_legacy_owned_route(b"SE_SQN_SS_LUSH_R08", b"OTHER")
    assert not Navigation.is_legacy_owned_route(b"CRASHED_FREIGHTER", b"")
    assert not Navigation.is_legacy_owned_route(b"SE_SQN_SS11_TGT", b"SQN_SS11_NAV")


def test_capture_planet_ignores_callback_outside_owned_query(monkeypatch):
    engine = _engine()
    calls = []
    monkeypatch.setattr(
        planet_data,
        "copy_planet_details",
        lambda *args, **kwargs: calls.append((args, kwargs)),
    )

    engine.capture_planet(0x1234)

    assert calls == []
    assert engine._captured_planet_details == []


def test_capture_planet_copies_name_even_without_optional_flags(monkeypatch):
    engine = _engine()
    engine._capture_enabled = True
    captured = {"planet_index": 3, "name": "Generated Name"}
    calls = []

    def copy_details(*args, **kwargs):
        calls.append((args, kwargs))
        return dict(captured)

    monkeypatch.setattr(planet_data, "copy_planet_details", copy_details)
    engine.capture_planet(0x1234)

    assert engine._captured_planet_details == [captured]
    assert calls == [
        (
            (0x1234,),
            {
                "include_colours": False,
                "include_weather": False,
                "include_metadata": False,
                "include_spawn_flags": False,
                "include_spawns": False,
            },
        )
    ]


def test_capture_planet_records_copy_failure_without_unwinding(monkeypatch):
    engine = _engine()
    engine._capture_enabled = True
    monkeypatch.setattr(
        planet_data,
        "copy_planet_details",
        lambda *args, **kwargs: (_ for _ in ()).throw(ValueError("bad planet")),
    )

    engine.capture_planet(0x1234)

    assert engine._captured_planet_details == []
    assert engine._planet_detail_capture_error == "ValueError: bad planet"


def test_capture_planet_resolves_only_selected_object_indices(monkeypatch):
    engine = _engine()
    engine._capture_enabled = True
    engine._capture_resolved_object_lists = True
    engine._resolved_object_planet_indices = frozenset({7})
    resolved = []
    monkeypatch.setattr(
        planet_data,
        "copy_planet_details",
        lambda *args, **kwargs: {"planet_index": 3, "name": "Not selected"},
    )
    engine.resolve_planet_object_lists = lambda address: resolved.append(address) or {"ok": True}

    engine.capture_planet(0x1234)
    assert resolved == []
    assert engine._captured_planet_details == [{"planet_index": 3, "name": "Not selected"}]

    engine._resolved_object_planet_indices = frozenset({3})
    engine.capture_planet(0x5678)
    assert resolved == [0x5678]
    assert engine._captured_planet_details[-1]["resolved_object_lists"] == {"ok": True}


def test_scheduler_requeue_failure_clears_search_and_survey_state():
    scheduler = SearchScheduler.__new__(SearchScheduler)
    scheduler.commands = type(
        "FullQueue",
        (),
        {"put_nowait": lambda self, command: (_ for _ in ()).throw(queue.Full)},
    )()
    scheduler.searches = {"command": {}}
    scheduler.surveys = {"command": {}}

    with pytest.raises(RuntimeError, match="queue filled"):
        scheduler.requeue_search({"id": "command"})

    assert scheduler.searches == {}
    assert scheduler.surveys == {}
