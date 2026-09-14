from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest


def _build_module():
    runtime = Path(__file__).parents[2] / "runtime"
    sys.path.insert(0, str(runtime))
    from nms_packaging import adapter, common, distribution, installer

    namespace = {}
    for module in (common, adapter, distribution, installer):
        namespace.update(
            {name: value for name, value in vars(module).items() if not name.startswith("__")}
        )
    namespace.update(hashlib=hashlib, json=json)
    return SimpleNamespace(**namespace)


def _adapter(root: Path) -> Path:
    root.mkdir(parents=True)
    (root / "LocTable.MXML").write_text("Search Probes\n", encoding="utf-8")
    wiki = root / "METADATA/REALITY/WIKI.EXML"
    wiki.parent.mkdir(parents=True)
    wiki.write_text(
        "\n".join(
            (
                "SQN_SS_CATEGORY",
                "MISSION.BLACKHOLE.ON.DDS",
                "MISSION.BLACKHOLE.OFF.DDS",
                "HUD/ICONS/WIKI/EXPLORATION4.DDS",
                "HUD/ICONS/WIKI/EXPLORATION2.DDS",
            )
        ),
        encoding="utf-8",
    )
    missions = root / "METADATA/SIMULATION/MISSIONS/TABLES/WIKIMISSIONTABLE.EXML"
    missions.parent.mkdir(parents=True)
    missions.write_text(
        "\n".join(
            (
                "SE_SQN_SS_LUSH_R08",
                "SE_SQN_SS9_P08",
                "SE_SQN_SS9_R08",
                "SE_SQN_SS9_T08",
                *(
                    'value="GcMissionConditionIsScanEventLocal"\n'
                    'name="BlockMissionRestart" value="false"\n'
                    'name="RequiresFullFireteam" value="false"\n'
                    for _index in range(10)
                ),
                *(
                    'value="GcMissionConditionIsScanEventActive"\n'
                    'name="MustMatchThisMissionIDSeed" value="true"'
                    for _index in range(9)
                ),
                *(
                    'value="GcMissionConditionIsScanEventOnCurrentPlanet"\n'
                    'name="AllowInShip" value="true"'
                    for _index in range(10)
                ),
                *('value="GcMissionSequenceEndScanEvent"' for _index in range(38)),
                *('value="GcMissionSequenceStartScanEvent"' for _index in range(19)),
                *(
                    'value="GcMissionSequenceShowMissionUpdateMessage"'
                    for _index in range(10)
                ),
                *('name="EventEndType" value="None"' for _index in range(28)),
                *(
                    'name="SolarSystemLocation" value="FromList"\n'
                    'name="UAsList" value="0000000000000000"'
                    for _index in range(9)
                ),
            )
        )
        + "\n",
        encoding="utf-8",
    )
    navigation = root / "METADATA/SIMULATION/MISSIONS/TABLES/NPCMISSIONTABLE.EXML"
    navigation.write_text(
        "\n".join(
            (
                "SE_SQN_SS11_TGT",
                'value="GcMissionConditionIsScanEventLocal"',
                'name="BlockMissionRestart" value="false"',
                'name="RequiresFullFireteam" value="false"',
                'value="GcMissionConditionIsScanEventOnCurrentPlanet"',
                'name="AllowInShip" value="true"',
                *('value="GcMissionSequenceEndScanEvent"' for _index in range(2)),
                'value="GcMissionSequenceStartScanEvent"',
                'value="GcMissionSequenceShowMissionUpdateMessage"',
                'name="EventEndType" value="None"',
                'name="SolarSystemLocation" value="FromList"',
                'name="UAsList" value="0000000000000000"',
            )
        )
        + "\n",
        encoding="utf-8",
    )
    return root


def _runtime(root: Path, build, proxy: bytes) -> Path:
    root.mkdir(parents=True)
    (root / "SEARCH_PROBES_PRODUCT").write_text(build.PRODUCT_MARKER, encoding="utf-8")
    (root / build.OWNED_PROXY_HASH).write_text(
        build.hashlib.sha256(proxy).hexdigest() + "\n", encoding="ascii"
    )
    state = root / "app/.resident-search"
    state.mkdir(parents=True)
    return root


def test_adapter_validation_and_ownership_are_exact(tmp_path: Path) -> None:
    build = _build_module()
    adapter = _adapter(tmp_path / "adapter")
    assert build.validate_adapter(adapter) == adapter.resolve()
    assert build.is_owned_installed_adapter(adapter)
    (adapter / "unexpected.bin").write_bytes(b"foreign")
    assert not build.is_owned_installed_adapter(adapter)
    with pytest.raises(build.BuildError, match="unexpected navigation-adapter contents"):
        build.validate_adapter(adapter)


def test_manifest_verification_detects_package_drift(tmp_path: Path) -> None:
    build = _build_module()
    (tmp_path / "payload").write_bytes(b"original")
    manifest = build.tree_manifest(tmp_path)
    (tmp_path / "SEARCH_PROBES_MANIFEST.json").write_text(
        build.json.dumps(manifest), encoding="utf-8"
    )
    build.verify_manifest(tmp_path)
    (tmp_path / "payload").write_bytes(b"changed")
    with pytest.raises(build.BuildError, match="does not match"):
        build.verify_manifest(tmp_path)


def test_transactional_install_replaces_both_search_probes_trees_and_preserves_presets(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    build = _build_module()
    old_proxy = b"old owned proxy"
    new_proxy = b"new owned proxy"
    game = tmp_path / "game"
    package = tmp_path / "package"
    (game / "Binaries").mkdir(parents=True)
    (game / "GAMEDATA/MODS").mkdir(parents=True)
    (package / "Binaries").mkdir(parents=True)
    (package / "GAMEDATA/MODS").mkdir(parents=True)

    old_runtime = _runtime(game / "Binaries/SearchProbes", build, old_proxy)
    (old_runtime / "app/.resident-search/presets.json").write_bytes(b'{"preserved":true}\n')
    (old_runtime / "app/.resident-search/form-navigation-context.json").write_bytes(
        b'{"legacy":true}\n'
    )
    (old_runtime / "old.txt").write_text("old", encoding="utf-8")
    (game / "Binaries/winmm.dll").write_bytes(old_proxy)
    _adapter(game / "GAMEDATA/MODS/SearchProbes")

    new_runtime = _runtime(package / "Binaries/SearchProbes", build, new_proxy)
    (new_runtime / "new.txt").write_text("new", encoding="utf-8")
    (package / "Binaries/winmm.dll").write_bytes(new_proxy)
    _adapter(package / "GAMEDATA/MODS/SearchProbes")

    from nms_packaging import installer

    monkeypatch.setattr(installer, "nms_running", lambda: False)
    build.install_tree(package, game)

    installed = game / "Binaries/SearchProbes"
    assert (installed / "new.txt").read_text(encoding="utf-8") == "new"
    assert not (installed / "old.txt").exists()
    assert (installed / "app/.resident-search/presets.json").read_bytes() == (
        b'{"preserved":true}\n'
    )
    assert not (installed / "app/.resident-search/form-navigation-context.json").exists()
    assert (game / "Binaries/winmm.dll").read_bytes() == new_proxy
    assert build.is_owned_installed_adapter(game / "GAMEDATA/MODS/SearchProbes")


def test_superseded_adapter_discovery_includes_amethyst_source_and_deployment(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    build = _build_module()
    game = tmp_path / "game"
    mods = game / "GAMEDATA/MODS"
    overwrite = tmp_path / "amethyst-overwrite"
    source = _adapter(overwrite / "SQUINCH_INVESTIGATION_old")
    deployed = mods / source.name
    deployed.mkdir(parents=True)
    for relative in (
        "LocTable.MXML",
        "METADATA/REALITY/WIKI.EXML",
        "METADATA/SIMULATION/MISSIONS/TABLES/NPCMISSIONTABLE.EXML",
        "METADATA/SIMULATION/MISSIONS/TABLES/WIKIMISSIONTABLE.EXML",
    ):
        target = deployed / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.symlink_to(source / relative)
    monkeypatch.setenv("SQN_NMS_AMETHYST_OVERWRITE", str(overwrite))

    assert build.superseded_adapter_roots(game) == sorted(
        (deployed.resolve(), source.resolve())
    )


def test_superseded_adapter_discovery_rejects_foreign_and_production_paths(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    build = _build_module()
    game = tmp_path / "game"
    mods = game / "GAMEDATA/MODS"
    overwrite = tmp_path / "amethyst-overwrite"
    _adapter(mods / "SearchProbes")
    foreign = _adapter(overwrite / "SQUINCH_INVESTIGATION_foreign")
    (foreign / "unexpected.bin").write_bytes(b"foreign")
    monkeypatch.setenv("SQN_NMS_AMETHYST_OVERWRITE", str(overwrite))

    assert build.superseded_adapter_roots(game) == []


def test_install_refuses_a_proxy_not_matching_the_recorded_owned_hash(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    build = _build_module()
    game = tmp_path / "game"
    package = tmp_path / "package"
    (game / "Binaries").mkdir(parents=True)
    (game / "GAMEDATA/MODS").mkdir(parents=True)
    (package / "Binaries").mkdir(parents=True)
    (package / "GAMEDATA/MODS").mkdir(parents=True)
    _runtime(game / "Binaries/SearchProbes", build, b"recorded owned proxy")
    (game / "Binaries/winmm.dll").write_bytes(b"foreign replacement")
    _runtime(package / "Binaries/SearchProbes", build, b"new proxy")
    (package / "Binaries/winmm.dll").write_bytes(b"new proxy")
    _adapter(package / "GAMEDATA/MODS/SearchProbes")
    from nms_packaging import installer

    monkeypatch.setattr(installer, "nms_running", lambda: False)

    with pytest.raises(build.BuildError, match="foreign WINMM proxy"):
        build.install_tree(package, game)


def test_install_refuses_running_nms_before_reading_package(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    build = _build_module()
    from nms_packaging import installer

    monkeypatch.setattr(installer, "nms_running", lambda: True)
    with pytest.raises(build.BuildError, match="NMS must be stopped"):
        build.install_tree(tmp_path / "package", tmp_path / "game")


def test_copy_runtime_excludes_cache_and_tooling_files(tmp_path: Path) -> None:
    build = _build_module()
    source = tmp_path / "source"
    (source / "app/__pycache__").mkdir(parents=True)
    (source / "app/logs").mkdir()
    (source / "app/cache.cache").write_bytes(b"cache")
    (source / "app/keep.py").write_text("print('ok')\n", encoding="utf-8")
    (source / "app/bytecode.pyc").write_bytes(b"pyc")
    (source / "app/noop_attach.py").write_text("tooling\n", encoding="utf-8")

    destination = tmp_path / "destination"
    build.copy_runtime(source, destination)

    assert (destination / "app/keep.py").is_file()
    assert not (destination / "app/__pycache__").exists()
    assert not (destination / "app/logs").exists()
    assert not (destination / "app/cache.cache").exists()
    assert not (destination / "app/bytecode.pyc").exists()
    assert not (destination / "app/noop_attach.py").exists()


def test_compile_proxy_uses_native_bootstrap_sources(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    build = _build_module()
    from nms_packaging import distribution

    source = tmp_path / "native-bootstrap"
    source.mkdir()
    (source / "winmm_proxy.c").write_text("source\n", encoding="utf-8")
    (source / "winmm_proxy.def").write_text("exports\n", encoding="utf-8")
    destination = tmp_path / "winmm.dll"
    calls: list[list[str]] = []

    monkeypatch.setattr(
        distribution.shutil,
        "which",
        lambda name: "/usr/bin/gcc" if name == "x86_64-w64-mingw32-gcc" else None,
    )
    monkeypatch.setenv("SQN_NMS_PROXY_CACHE", str(tmp_path / "cache"))

    def fake_run(command: list[str], **kwargs: object):
        calls.append(command)
        if command[0] == "objdump":
            return type("Result", (), {"stdout": "pei-x86-64\ntimeBeginPeriod\ntimeEndPeriod"})()
        Path(command[command.index("-o") + 1]).write_bytes(b"native dll")
        return type("Result", (), {"stdout": ""})()

    monkeypatch.setattr(distribution, "run", fake_run)
    build.compile_proxy(source, destination)

    assert calls[0][0] == "/usr/bin/gcc"
    assert str(source / "winmm_proxy.c") in calls[0]
    assert str(source / "winmm_proxy.def") in calls[0]

    calls.clear()
    destination.unlink()
    build.compile_proxy(source, destination)
    assert destination.read_bytes() == b"native dll"
    assert calls == [["objdump", "-p", str(destination)]]

    cached_dll = next((tmp_path / "cache").glob("*.dll"))
    cached_dll.write_bytes(b"corrupt cache")
    calls.clear()
    destination.unlink()
    build.compile_proxy(source, destination)
    assert calls[0][0] == "/usr/bin/gcc"

    (source / "winmm_proxy.def").write_text("changed exports\n", encoding="utf-8")
    calls.clear()
    destination.unlink()
    build.compile_proxy(source, destination)
    assert calls[0][0] == "/usr/bin/gcc"


def test_cli_resolves_repository_root_from_packaging_module() -> None:
    _build_module()
    from nms_packaging.cli import repository_root

    assert repository_root() == Path(__file__).parents[5]
