from __future__ import annotations

import hashlib
import json
import subprocess
import tomllib
from pathlib import Path

from .catalog import ResolvedArtifact
from .errors import InvestigationError
from .paths import PROBE_OVERLAY, PROBE_RUNTIME_ROOT


def git_status(project: Path) -> str | None:
    result = subprocess.run(
        ["git", "-C", str(project), "status", "--porcelain=v2", "-z", "--untracked-files=no"],
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        check=False,
    )
    return result.stdout.decode("utf-8", errors="replace") if result.returncode == 0 else None


def _probe_pack_details(root: Path) -> dict:
    resolved = root.expanduser().resolve()
    manifest = resolved / "probe-pack.toml"
    if not manifest.is_file():
        raise InvestigationError(
            "probe_pack_invalid", f"probe pack manifest is missing: {manifest}"
        )
    try:
        value = tomllib.loads(manifest.read_text(encoding="utf-8"))
    except (OSError, tomllib.TOMLDecodeError) as exc:
        raise InvestigationError(
            "probe_pack_invalid", f"cannot read probe pack manifest {manifest}: {exc}"
        ) from exc
    if value.get("schema_version") != 1:
        raise InvestigationError("probe_pack_invalid", f"unsupported probe pack: {manifest}")
    pack_id = value.get("id")
    if not isinstance(pack_id, str) or not pack_id:
        raise InvestigationError("probe_pack_invalid", f"probe pack id is missing: {manifest}")
    sources = value.get("sources", [])
    resources = value.get("resources", [])
    mixins = value.get("mixins", [])
    if not all(
        isinstance(items, list) and all(isinstance(item, str) and item for item in items)
        for items in (sources, resources, mixins)
    ):
        raise InvestigationError(
            "probe_pack_invalid", f"sources, resources, and mixins must be string arrays: {manifest}"
        )
    source_paths = [(resolved / item).resolve() for item in sources]
    resource_paths = [(resolved / item).resolve() for item in resources]
    paths = [*source_paths, *resource_paths]
    if any(path != resolved and resolved not in path.parents for path in paths):
        raise InvestigationError("probe_pack_invalid", f"probe pack path escapes its root: {manifest}")
    missing = next((path for path in paths if not path.is_dir()), None)
    if missing is not None:
        raise InvestigationError("probe_pack_invalid", f"probe pack input is missing: {missing}")
    input_files = []
    content = hashlib.sha256()
    for path in sorted(
        item for directory in paths for item in directory.rglob("*") if item.is_file()
    ):
        relative = path.relative_to(resolved).as_posix()
        file_hash = hashlib.sha256(path.read_bytes()).hexdigest()
        content.update(relative.encode())
        content.update(file_hash.encode())
        input_files.append(
            {"path": relative, "sha256": file_hash, "size": path.stat().st_size}
        )
    required_source_paths = value.get("required_source_paths", [])
    if not isinstance(required_source_paths, list) or not all(
        isinstance(item, str) and item for item in required_source_paths
    ):
        raise InvestigationError(
            "probe_pack_invalid",
            f"required_source_paths must be an array of strings: {manifest}",
        )
    return {
        "id": pack_id,
        "version": str(value.get("version", "")),
        "root": str(resolved),
        "manifest": str(manifest),
        "manifest_sha256": hashlib.sha256(manifest.read_bytes()).hexdigest(),
        "content_sha256": content.hexdigest(),
        "inputs": input_files,
        "sources": [str(path) for path in source_paths],
        "resources": [str(path) for path in resource_paths],
        "mixins": mixins,
        "capabilities": value.get("capabilities", []),
        "required_source_paths": required_source_paths,
    }


def _validate_required_source_paths(project: Path, packs: list[dict]) -> None:
    resolved_project = project.expanduser().resolve()
    for pack in packs:
        for relative in pack.get("required_source_paths", []):
            required = resolved_project / relative
            if not required.is_dir():
                raise InvestigationError(
                    "probe_pack_source_missing",
                    f"probe pack {pack['id']!r} requires {relative!r} in the project "
                    f"source tree, but the directory does not exist — this pack likely "
                    f"needs a different branch",
                    details={
                        "pack_id": pack["id"],
                        "required_path": relative,
                        "project": str(resolved_project),
                    },
                )


def probe_overlay_command(
    loader: str,
    probe_packs: tuple[Path, ...] = (),
    compile_artifacts: tuple[tuple[ResolvedArtifact, str], ...] = (),
    runtime_artifacts: tuple[ResolvedArtifact, ...] = (),
    runtime_output: Path | None = None,
    client_run_dir: Path | None = None,
    runtime_evidence: Path | None = None,
    project: Path | None = None,
    production: bool = False,
    neoforge_client_home: Path | None = None,
    launcher_profile_template: Path | None = None,
) -> tuple[list[str], dict]:
    if loader not in {"fabric", "neoforge"}:
        raise InvestigationError(
            "probe_overlay_unsupported", f"the probe overlay does not support loader {loader!r}"
        )
    if not PROBE_OVERLAY.is_file():
        raise InvestigationError(
            "probe_overlay_missing", f"probe overlay input is missing: {PROBE_OVERLAY}"
        )
    packs = [_probe_pack_details(PROBE_RUNTIME_ROOT)]
    packs.extend(_probe_pack_details(path) for path in probe_packs)
    if project is not None:
        _validate_required_source_paths(project, packs)
    pack_ids = [pack["id"] for pack in packs]
    if len(pack_ids) != len(set(pack_ids)):
        raise InvestigationError("probe_pack_invalid", "probe pack IDs must be unique")
    mixins = list(dict.fromkeys(mixin for pack in packs for mixin in pack["mixins"]))
    compile_inputs = [
        {
            "id": artifact.id,
            "path": str(artifact.path),
            "sha256": artifact.sha256,
            "mapping": mapping,
        }
        for artifact, mapping in compile_artifacts
    ]
    runtime_inputs = [
        {
            "id": artifact.id,
            "path": str(artifact.path),
            "filename": artifact.filename,
            "sha256": artifact.sha256,
        }
        for artifact in runtime_artifacts
    ]
    if runtime_inputs and runtime_output is None:
        raise InvestigationError(
            "probe_runtime_artifact_invalid",
            "runtime artifacts require an owned runtime output directory",
        )
    details = {
        "overlay": str(PROBE_OVERLAY),
        "runtime": str(PROBE_RUNTIME_ROOT),
        "manifest": packs[0]["manifest"],
        "manifest_sha256": packs[0]["manifest_sha256"],
        "packs": packs,
        "mixins": mixins,
        "compile_artifacts": compile_inputs,
        "runtime_artifacts": runtime_inputs,
        "runtime_output": None if runtime_output is None else str(runtime_output),
        "client_run_dir": None if client_run_dir is None else str(client_run_dir),
        "runtime_evidence": None if runtime_evidence is None else str(runtime_evidence),
        "sentinel": "SQUINCH_DEVELOPMENT_PROBE",
    }
    arguments = [
        "--init-script",
        str(PROBE_OVERLAY),
        f"-PsquinchProbeRuntime={PROBE_RUNTIME_ROOT}",
        f"-PsquinchProbeLoader={loader}",
        f"-PsquinchProbePacksJson={json.dumps(packs, separators=(',', ':'))}",
        f"-PsquinchProbeMixinsJson={json.dumps(mixins, separators=(',', ':'))}",
        f"-PsquinchProbeCompileArtifactsJson={json.dumps(compile_inputs, separators=(',', ':'))}",
        f"-PsquinchProbeRuntimeArtifactsJson={json.dumps(runtime_inputs, separators=(',', ':'))}",
    ]
    if runtime_output is not None:
        arguments.append(f"-PsquinchProbeRuntimeOutput={runtime_output}")
    if client_run_dir is not None:
        arguments.append(f"-PsquinchClientRunDir={client_run_dir}")
    if runtime_evidence is not None:
        arguments.append(f"-PsquinchProbeRuntimeEvidence={runtime_evidence}")
    if production:
        arguments.append("-PsquinchProbeProduction=true")
    if neoforge_client_home is not None:
        arguments.append(f"-PsquinchNeoForgeClientHome={neoforge_client_home}")
    if launcher_profile_template is not None:
        arguments.append(f"-PsquinchLauncherProfileTemplate={launcher_profile_template}")
    return arguments, details
