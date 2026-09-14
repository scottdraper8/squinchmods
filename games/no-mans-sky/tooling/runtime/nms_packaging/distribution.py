from __future__ import annotations

import hashlib
import json
import os
import shutil
import tempfile
import time
import uuid
import zipfile
from email.parser import Parser
from pathlib import Path

from .adapter import native_adapter, validate_adapter
from .common import (
    FEDORA_MINGW_IMAGE,
    MOD_NATIVE_BOOTSTRAP,
    MOD_SOURCE,
    NMS_VERSION,
    OWNED_PROXY_HASH,
    PRODUCT_MARKER,
    BuildError,
    file_hash,
    run,
)


def prepared_runtime(runtime_dir: Path, *, rebuild: bool, script_dir: Path) -> Path:
    command = [str(script_dir / "prepare_search_runtime.sh")]
    if rebuild:
        command.append("--rebuild")
    env = dict(os.environ)
    env["SQN_NMS_RUNTIME_ROOT"] = str(runtime_dir)
    run(command, env=env)
    return runtime_dir


def compile_proxy(source_dir: Path, destination: Path) -> None:
    source_files = [source_dir / "winmm_proxy.c", source_dir / "winmm_proxy.def"]
    compiler = shutil.which("x86_64-w64-mingw32-gcc")
    common = [
        "-std=c11",
        "-Os",
        "-Wall",
        "-Wextra",
        "-Werror",
        "-shared",
        "-s",
        "-Wl,--no-insert-timestamp",
        "-Wl,--kill-at",
    ]
    recipe_payload = {
        "schema": 1,
        "sources": [file_hash(path) for path in source_files],
        "flags": common,
        "compiler": (
            {
                "path": compiler,
                "sha256": file_hash(Path(compiler))
                if compiler and Path(compiler).is_file()
                else None,
            }
            if compiler
            else None
        ),
        "container": FEDORA_MINGW_IMAGE,
        "container_command": (
            "dnf -q clean all && dnf -q -y --refresh install mingw64-gcc && "
            "x86_64-w64-mingw32-gcc [flags] /src/winmm_proxy.c "
            "/src/winmm_proxy.def -o /out/winmm.dll"
        ),
    }
    recipe = json.dumps(recipe_payload, sort_keys=True).encode("utf-8")
    cache_key = hashlib.sha256(recipe).hexdigest()
    cache_root = Path(
        os.environ.get(
            "SQN_NMS_PROXY_CACHE",
            source_dir.parents[2] / "investigation-state/native-proxy-cache",
        )
    )
    cached = cache_root / f"{cache_key}.dll"
    metadata = cached.with_suffix(".json")
    if cached.is_file() and metadata.is_file():
        try:
            record = json.loads(metadata.read_text(encoding="utf-8"))
            if (
                record.get("schema") == 1
                and record.get("recipe") == recipe_payload
                and record.get("dll_sha256") == file_hash(cached)
            ):
                shutil.copy2(cached, destination)
                _validate_proxy(destination)
                return
        except (AttributeError, OSError, TypeError, ValueError, json.JSONDecodeError, BuildError):
            pass
    if compiler:
        run(
            [
                compiler,
                *common,
                str(source_dir / "winmm_proxy.c"),
                str(source_dir / "winmm_proxy.def"),
                "-o",
                str(destination),
            ]
        )
    else:
        if not shutil.which("podman"):
            raise BuildError(
                "x86_64-w64-mingw32-gcc or podman is required to build winmm.dll"
            )
        with tempfile.TemporaryDirectory(
            prefix="search-probes-native-"
        ) as temporary_text:
            temporary = Path(temporary_text)
            shutil.copy2(source_dir / "winmm_proxy.c", temporary / "winmm_proxy.c")
            shutil.copy2(source_dir / "winmm_proxy.def", temporary / "winmm_proxy.def")
            output = temporary / "out"
            output.mkdir()
            command = " ".join(
                [
                    "x86_64-w64-mingw32-gcc",
                    *common,
                    "/src/winmm_proxy.c",
                    "/src/winmm_proxy.def",
                    "-o",
                    "/out/winmm.dll",
                ]
            )
            run(
                [
                    "podman",
                    "run",
                    "--rm",
                    "--pull=missing",
                    "-v",
                    f"{temporary}:/src:ro,Z",
                    "-v",
                    f"{output}:/out:Z",
                    FEDORA_MINGW_IMAGE,
                    "bash",
                    "-lc",
                    f"dnf -q clean all && dnf -q -y --refresh install mingw64-gcc && {command}",
                ],
                capture=True,
                timeout=600.0,
            )
            shutil.copy2(output / "winmm.dll", destination)
    _validate_proxy(destination)
    cache_root.mkdir(parents=True, exist_ok=True)
    temporary = cache_root / f".{cache_key}.{uuid.uuid4().hex}.tmp"
    metadata_temporary = temporary.with_suffix(".json.tmp")
    shutil.copy2(destination, temporary)
    temporary.replace(cached)
    metadata_temporary.write_text(
        json.dumps(
            {"schema": 1, "recipe": recipe_payload, "dll_sha256": file_hash(cached)},
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    metadata_temporary.replace(metadata)


def _validate_proxy(path: Path) -> None:
    details = run(["objdump", "-p", str(path)], capture=True).stdout
    if "pei-x86-64" not in details:
        raise BuildError("native bootstrap is not a 64-bit PE DLL")
    for symbol in ("timeBeginPeriod", "timeEndPeriod"):
        if symbol not in details:
            raise BuildError(f"native bootstrap does not export {symbol}")


def copy_runtime(source: Path, destination: Path) -> None:
    ignored = shutil.ignore_patterns(
        "__pycache__",
        "*.pyc",
        "noop_attach.py",
        "logs",
        "*.cache",
    )
    shutil.copytree(source, destination, ignore=ignored)


def write_package_readme(path: Path) -> None:
    path.write_text(
        """Search Probes for No Man's Sky 7.01

This archive is rooted at the No Man's Sky installation directory. It contains:
- Binaries/winmm.dll: a two-export forwarder that starts the bundled runtime.
- Binaries/SearchProbes: pinned embedded Python, native dependencies, and the search engine.
- GAMEDATA/MODS/SearchProbes: the Search Probes Guide/navigation adapter.

The build is pinned to one NMS.exe hash and fails closed after a game update. Do not overwrite an
unrelated Binaries/winmm.dll; proxy/chain-loader compatibility must be established separately.
Windows loads the application-local WINMM proxy automatically. Proton must use a native-first
winmm override; the repository build command configures that override during local installation.

Launch NMS normally. Search Probes initializes silently; F7 shows or hides the form. Saved presets
live under Binaries/SearchProbes/app/.resident-search and should be retained when updating.
""",
        encoding="utf-8",
    )


def write_third_party_notices(product: Path, destination: Path) -> None:
    site_packages = product / "Lib/site-packages"
    packages: list[tuple[str, str, str]] = []
    for metadata_path in sorted(site_packages.glob("*.dist-info/METADATA")):
        metadata = Parser().parsestr(
            metadata_path.read_text(encoding="utf-8", errors="replace")
        )
        name = metadata.get("Name", metadata_path.parent.name)
        version = metadata.get("Version", "unknown version")
        license_text = (
            metadata.get("License-Expression") or metadata.get("License") or ""
        )
        license_text = " ".join(license_text.split())
        if not license_text or len(license_text) > 100:
            license_text = "see retained package metadata/license files"
        packages.append((name, version, license_text))
    lines = [
        "Search Probes - third-party notices",
        "",
        "The bundled CPython runtime is distributed under the license retained at",
        "Binaries/SearchProbes/LICENSE.txt.",
        "",
        "Bundled Python packages:",
    ]
    lines.extend(
        f"- {name} {version}: {license_text}"
        for name, version, license_text in packages
    )
    lines.extend(
        (
            "",
            "Upstream METADATA, RECORD, and license files are retained under each package's",
            "Binaries/SearchProbes/Lib/site-packages/*.dist-info directory.",
            "",
        )
    )
    destination.write_text("\n".join(lines), encoding="utf-8")


def tree_manifest(root: Path) -> dict[str, object]:
    records = []
    for path in sorted(root.rglob("*")):
        if path.is_symlink():
            raise BuildError(f"package contains a symlink: {path}")
        if path.is_file() and path.name != "SEARCH_PROBES_MANIFEST.json":
            records.append(
                {
                    "path": path.relative_to(root).as_posix(),
                    "bytes": path.stat().st_size,
                    "sha256": file_hash(path),
                }
            )
    return {
        "schema": 1,
        "product": "Search Probes",
        "nms_version": NMS_VERSION,
        "files": records,
    }


def build_package(
    output: Path,
    *,
    repo_root: Path,
    game_root: Path,
    runtime_root: Path,
    rebuild_runtime: bool,
    adapter_root: Path | None,
) -> tuple[Path, Path]:
    script_dir = Path(__file__).resolve().parent.parent
    output = output.expanduser().resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    if output.exists():
        marker = output / "Binaries/SearchProbes/SEARCH_PROBES_PRODUCT"
        if not marker.is_file() or marker.read_text(encoding="utf-8") != PRODUCT_MARKER:
            raise BuildError(
                f"refusing to replace an unowned output directory: {output}"
            )
    adapter = (
        validate_adapter(adapter_root)
        if adapter_root
        else native_adapter(repo_root, game_root)
    )
    runtime = prepared_runtime(
        runtime_root, rebuild=rebuild_runtime, script_dir=script_dir
    )
    temporary = Path(tempfile.mkdtemp(prefix=f".{output.name}.", dir=output.parent))
    try:
        binaries = temporary / "Binaries"
        product = binaries / "SearchProbes"
        app = product / "app"
        binaries.mkdir(parents=True)
        compile_proxy(repo_root / MOD_NATIVE_BOOTSTRAP, binaries / "winmm.dll")
        copy_runtime(runtime, product)
        app.mkdir()
        python_path = product / "python313._pth"
        path_lines = python_path.read_text(encoding="utf-8").splitlines()
        if "app" not in path_lines:
            insertion = (
                path_lines.index("import site")
                if "import site" in path_lines
                else len(path_lines)
            )
            path_lines.insert(insertion, "app")
            python_path.write_text("\n".join(path_lines) + "\n", encoding="utf-8")
        shutil.copytree(
            repo_root / MOD_SOURCE,
            app / "search_probes",
            ignore=shutil.ignore_patterns("__pycache__", "*.pyc"),
        )
        state = app / ".resident-search"
        state.mkdir()
        (state / "launch-mode.json").write_text(
            '{"overlay_enabled":true,"protocol":1}\n', encoding="utf-8"
        )
        (product / "SEARCH_PROBES_PRODUCT").write_text(PRODUCT_MARKER, encoding="utf-8")
        (product / OWNED_PROXY_HASH).write_text(
            file_hash(binaries / "winmm.dll") + "\n", encoding="ascii"
        )
        shutil.copytree(adapter, temporary / "GAMEDATA/MODS/SearchProbes")
        write_package_readme(temporary / "README-SEARCH-PROBES.txt")
        write_third_party_notices(product, temporary / "THIRD-PARTY-NOTICES.txt")
        manifest = tree_manifest(temporary)
        (temporary / "SEARCH_PROBES_MANIFEST.json").write_text(
            json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
        archive_temporary = output.parent / f".{output.name}.zip.tmp"
        archive_final = output.parent / f"{output.name}.zip"
        archive_temporary.unlink(missing_ok=True)
        with zipfile.ZipFile(
            archive_temporary, "w", compression=zipfile.ZIP_DEFLATED
        ) as archive:
            for path in sorted(temporary.rglob("*")):
                if path.is_file():
                    archive.write(path, path.relative_to(temporary).as_posix())
        if output.exists():
            backup = output.with_name(f".{output.name}.old-{time.time_ns()}")
            output.replace(backup)
            temporary.replace(output)
            shutil.rmtree(backup)
        else:
            temporary.replace(output)
        archive_temporary.replace(archive_final)
    except BaseException:
        shutil.rmtree(temporary, ignore_errors=True)
        raise
    return output, archive_final


def verify_manifest(root: Path) -> None:
    manifest = json.loads(
        (root / "SEARCH_PROBES_MANIFEST.json").read_text(encoding="utf-8")
    )
    expected = {record["path"]: record["sha256"] for record in manifest["files"]}
    actual = {
        path.relative_to(root).as_posix(): file_hash(path)
        for path in root.rglob("*")
        if path.is_file() and path.name != "SEARCH_PROBES_MANIFEST.json"
    }
    if actual != expected:
        raise BuildError("built package does not match its file manifest")
