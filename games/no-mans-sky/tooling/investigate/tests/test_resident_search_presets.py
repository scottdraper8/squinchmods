from __future__ import annotations

import importlib.util
import json
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest


def _module(filename: str):
    path = Path(__file__).parents[3] / "mods/search-probes/src/search_probes" / filename
    spec = importlib.util.spec_from_file_location(f"test_{path.stem}", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


presets = _module("resident_search_presets.py")
protocol = _module("resident_search_protocol.py")


def _store(path: Path, defaults=None):
    return presets.PresetStore(
        path,
        defaults=defaults or {"Default": {"target_biome": "Lush"}},
        normalize_criteria=protocol.normalize_criteria,
        default_candidate_limit=5000,
        max_candidate_limit=protocol.MAX_PROVEN_UI_CANDIDATES,
        default_result_limit=5,
        max_result_limit=protocol.MAX_RESULTS,
    )


def test_absent_file_starts_with_defaults_without_writing(tmp_path: Path) -> None:
    path = tmp_path / "presets.json"
    store = _store(path)
    assert store.names() == ("Default",)
    assert store.get("default") == {
        "name": "Default",
        "criteria": {"target_biome": "Lush"},
        "candidate_limit": 5000,
        "result_limit": 5,
    }
    assert not path.exists()


def test_save_override_delete_zero_and_reload(tmp_path: Path) -> None:
    path = tmp_path / "presets.json"
    store = _store(path)
    store.save(
        "Default",
        {"target_biome": "Frozen"},
        candidate_limit=200,
        result_limit=2,
    )
    store.save(
        "My calm world",
        {"storm_frequency": "None", "planet_rings": "Exclude"},
        candidate_limit=800,
        result_limit=3,
    )
    assert store.names() == ("Default", "My calm world")
    assert store.get("Default")["criteria"] == {"target_biome": "Frozen"}
    assert store.delete("default") is True
    assert store.delete("My calm world") is True
    assert store.names() == ()
    assert _store(path).names() == ()
    assert json.loads(path.read_text(encoding="utf-8")) == {
        "schema": 1,
        "presets": [],
    }


def test_restore_builtins_preserves_custom_and_replaces_overrides(tmp_path: Path) -> None:
    path = tmp_path / "presets.json"
    store = _store(path)
    store.save(
        "Default",
        {"target_biome": "Frozen"},
        candidate_limit=10,
        result_limit=1,
    )
    store.save("Custom", {}, candidate_limit=20, result_limit=2)
    store.restore_defaults()
    assert store.names() == ("Default", "Custom")
    assert store.get("Default")["criteria"] == {"target_biome": "Lush"}
    assert store.get("Custom")["candidate_limit"] == 20
    assert store.backup_path.exists()


@pytest.mark.parametrize("name", ("", "  ", "line\nbreak", "x" * 81))
def test_invalid_names_fail_closed(tmp_path: Path, name: str) -> None:
    store = _store(tmp_path / "presets.json")
    with pytest.raises((TypeError, ValueError)):
        store.save(name, {}, candidate_limit=10, result_limit=1)


def test_store_enforces_maximum_but_has_no_minimum(tmp_path: Path) -> None:
    defaults = {f"Preset {index}": {} for index in range(presets.MAX_PRESETS)}
    store = _store(tmp_path / "presets.json", defaults)
    with pytest.raises(ValueError, match="at most 9"):
        store.save("One too many", {}, candidate_limit=10, result_limit=1)


def test_guide_slots_are_bounded_exact_and_round_trip() -> None:
    assert presets.guide_slot_mission(0) == "SQN_SS9_P00"
    assert presets.guide_slot_event(8) == "SE_SQN_SS9_P08"
    assert presets.guide_slot_ready_event(8) == "SE_SQN_SS9_R08"
    assert presets.guide_slot_target_event(8) == "SE_SQN_SS9_T08"
    assert presets.guide_event_slot("SE_SQN_SS9_P00") == 0
    assert presets.guide_event_slot("SE_SQN_SS9_P08") == 8
    for invalid in (
        "SE_SQN_SS_LUSH_R08",
        "SE_SQN_SS9_P0",
        "SE_SQN_SS9_P09",
        "SE_SQN_SS9_P000",
        "prefix-SE_SQN_SS9_P00",
    ):
        assert presets.guide_event_slot(invalid) is None
    with pytest.raises(ValueError):
        presets.guide_slot_mission(9)


def test_guide_labels_preserve_short_names_and_utf8_safe_abbreviations() -> None:
    assert presets.guide_topic_label("Earthlike", 0) == "Earthlike"
    long_ascii = presets.guide_topic_label("A" * 80, 0)
    long_utf8 = presets.guide_topic_label("Planet ☁" * 20, 8)
    assert long_ascii.endswith("~01")
    assert long_utf8.endswith("~09")
    assert len(long_ascii.encode("utf-8")) <= 31
    assert len(long_utf8.encode("utf-8")) <= 31
def test_concurrent_store_access_remains_coherent(tmp_path: Path) -> None:
    store = _store(tmp_path / "presets.json", {"Default": {}})

    def save(index: int) -> None:
        store.save(f"Concurrent {index}", {}, candidate_limit=10, result_limit=1)

    with ThreadPoolExecutor(max_workers=8) as executor:
        tuple(executor.map(save, range(presets.MAX_PRESETS - 1)))
    assert len(store.records()) == presets.MAX_PRESETS
    assert len(set(name.casefold() for name in store.names())) == presets.MAX_PRESETS
    assert _store(store.path, {"Default": {}}).records() == store.records()


@pytest.mark.parametrize("operation", ("save", "delete", "restore"))
def test_failed_persistence_does_not_change_visible_records(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, operation: str
) -> None:
    store = _store(tmp_path / "presets.json")
    if operation == "restore":
        store.save(
            "Default",
            {"target_biome": "Frozen"},
            candidate_limit=10,
            result_limit=1,
        )
    before = store.records()

    def fail(_records):
        raise OSError("simulated persistence failure")

    monkeypatch.setattr(store, "_write", fail)
    with pytest.raises(OSError, match="simulated persistence failure"):
        if operation == "save":
            store.save("Custom", {}, candidate_limit=10, result_limit=1)
        elif operation == "delete":
            store.delete("Default")
        else:
            store.restore_defaults()
    assert store.records() == before


def test_malformed_or_duplicate_persisted_data_fails_closed(tmp_path: Path) -> None:
    path = tmp_path / "presets.json"
    record = {
        "name": "Duplicate",
        "criteria": {},
        "candidate_limit": 10,
        "result_limit": 1,
    }
    path.write_text(
        json.dumps({"schema": 1, "presets": [record, {**record, "name": "duplicate"}]}),
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="duplicate preset name"):
        _store(path)
