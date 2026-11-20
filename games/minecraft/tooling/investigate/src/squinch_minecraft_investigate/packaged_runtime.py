"""Run exact, externally assembled runtimes; never build or inject a probe.

Results are external assertions, not independent proof of Minecraft compatibility.
The supplied test mod owns observation of loaded identities and production behavior.
"""

from __future__ import annotations

import fnmatch
import hashlib
import json
import os
import re
import shutil
import stat
import subprocess
import sys
import zipfile
from pathlib import Path

import jsonschema

from .artifact_inspection import inspect_artifact
from .client import _display_runtime_root, _remove_display_runtime
from .errors import CleanupError, InvestigationError
from .output import timestamp
from .owned_operation import (
    recover_finite_service,
    run_finite_service,
    write_active_manifest,
)
from .paths import (
    PACKAGE_DIR,
    REPOSITORY_ROOT,
    RUNS_ROOT,
    STATE_ROOT,
    active_path,
    lock_path,
)
from .processes import proc_identity
from .server import (
    OWNERSHIP,
    load_owned_active,
    new_run_id,
    uninterruptible_owned_processes,
)
from .tranche import prepare_owned_directory, require_scratch_input, require_tranche

AUTHORITY = "external-structured-assertions-and-owned-lifecycle"
_RESERVED_ENV = {
    "SQUINCH_TRANCHE",
    "SQUINCH_TRANCHE_WORKSPACE",
    "SQUINCH_INVESTIGATE_RUN_ID",
}
_RESERVED_ROOTS = {
    "mods",
    "results",
    "logs",
    "crash-reports",
    "home",
    "tmp",
    ".squinch-investigate",
}
_FORBIDDEN_COMPONENTS = {
    ".git",
    ".gradle",
    ".venv",
    ".vscode",
    ".directory",
    ".DS_Store",
    "Desktop.ini",
    "ehthumbs.db",
    "Thumbs.db",
    "__pycache__",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
    "node_modules",
    "dist",
}


def _fail(message: str) -> InvestigationError:
    return InvestigationError("packaged_runtime_invalid", message)


def _json(path: Path) -> dict:
    def unique(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError(f"duplicate JSON key: {key}")
            result[key] = value
        return result

    try:
        value = json.loads(
            path.read_text(encoding="utf-8"),
            object_pairs_hook=unique,
            parse_constant=lambda value: (_ for _ in ()).throw(ValueError(value)),
        )
    except (OSError, UnicodeError, ValueError) as exc:
        raise _fail(f"invalid JSON at {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise _fail(f"JSON must be an object: {path}")
    return value


def _schema(value: dict, name: str) -> None:
    schema = json.loads((PACKAGE_DIR / "schemas" / name).read_text(encoding="utf-8"))
    try:
        jsonschema.Draft202012Validator(schema).validate(value)
    except jsonschema.ValidationError as exc:
        raise _fail(f"{name}: {exc.json_path}: {exc.message}") from exc


def _path(value: str | Path, *, task: bool = False) -> Path:
    path = Path(value)
    if not path.is_absolute() or str(path) != str(value) or ".." in path.parts:
        raise _fail(f"path must be exact, canonical and absolute: {value}")
    if task:
        require_scratch_input(path)
    # Check components before resolve/open, including dangling links.
    current = Path(path.anchor)
    for part in path.parts[1:]:
        current /= part
        if current.is_symlink():
            raise _fail(f"symbolic links are forbidden: {current}")
    if path.resolve() != path:
        raise _fail(f"noncanonical path: {path}")
    return path


def _regular(path: Path) -> None:
    _path(path)
    info = path.lstat()
    if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
        raise _fail(f"expected an unlinked regular file: {path}")


def _hash(path: Path) -> str:
    _regular(path)
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _verify(path: Path, expected: str) -> None:
    if _hash(path) != expected:
        raise _fail(f"SHA-256 mismatch: {path}")


def _relative(name: str) -> Path:
    path = Path(name)
    if not re.fullmatch(r"[A-Za-z0-9_.+-]+(?:/[A-Za-z0-9_.+-]+)*", name) or any(
        part in {".", ".."} for part in name.split("/")
    ):
        raise _fail(f"unsafe relative filename: {name}")
    return path


def _tree(root: Path, *, hashes: bool = True) -> dict[str, str]:
    _path(root)
    if not root.is_dir():
        raise _fail(f"not a directory: {root}")
    files = {}
    pending = [root]
    while pending:
        directory = pending.pop()
        with os.scandir(directory) as entries:
            for entry in entries:
                path = Path(entry.path)
                _relative(path.relative_to(root).as_posix())
                if entry.name in _FORBIDDEN_COMPONENTS or entry.name.endswith(
                    (".egg-info", ".pyc", ".pyo", ".pyd")
                ):
                    raise _fail(f"source/cache state is not a runtime input: {path}")
                info = entry.stat(follow_symlinks=False)
                if stat.S_ISDIR(info.st_mode):
                    pending.append(path)
                elif stat.S_ISREG(info.st_mode) and info.st_nlink == 1:
                    files[path.relative_to(root).as_posix()] = (
                        _hash(path) if hashes else ""
                    )
                else:
                    raise _fail(f"links and special files are forbidden: {path}")
    return files


def resolve_packaged_project(value: str | Path) -> Path:
    project = _path(value)
    if not project.is_dir():
        raise _fail(f"project does not exist: {project}")
    _id, workspace = require_tranche()
    tranches = workspace.parent
    if project.is_relative_to(tranches) and not project.is_relative_to(workspace):
        raise _fail(f"project belongs to another tranche: {project}")
    return project


def _git(project: Path, *args: str) -> bytes:
    result = subprocess.run(
        ["git", "-c", "core.fsmonitor=false", "-C", str(project), *args],
        capture_output=True,
        check=False,
        env={**os.environ, "GIT_OPTIONAL_LOCKS": "0"},
    )
    if result.returncode:
        raise _fail(
            f"cannot snapshot source Git state: {project}: {result.stderr.decode(errors='replace')}"
        )
    return result.stdout


# Never traverse generated/denied state when hashing a declared source boundary.
# Ignored *source* is still hashed; Git ignore flags are not a content identity.
_SOURCE_EXCLUDED_DIRS = _FORBIDDEN_COMPONENTS | {
    ".qa-runs",
    ".qa-incoming",
    ".qa-staging",
    ".qa-current",
    ".qa-trash",
}
_SOURCE_DENIED_ROOTS = tuple(
    REPOSITORY_ROOT / name
    for name in (
        ".direnv",
        ".vscode",
        "logs",
        "games/minecraft/reference",
        "games/no-mans-sky/reference",
        "games/minecraft/qa-state",
        "games/minecraft/investigation-state",
        "games/no-mans-sky/investigation-state",
        ".agent-docs/.cache",
        ".agent-docs/tmp",
        ".agent-docs/private",
        "site/.output",
        "site/.tanstack",
        "site/.wrangler",
    )
)
_SOURCE_EXCLUDED_GLOBS = (
    "*.egg-info",
    "*.py[cod]",
    ".directory",
    ".DS_Store",
    "Desktop.ini",
    "ehthumbs.db",
    "Thumbs.db",
)


_SOURCE_INVESTIGATIONS = REPOSITORY_ROOT / "games/minecraft/investigations"


def _source_excluded(path: Path) -> bool:
    if any(
        part in _SOURCE_EXCLUDED_DIRS
        or any(fnmatch.fnmatchcase(part, pattern) for pattern in _SOURCE_EXCLUDED_GLOBS)
        for part in path.parts
    ) or any(path.is_relative_to(root) for root in _SOURCE_DENIED_ROOTS):
        return True
    # These generated-output restrictions belong to the former investigation tree,
    # not arbitrary production directories named build/run or tracked binary inputs.
    # A wrapper JAR and tools/build/*.py are ordinary declared source elsewhere.
    if path.is_relative_to(_SOURCE_INVESTIGATIONS):
        relative = path.relative_to(_SOURCE_INVESTIGATIONS)
        return any(part in {"build", "run"} for part in relative.parts) or any(
            fnmatch.fnmatchcase(relative.name, pattern)
            for pattern in ("*.class", "*.jar", "*.log", "*.log.gz")
        )
    return False


def _source_roots(spec: dict, git_root: Path) -> list[Path]:
    roots = [Path(value) for value in spec["source_roots"]]
    _id, workspace = require_tranche()
    project = Path(spec["project"])
    for root in roots:
        if (
            not root.is_relative_to(git_root)
            or _source_excluded(root)
            or workspace.is_relative_to(root)
            or root.is_relative_to(workspace.parent)
            and not root.is_relative_to(workspace)
            or root.is_relative_to(workspace)
            and not git_root.is_relative_to(workspace)
            or not _path(root).is_dir()
            or Path(_git(root, "rev-parse", "--show-toplevel").decode().strip())
            != git_root
        ):
            raise _fail(
                f"source root must be a focused directory in the project's Git worktree, outside task state: {root}"
            )
    if not any(
        project.is_relative_to(root) or root.is_relative_to(project) for root in roots
    ):
        raise _fail(
            "source roots must cover the build project or its production source directories"
        )
    if any(a != b and a.is_relative_to(b) for a in roots for b in roots):
        raise _fail("source roots must not overlap")
    return roots


def _source_snapshot(project: Path, source_roots: list[str]) -> dict:
    git_root = Path(_git(project, "rev-parse", "--show-toplevel").decode().strip())
    roots = _source_roots(
        {"project": str(project), "source_roots": source_roots}, git_root
    )
    files = {}
    for root in roots:
        pending = [root]
        while pending:
            directory = pending.pop()
            with os.scandir(directory) as entries:
                for entry in entries:
                    # Filter names BEFORE stat/open/traversal, including denied links.
                    path = directory / entry.name
                    if _source_excluded(path):
                        continue
                    info = entry.stat(follow_symlinks=False)
                    if stat.S_ISDIR(info.st_mode):
                        pending.append(path)
                    else:
                        files[path.relative_to(git_root).as_posix()] = _hash(path)
    pathspecs = [root.relative_to(git_root).as_posix() for root in roots]
    exclusions = [
        f":(top,exclude,glob)**/{name}/**" for name in sorted(_SOURCE_EXCLUDED_DIRS)
    ] + [f":(top,exclude,glob)**/{pattern}" for pattern in _SOURCE_EXCLUDED_GLOBS]
    exclusions.append(":(top,exclude,glob)**/*.egg-info/**")
    exclusions.extend(
        f":(top,exclude,literal){root.relative_to(git_root).as_posix()}"
        for root in _SOURCE_DENIED_ROOTS
        if root.is_relative_to(git_root)
    )
    if _SOURCE_INVESTIGATIONS.is_relative_to(git_root):
        prefix = _SOURCE_INVESTIGATIONS.relative_to(git_root).as_posix() + "/"
    elif git_root.is_relative_to(_SOURCE_INVESTIGATIONS):
        prefix = ""
    else:
        prefix = None
    if prefix is not None:
        exclusions.extend(
            f":(top,exclude,glob){prefix}**/{pattern}"
            for pattern in (
                "build/**",
                "run/**",
                "*.class",
                "*.jar",
                "*.log",
                "*.log.gz",
            )
        )
    return {
        "git_root": str(git_root),
        "source_roots": source_roots,
        "head": _git(git_root, "rev-parse", "HEAD").decode().strip(),
        # No whole-parent status, untracked discovery, diff drivers or submodule recursion.
        "status": _git(
            git_root,
            "status",
            "--porcelain=v2",
            "-z",
            "--untracked-files=no",
            "--ignore-submodules=all",
            "--",
            *pathspecs,
            *exclusions,
        ).decode(),
        "files": files,
    }


def _references(text: str) -> None:
    # This is a launch-reference boundary: argv, referenced @files and manifest
    # Class-Path, NOT arbitrary template resource/configuration bytes or control data.
    if (
        "\\" in text
        or "\0" in text
        or re.search(r"(?:^|[\s=:,\"'@])/", text)
        or re.search(r"(?:^|[\s=:/,\"'@])\.\.(?:/|$|[\s\"'])", text)
        or re.search(r"[A-Za-z]:/|file:|https?://", text)
    ):
        raise _fail(
            "runtime references must be relative, offline and confined to packaged inputs"
        )
    if re.search(r"-D(?:user\.(?:dir|home)|java\.(?:home|io\.tmpdir))=", text):
        raise _fail("runtime arguments cannot override owned Java directories")


def _jar_references(
    path: Path, *, agent: bool = False, executable: bool = False
) -> set[str]:
    references = set()
    try:
        with zipfile.ZipFile(path) as jar:
            # JarFile also discovers differently cased manifest entry names. Never
            # choose one of several entries (even identical names/content): Python,
            # JarFile and the native agent reader need not choose the same one.
            manifests = [
                entry
                for entry in jar.infolist()
                if entry.filename.upper() == "META-INF/MANIFEST.MF"
            ]
            if len(manifests) > 1:
                raise _fail(
                    f"ambiguous runtime manifests: {path}; package exactly one "
                    "META-INF/MANIFEST.MF entry"
                )
            if manifests:
                manifest = jar.read(manifests[0]).decode("utf-8")
                # Roles come from actual launcher options, not mere attributes.
                # Unfold continuations; named-entry attributes are not recipes.
                manifest = manifest.replace("\r\n", "\n").replace("\r", "\n")
                main = manifest.split("\n\n", 1)[0].replace("\n ", "")
                for line in main.splitlines():
                    attribute, separator, value = line.partition(":")
                    if separator and attribute.lower() == "class-path":
                        references.update(value.split())
                    if executable and attribute.lower() == "launcher-agent-class":
                        raise _fail(
                            f"executable-JAR Launcher-Agent-Class is unsupported: {path}; "
                            "remove the attribute and use an explicit packaged -javaagent "
                            "without Boot-Class-Path instead"
                        )
                    if (
                        agent
                        and attribute.lower() == "boot-class-path"
                        and value.strip()
                    ):
                        raise _fail(
                            f"agent Boot-Class-Path is unsupported: {path}; remove the "
                            "attribute and package dependencies via ordinary Class-Path "
                            "or explicit immutable launch paths instead"
                        )
    except (zipfile.BadZipFile, UnicodeError) as exc:
        raise _fail(f"invalid runtime archive: {path}") from exc
    return references


def _manifest_target(archive: str, reference: str) -> tuple[str, bool]:
    # Manifest URLs are archive-relative, unlike argv paths. Support plain local
    # relative URLs (including internal ../ and directory /), not encoded URLs,
    # queries, schemes or paths that escape the combined runtime namespace.
    if not re.fullmatch(r"[A-Za-z0-9_.+-]+(?:/[A-Za-z0-9_.+-]+)*/?", reference):
        raise _fail(f"unsupported manifest launch references: {archive}: {reference}")
    parts = list(Path(archive).parent.parts)
    for part in reference.rstrip("/").split("/"):
        if part == "..":
            if not parts:
                raise _fail(
                    f"manifest references escape runtime: {archive}: {reference}"
                )
            parts.pop()
        elif part != ".":
            parts.append(part)
    if not parts:
        raise _fail("manifest references to the runtime/output root are not supported")
    return "/".join(parts), reference.endswith("/")


def _argument_file(path: Path) -> list[str]:
    """A deliberately bounded Java argfile grammar, not shell/shlex syntax."""
    try:
        text = path.read_text(encoding="utf-8")
        if "\\" in text or any(ord(c) < 32 and c not in "\t\r\n" for c in text):
            raise ValueError(
                "backslash escapes and non-whitespace controls are unsupported"
            )
        tokens = []
        # Multiline quotes are explicitly unsupported, so a whole-line comment
        # cannot accidentally consume a continuation of a quoted Java argument.
        for line in text.split("\n"):
            if line.lstrip(" \t").startswith("#"):
                continue
            if "#" in line:
                raise ValueError("only whole-line # comments are supported")
            token = []
            quote = None
            started = False
            for char in line:
                if quote:
                    if char == quote:
                        quote = None
                    else:
                        token.append(char)
                elif char in "\"'":
                    quote = char
                    started = True
                elif char in " \t":
                    if started:
                        tokens.append("".join(token))
                        token = []
                        started = False
                else:
                    token.append(char)
                    started = True
            if quote:
                raise ValueError(
                    "unterminated or multiline quoted arguments are unsupported"
                )
            if started:
                tokens.append("".join(token))
        return tokens
    except (UnicodeError, ValueError) as exc:
        raise _fail(f"unsupported argument file {path.name}: {exc}") from exc


def _launch_inputs(spec: dict, template: Path) -> tuple[set[str], set[str]]:
    """Return immutable files and closed directories in the packaged launch graph."""
    launch_files: set[str] = set()
    launch_dirs: set[str] = set()
    agents: set[str] = set()
    executables: set[str] = set()
    arguments = iter(spec["arguments"])
    expanded = iter(())

    def next_token() -> str | None:
        # Consume only while the launcher still owns the token (including option
        # operands). Once a main/JAR/module is consumed the caller stops: remaining
        # @tokens, even inside this argfile, are literal application data. Java does
        # not recursively expand @tokens originating inside an argument file.
        nonlocal expanded
        while True:
            token = next(expanded, None)
            if token is not None:
                if token.startswith("@"):
                    raise _fail(
                        "nested argument files in launcher options are not supported"
                    )
                return token
            token = next(arguments, None)
            if token is None or not token.startswith("@"):
                return token
            name = _relative(token[1:]).as_posix()
            if name not in spec["template"]["files"]:
                raise _fail(f"argument file is not in the template manifest: {name}")
            launch_files.add(name)
            expanded = iter(_argument_file(template / name))

    packaged = {name: template / name for name in spec["template"]["files"]}
    packaged.update(
        (f"mods/{item['name']}", Path(item["path"]))
        for item in [spec["subject"], *spec["companions"]]
    )
    # JARs are potential loader inputs; non-JAR archives are data until an actual
    # file launch edge reaches them. Directory edges do not turn data ZIPs into code.
    pending = {name for name in packaged if Path(name).suffix.lower() == ".jar"}

    def include(name: str, *, directory: bool = False) -> None:
        if name in packaged and not directory:
            launch_files.add(name)
            pending.add(name)
            return
        matches = {entry for entry in packaged if entry.startswith(name + "/")}
        if not matches or name in packaged:
            raise _fail(f"launch path is not a packaged input: {name}")
        launch_files.update(matches)
        launch_dirs.add(name)

    def paths(value: str, *, kind: str = "list", wildcards: bool = True) -> None:
        _references(value)
        if kind == "directory" and (":" in value or "*" in value):
            raise _fail(
                "libraryDirectory requires one packaged directory, not a list/wildcard"
            )
        for reference in value.split(":") if kind == "list" else [value]:
            if not reference:
                raise _fail("empty launch path element")
            wildcard = wildcards and reference.endswith("/*")
            name = _relative(reference[:-2] if wildcard else reference).as_posix()
            if kind == "file" and name not in packaged:
                raise _fail(f"launch file is not a packaged input: {name}")
            include(name, directory=wildcard or kind == "directory")

    path_options = {
        "-cp",
        "-classpath",
        "--class-path",
        "-p",
        "--module-path",
        "--upgrade-module-path",
        "--patch-module",
        "-jar",
    }
    path_properties = {
        "-Djava.class.path",
        "-Djava.library.path",
        "-Djdk.module.path",
        "-Djdk.module.upgrade.path",
        "-DlegacyClassPath",
        "-DlibraryDirectory",
    }
    value_options = {
        "--add-modules",
        "--limit-modules",
        "--add-reads",
        "--add-exports",
        "--add-opens",
        "--enable-native-access",
        "--illegal-native-access",
        "--enable-final-field-mutation",
        "--illegal-final-field-mutation",
    }
    while (token := next_token()) is not None:
        option, equals, value = token.partition("=")
        if token != "-XX:-UsePerfData" and option in {
            "-XX:+UsePerfData",
            "-XX:-UsePerfData",
            "-XX:UsePerfData",
        }:
            raise _fail(
                "HotSpot performance data must remain disabled; remove "
                f"{token} and retain the runner's -XX:-UsePerfData"
            )
        if option in {"-XX:VMOptionsFile", "-XX:Flags"}:
            raise _fail(
                f"{option} is unsupported; supply its JVM options explicitly "
                "in arguments or a manifested immutable @argument-file instead"
            )
        if option in {"-XXaltjvm", "-J-XXaltjvm"}:
            raise _fail(
                f"{option} is unsupported; retain the selected Java installation's VM"
            )
        if token.startswith(("-agentlib:", "-Xrun")):
            # Named native agents include instrument aliases that accept a second
            # Java-agent JAR in otherwise opaque options. Use the typed interfaces.
            raise _fail(
                "named native agents (-agentlib/-Xrun) are unsupported; use explicit "
                "packaged -javaagent or -agentpath inputs instead"
            )
        if option in {
            "-XX:SharedArchiveFile",
            "-XX:SharedClassListFile",
            "-XX:ExtraSharedClassListFile",
            "-XX:SharedArchiveConfigFile",
        }:
            raise _fail(
                f"{option} is unsupported; retain the selected Java installation's "
                "default shared archive and use explicit packaged class paths instead"
            )
        if option in {"-XX:CompileCommandFile", "-XX:CompilerDirectivesFile"}:
            raise _fail(
                f"{option} is unsupported; supply supported compiler options explicitly "
                "in arguments or a manifested immutable @argument-file instead"
            )
        if option in {"-Duser.dir", "-Duser.home", "-Djava.home", "-Djava.io.tmpdir"}:
            raise _fail("runtime arguments cannot override owned Java directories")
        if option in {
            "-Djava.ext.dirs",
            "-Djava.endorsed.dirs",
            "-Dsun.boot.class.path",
            "-Dsun.boot.library.path",
        }:
            raise _fail(
                f"{option} is unsupported; retain the selected Java installation's "
                "standard paths and use explicit packaged class/library/boot paths instead"
            )
        if option in {"--source", "--disable-@files"}:
            raise _fail(f"unsupported Java launch recipe: {option}")
        if option in path_options | value_options | {"-m", "--module"}:
            if not equals:
                value = next_token()
                if value is None:
                    raise _fail(f"missing launch value for {option}")
            if option in value_options:
                continue
            if option in {"-m", "--module"}:
                break  # Remaining tokens are application data, not JVM options.
            if option == "--patch-module":
                _module, separator, value = value.partition("=")
                if not separator or not _module:
                    raise _fail("patch-module requires module=paths")
            paths(value, kind="file" if option == "-jar" else "list")
            if option == "-jar":
                executables.add(value)
                break
        elif option in path_properties:
            if not equals:
                raise _fail(f"{option} requires an explicit packaged path value")
            paths(
                value,
                kind="directory" if option == "-DlibraryDirectory" else "list",
                wildcards=option != "-DlegacyClassPath",
            )
        elif token.startswith(("-javaagent:", "-agentpath:")):
            name = token.split(":", 1)[1].split("=", 1)[0]
            paths(name, kind="file")
            if token.startswith("-javaagent:"):
                agents.add(name)
        elif token.startswith(
            ("-Xbootclasspath:", "-Xbootclasspath/a:", "-Xbootclasspath/p:")
        ):
            paths(token.split(":", 1)[1])
        elif not token.startswith("-"):
            _references(token)
            if token.endswith(".java"):
                raise _fail("source-language Java launch recipes are not supported")
            break
        # Unrelated -D values and application/control data remain opaque. A URL or
        # option-looking phrase inside a description is not a launch reference.
    inspected = set()
    while pending:
        name = pending.pop()
        if name in inspected:
            continue
        inspected.add(name)
        launch_files.add(name)
        path = packaged[name]
        if path.suffix.lower() != ".jar" and not zipfile.is_zipfile(path):
            continue
        # Roles are collected before traversal, so an ordinary/cyclic visit cannot
        # suppress the additional manifest boundary of an actually invoked agent.
        for reference in _jar_references(
            path, agent=name in agents, executable=name in executables
        ):
            target, directory = _manifest_target(name, reference)
            # No optional/missing edge may acquire unmanifested code later. A
            # manifest archive URL without trailing / must identify an exact file.
            if not directory and target not in packaged:
                raise _fail(
                    f"manifest launch dependency is not a packaged input: {name}: {reference}"
                )
            include(target, directory=directory)
    return launch_files, launch_dirs


def _mutable_inputs(spec: dict, template: Path, launch_files: set[str]) -> None:
    for name in spec["template"]["mutable_files"]:
        relative = _relative(name)
        # Explicit configuration only. No wildcard mutability, executable/launch/library
        # inputs, archives disguised as config, or nonexistent initial identities.
        if (
            name not in spec["template"]["files"]
            or name in launch_files
            or not (
                name in {"server.properties", "options.txt", "optionsof.txt"}
                or relative.parts[0] == "config"
                and len(relative.parts) > 1
                and relative.suffix.lower()
                in {
                    ".json",
                    ".toml",
                    ".properties",
                    ".cfg",
                    ".conf",
                    ".txt",
                    ".yaml",
                    ".yml",
                }
            )
            or zipfile.is_zipfile(template / name)
        ):
            raise _fail(f"invalid mutable configuration file: {name}")


def _base_environment(run_dir: Path) -> dict[str, str]:
    return {
        "PATH": "/usr/bin:/bin",
        "LANG": "C.UTF-8",
        "HOME": str(run_dir / "home"),
        "TMPDIR": str(run_dir / "tmp"),
        "XDG_CONFIG_HOME": str(run_dir / "home" / "config"),
        "XDG_CACHE_HOME": str(run_dir / "home" / "cache"),
        "XDG_DATA_HOME": str(run_dir / "home" / "data"),
        "PYTHONPATH": str(PACKAGE_DIR / "src"),
        "PYTHONDONTWRITEBYTECODE": "1",
        # -B alone does not prevent reading existing adjacent Python caches.
        # The fresh run owns this unused prefix; no directory is created with -B.
        "PYTHONPYCACHEPREFIX": str(run_dir / "tmp" / "unused-python-cache"),
    }


def _java_identity(spec: dict) -> dict:
    java = _path(spec["java"]["path"])
    _verify(java, spec["java"]["sha256"])
    if not os.access(java, os.X_OK):
        raise _fail(f"Java executable is not executable: {java}")
    _id, workspace = require_tranche()
    try:
        result = subprocess.run(
            [str(java), "-XX:-UsePerfData", "-version"],
            cwd=workspace,
            env={"PATH": "/usr/bin:/bin", "LANG": "C.UTF-8"},
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            timeout=10,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise _fail(f"Java identity check failed: {exc}") from exc
    version = result.stdout.decode("utf-8").strip()
    if result.returncode != 0:
        raise _fail(
            "Java identity check requires a HotSpot-compatible JVM supporting "
            f"-XX:-UsePerfData (performance data disabled): {version}"
        )
    if version != spec["java"]["version"]:
        raise _fail(f"Java -version identity mismatch: {version}")
    _verify(java, spec["java"]["sha256"])
    return {**spec["java"], "observed_version": version}


def validate_spec(path: Path) -> dict:
    path = _path(path, task=True)
    _regular(path)
    spec = _json(path)
    _schema(spec, "packaged-runtime-v1.json")
    project = resolve_packaged_project(spec["project"])
    git_root = Path(_git(project, "rev-parse", "--show-toplevel").decode().strip())
    source_roots = _source_roots(spec, git_root)
    template = _path(spec["template"]["path"], task=True)
    java = _path(spec["java"]["path"])
    _id, workspace = require_tranche()
    if (
        any(java.is_relative_to(root) for root in source_roots)
        or java.is_relative_to(git_root)
        and not workspace.is_relative_to(git_root)
        or java.is_relative_to(workspace.parent)
        and not java.is_relative_to(workspace)
    ):
        raise _fail("Java must not come from a source tree or another tranche")
    inputs = [
        path,
        template,
        *(
            _path(item["path"], task=True)
            for item in [spec["subject"], *spec["companions"]]
        ),
    ]
    for item in inputs:
        # The selected tranche may be ignored *inside* a parent Git repository, but
        # an input in a nested source worktree is never a scratch recipe.
        parent = item if item.is_dir() else item.parent
        while parent != workspace:
            if (parent / ".git").exists() or (parent / ".git").is_symlink():
                raise _fail(f"input is inside a source worktree: {item}")
            parent = parent.parent
        if (
            any(item.is_relative_to(root) for root in source_roots)
            or item.is_relative_to(project)
            and not (workspace != project and workspace.is_relative_to(project))
            or item.is_relative_to(git_root)
            and not workspace.is_relative_to(git_root)
            or item.is_relative_to(RUNS_ROOT)
        ):
            raise _fail(f"input is source-tree or previous-run state: {item}")
    names = [item["name"].casefold() for item in [spec["subject"], *spec["companions"]]]
    if len(names) != len(set(names)):
        raise _fail("subject and companion output names must be unique")
    sources = [item["path"] for item in [spec["subject"], *spec["companions"]]]
    if len(sources) != len(set(sources)):
        raise _fail("artifacts must be separately enumerated unique inputs")
    variables = [item["environment"] for item in spec["results"]]
    result_names = [item["name"].casefold() for item in spec["results"]]
    if len(variables) != len(set(variables)) or len(result_names) != len(
        set(result_names)
    ):
        raise _fail("result variables and basenames must be unique")
    if (
        set(variables) & (set(spec["environment"]) | _RESERVED_ENV)
        or set(spec["environment"]) & _RESERVED_ENV
    ):
        raise _fail("control, result and reserved environments must be disjoint")
    actual = _tree(template)
    if actual != spec["template"]["files"]:
        raise _fail(
            "template manifest does not exactly match ALL regular template files/hashes"
        )
    for name in actual:
        relative = _relative(name)
        if (
            relative.parts[0] in _RESERVED_ROOTS
            or relative.name.casefold() in result_names
            or relative.name in {"application-exit.json", "gradlew", "pom.xml"}
            or relative.suffix in {".log", ".gz", ".java", ".gradle"}
        ):
            raise _fail(
                f"template contains implicit mods, stale output or reserved state: {name}"
            )
    mods = template / "mods"
    if mods.exists() and (not mods.is_dir() or any(mods.iterdir())):
        raise _fail("template mods directory must be empty")
    # Empty mods is permitted, but no other reserved directory (even empty) is an input.
    for name in _RESERVED_ROOTS - {"mods"}:
        if (template / name).exists():
            raise _fail(f"template contains a reserved output directory: {name}")
    for item in [spec["subject"], *spec["companions"]]:
        _verify(Path(item["path"]), item["sha256"])
        try:
            with zipfile.ZipFile(item["path"]) as jar:
                if jar.testzip() is not None:
                    raise _fail(f"corrupt artifact: {item['path']}")
        except zipfile.BadZipFile as exc:
            raise _fail(f"artifact is not a JAR: {item['path']}") from exc
    inspection = inspect_artifact(Path(spec["subject"]["path"]))
    if not inspection["clean"]:
        raise _fail(
            f"subject contains known development probe markers: {inspection['findings']}"
        )
    launch_files, _launch_dirs = _launch_inputs(spec, template)
    _mutable_inputs(spec, template, launch_files)
    _java_identity(spec)
    return spec


def _inspect_results(state: dict) -> list[dict]:
    results = []
    spec = state["spec"]
    for contract in spec["results"]:
        path = Path(state["artifact_dir"]) / "results" / contract["name"]
        _regular(path)
        value = _json(path)
        _schema(value, "packaged-runtime-result-v1.json")
        if (
            value["run_id"] != state["run_id"]
            or value["subject_sha256"] != spec["subject"]["sha256"]
            or value["runtime"]
            != {key: spec[key] for key in ("loader", "minecraft", "side")}
        ):
            raise _fail(f"result run/runtime/subject identity mismatch: {path}")
        cases = [case["id"] for case in value["cases"]]
        if len(cases) != len(set(cases)) or set(cases) != set(contract["cases"]):
            raise _fail(
                f"result must contain exactly the required unique case IDs: {path}"
            )
        results.append(
            {
                "environment": contract["environment"],
                "path": str(path),
                "sha256": _hash(path),
                "result": value,
            }
        )
    return results


def _application_exited(state: dict) -> bool:
    path = Path(state["application_exit"])
    if not path.exists() and not path.is_symlink():
        return False
    _regular(path)
    value = _json(path)
    if (
        value.get("status") != "exited"
        or type(value.get("exit_code")) is not int
        or value["exit_code"] != 0
    ):
        raise _fail(f"inner Java application did not exit successfully: {value}")
    return True


def _diagnostics(state: dict) -> None:
    run_dir = Path(state["run_dir"])
    reports = run_dir / "crash-reports"
    if reports.exists():
        _path(reports)
        if not reports.is_dir() or any(reports.iterdir()):
            raise _fail("runtime wrote a crash report")
    logs = [Path(state["log_path"])]
    log_root = run_dir / "logs"
    if log_root.exists():
        _tree(log_root, hashes=False)  # Reject links/special files before reading logs.
        logs.extend(log_root.glob("*.log"))
    logs.extend(run_dir.glob("hs_err_pid*.log"))
    for path in logs:
        _regular(path)
        if path.name.startswith("hs_err_pid") or re.search(
            r"\bFATAL\b|A fatal error has been detected|Encountered an unexpected exception|"
            r"Exception in thread|Failed to start the minecraft server",
            path.read_text(errors="replace"),
        ):
            raise _fail(f"fatal/crash diagnostic: {path}")


def _integrity(state: dict) -> None:
    spec = state["spec"]
    if (
        validate_spec(Path(state["spec_path"])) != spec
        or _hash(Path(state["spec_path"])) != state["spec_sha256"]
    ):
        raise _fail("specification changed during the operation")
    mods = Path(state["run_dir"]) / "mods"
    expected = {
        item["name"]: item["sha256"] for item in [spec["subject"], *spec["companions"]]
    }
    if _tree(mods) != expected:
        raise _fail("staged mods changed or include unrequested files")
    state["mutable_files_after"] = {}
    for name, sha256 in spec["template"]["files"].items():
        path = Path(state["run_dir"]) / name
        if name in spec["template"]["mutable_files"]:
            state["mutable_files_after"][name] = _hash(path)
        else:
            _verify(path, sha256)
    runtime_files = _tree(Path(state["run_dir"]), hashes=False)
    _launch_files, launch_dirs = _launch_inputs(spec, Path(spec["template"]["path"]))
    packaged_files = set(spec["template"]["files"]) | {
        f"mods/{name}" for name in expected
    }
    for name in runtime_files.keys() - packaged_files:
        if any(name.startswith(directory + "/") for directory in launch_dirs):
            raise _fail(f"unmanifested file in a launch directory: {name}")
    state["source_after"] = _source_snapshot(
        Path(state["project"]), spec["source_roots"]
    )
    if state["source_after"] != state["source_before"]:
        raise _fail("runtime polluted source Git state")


def validate_active_paths(state: dict) -> None:
    """Additional side-specific confinement before status/recovery touches owned state."""
    if re.fullmatch(r"\d{8}T\d{6}Z-[0-9a-f]{10}", state["run_id"]) is None:
        raise InvestigationError("invalid_state", "invalid packaged runtime run ID")
    for field in ("active_path", "artifact_dir", "run_dir", "log_path"):
        _path(state[field], task=True)
    contract = state.get("spec")
    if not isinstance(contract, dict) or any(
        contract.get(key) != state.get(key) for key in ("project", "loader", "side")
    ):
        raise InvestigationError(
            "invalid_state", "packaged runtime contract identity changed"
        )
    expected_exit = Path(state["artifact_dir"]) / "application-exit.json"
    if state.get("application_exit") != str(expected_exit) or state.get("side") not in {
        "server",
        "client",
    }:
        raise InvestigationError(
            "invalid_state", "invalid packaged runtime side/exit ownership"
        )
    _path(expected_exit, task=True)
    if state["side"] == "server":
        if state.get("display") is not None:
            raise InvestigationError("invalid_state", "server cannot own a display")
    else:
        display = state.get("display", {})
        # Derive the root from this user's actual runtime, not from untrusted active JSON.
        root = _display_runtime_root(dict(os.environ))
        if (
            not isinstance(display, dict)
            or display.get("runtime_root") != str(root)
            or display.get("runtime_dir")
            != str(root / f"squinch-{state['run_id'][-10:]}")
            or display.get("wayland_display") != f"squinch-{state['run_id'][-10:]}"
            or display.get("backend") != "headless"
        ):
            raise InvestigationError(
                "invalid_state", "invalid packaged runtime display ownership"
            )
        _path(display["runtime_dir"])


def _cleanup_display(state: dict) -> list[str]:
    if state["side"] != "client":
        return []
    path = Path(state["display"]["runtime_dir"])
    try:
        _path(path)  # Includes dangling links, which Path.exists() alone would miss.
    except InvestigationError as exc:
        return [f"display runtime ownership: {exc}"]
    failures = _remove_display_runtime(state)
    if path.exists() or path.is_symlink():
        failures.append(f"display runtime remains after cleanup: {path}")
    return failures


def run_packaged_runtime(path: Path) -> dict:
    spec = validate_spec(
        path
    )  # Implementation boundary, independent of CLI validation.
    project = Path(spec["project"])
    loader = spec["loader"]
    root = prepare_owned_directory("minecraft", "investigate")
    if root != STATE_ROOT:
        raise _fail("selected tranche differs from imported operation state root")
    prepare_owned_directory("minecraft", "investigate", "runs")
    prepare_owned_directory("minecraft", "investigate", "active")
    prepare_owned_directory("minecraft", "investigate", "locks")
    active = _path(active_path(project, loader), task=True)
    _path(lock_path(project, loader), task=True)
    blocked = uninterruptible_owned_processes(active.parent)
    if blocked:
        raise InvestigationError(
            "host_degraded",
            "owned uninterruptible processes prevent launch",
            details={"processes": blocked},
        )
    run_id = new_run_id()
    artifact = RUNS_ROOT / run_id
    run_dir = artifact / "runtime"
    log_path = artifact / "packaged-runtime.log"
    exit_path = artifact / "application-exit.json"
    environment = _base_environment(run_dir)
    environment.update(spec["environment"])
    environment.update(
        {
            item["environment"]: str(artifact / "results" / item["name"])
            for item in spec["results"]
        }
    )
    environment["SQUINCH_INVESTIGATE_RUN_ID"] = run_id
    display = None
    if spec["side"] == "client":
        display_root = _display_runtime_root(dict(os.environ))
        display_name = f"squinch-{run_id[-10:]}"
        display = {
            "backend": "headless",
            "runtime_root": str(display_root),
            "runtime_dir": str(display_root / display_name),
            "wayland_display": display_name,
        }
        environment.update(
            {
                "XDG_RUNTIME_DIR": display["runtime_dir"],
                "WAYLAND_DISPLAY": display_name,
                "ALSOFT_DRIVERS": "null",
                "WLR_BACKENDS": "headless",
                "WLR_HEADLESS_OUTPUTS": "1",
                "WLR_LIBINPUT_NO_DEVICES": "1",
                "WLR_RENDERER": "pixman",
            }
        )
    java_command = [
        spec["java"]["path"],
        "-XX:-UsePerfData",
        f"-Duser.home={run_dir / 'home'}",
        f"-Djava.io.tmpdir={run_dir / 'tmp'}",
        *spec["arguments"],
    ]
    inner = [
        sys.executable,
        "-m",
        "squinch_minecraft_investigate.application_exit",
        "--output",
        str(exit_path),
        "--cwd",
        str(run_dir),
        "--",
        *java_command,
    ]
    # env -i also discards user-systemd's manager environment (JAVA_TOOL_OPTIONS,
    # CLASSPATH, personal display/launcher state and inherited SQUINCH_* controls).
    command = [
        "/usr/bin/env",
        "-i",
        *(f"{key}={value}" for key, value in sorted(environment.items())),
        *(["cage", "-d", "--"] if display else []),
        *inner,
    ]
    display_created = False
    fields = {
        "side": spec["side"],
        "spec": spec,
        "spec_path": str(path),
        "spec_sha256": _hash(path),
        "source_before": _source_snapshot(project, spec["source_roots"]),
        "java": _java_identity(spec),
        "application_exit": str(exit_path),
        "display": display,
        "authority": AUTHORITY,
        "java_command": java_command,
        "environment": environment,
    }

    def prepare() -> None:
        nonlocal display_created
        if validate_spec(path) != spec or _hash(path) != fields["spec_sha256"]:
            raise _fail("specification changed before preparation")
        if _source_snapshot(project, spec["source_roots"]) != fields["source_before"]:
            raise _fail("source Git state changed before preparation")
        shutil.copytree(spec["template"]["path"], run_dir, symlinks=True)
        if _tree(run_dir) != spec["template"]["files"]:
            raise _fail("template changed during copy")
        mods = run_dir / "mods"
        mods.mkdir(exist_ok=True)
        for item in [spec["subject"], *spec["companions"]]:
            _verify(Path(item["path"]), item["sha256"])
            target = mods / item["name"]
            with target.open("xb") as output, Path(item["path"]).open("rb") as source:
                shutil.copyfileobj(source, output)
            _verify(target, item["sha256"])
        for directory in (run_dir / "home", run_dir / "tmp", artifact / "results"):
            directory.mkdir(mode=0o700)
        _integrity({**fields, "project": str(project), "run_dir": str(run_dir)})
        if display:
            Path(display["runtime_dir"]).mkdir(mode=0o700)
            display_created = True

    def poll_failure(state: dict) -> BaseException | None:
        try:
            _diagnostics(state)
            # An early result alone never completes the operation.
            _application_exited(state)
        except (InvestigationError, OSError, ValueError) as exc:
            return exc
        return None

    def validate(state: dict) -> dict:
        if not _application_exited(state):
            raise _fail("inner Java application exit sentinel is missing")
        _diagnostics(state)
        _integrity(state)
        state["results"] = _inspect_results(state)
        return state["results"]

    def post_teardown_validate(state: dict) -> None:
        # Always check late writes after service teardown, including on rejected runs.
        # These invalidate the run, not actual process/thread/display cleanup.
        _integrity(state)
        _diagnostics(state)
        if "results" in state and (
            not _application_exited(state)
            or _inspect_results(state) != state["results"]
        ):
            raise _fail("required results or application exit changed during teardown")

    try:
        state, _results = run_finite_service(
            project=project,
            loader=loader,
            operation="packaged-runtime",
            ownership=OWNERSHIP,
            run_id=run_id,
            artifact_dir=artifact,
            run_dir=run_dir,
            log_path=log_path,
            active_path=active,
            lock_path=lock_path(project, loader),
            command=command,
            environment={},
            timeout=spec["timeout"],
            load_active=load_owned_active,
            prepare=prepare,
            validate=validate,
            poll_failure=poll_failure,
            poll_complete=_application_exited,
            cleanup=_cleanup_display,
            post_teardown_validate=post_teardown_validate,
            state_fields=fields,
        )
    except BaseException:
        # Finite-service startup rollback removes in-tranche preparation. Its cleanup
        # callback runs only after launch; roll back the external display here as well.
        if not active.exists() and display_created:
            failures = _cleanup_display({**fields, "run_id": run_id})
            if failures:
                # Retain a valid launching intent for explicit doctor recovery; no process
                # identity is invented and no unrelated external path can be removed.
                marker = {
                    **fields,
                    "ownership": OWNERSHIP,
                    "schema_version": 3,
                    "operation": "packaged-runtime",
                    "run_id": run_id,
                    "project": str(project),
                    "loader": loader,
                    "artifact_dir": str(artifact),
                    "run_dir": str(run_dir),
                    "log_path": str(log_path),
                    "active_path": str(active),
                    "lifecycle": "launching",
                    "started_at": timestamp(),
                    "finished_at": None,
                    "command": command,
                    "launcher": proc_identity(os.getpid()),
                    "process": None,
                    "service": {
                        "unit": f"squinch-mc-{run_id.lower()}.service",
                        "cgroup": "",
                        "wrapper": None,
                    },
                    "owned_processes": [],
                    "owned_threads": [],
                    "thread_capture_errors": [],
                    "cleanup": {"complete": False, "failures": failures},
                }
                write_active_manifest(marker)
                raise CleanupError(
                    "packaged runtime display rollback failed",
                    details={
                        "run_id": run_id,
                        "artifact_dir": str(artifact),
                        "failures": failures,
                    },
                )
        raise
    return state


def recover_packaged_runtime(project: Path, loader: str, timeout: float) -> dict:
    return recover_finite_service(
        project=project,
        loader=loader,
        timeout=timeout,
        lock_path=lock_path(project, loader),
        load_active=load_owned_active,
        operations={"packaged-runtime"},
        cleanup=_cleanup_display,
    )
