#!/usr/bin/env bash
set -euo pipefail

readonly PYTHON_VERSION="3.13.15"
readonly PYTHON_ARCHIVE="python-${PYTHON_VERSION}-embed-amd64.zip"
readonly PYTHON_URL="https://www.python.org/ftp/python/${PYTHON_VERSION}/${PYTHON_ARCHIVE}"
readonly PYTHON_SHA256="d1f04d990aee1253d8569e8e5104e30fa9f5fa830899f14843448872d936a2cf"
readonly SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
readonly MOD_ROOT="${SQN_NMS_MOD_ROOT:-${SCRIPT_DIR}/../../mods/search-probes}"
readonly STEAM_ROOT="${SQN_STEAM_ROOT:-${HOME}/.local/share/Steam}"
readonly RUNTIME_ROOT="${SQN_NMS_RUNTIME_ROOT:-${STEAM_ROOT}/steamapps/compatdata/275850/nmspy-runtime}"
readonly REQUIREMENTS_SPEC="${MOD_ROOT}/dependencies/runtime-requirements.in"
readonly REQUIREMENTS_LOCK="${MOD_ROOT}/dependencies/runtime-requirements.txt"

rebuild=false
if [[ ${1:-} == "--rebuild" ]]; then
  rebuild=true
elif [[ $# -ne 0 ]]; then
  echo "usage: $0 [--rebuild]" >&2
  exit 2
fi

case "$RUNTIME_ROOT" in
  */steamapps/compatdata/275850/nmspy-runtime) ;;
  *)
    echo "runtime destination must end in steamapps/compatdata/275850/nmspy-runtime" >&2
    exit 2
    ;;
esac

for command in curl find python3 sha256sum unzip uv; do
  if ! command -v "$command" >/dev/null; then
    echo "required command is unavailable: $command" >&2
    exit 1
  fi
done

verify_runtime() {
  python3 - "$1" "$REQUIREMENTS_SPEC" <<'PY'
from pathlib import Path
import sys

root = Path(sys.argv[1])
requirements = Path(sys.argv[2])
required = {}
for line in requirements.read_text(encoding="utf-8").splitlines():
    if line and not line.startswith("#"):
        name, version = line.split("==", 1)
        required[name.casefold().replace("-", "_")] = version

installed = {}
for metadata in (root / "Lib/site-packages").glob("*.dist-info/METADATA"):
    fields = {}
    for line in metadata.read_text(encoding="utf-8", errors="replace").splitlines():
        if line.startswith("Name: "):
            fields["name"] = line[6:]
        elif line.startswith("Version: "):
            fields["version"] = line[9:]
    if fields.keys() >= {"name", "version"}:
        installed[fields["name"].casefold().replace("-", "_")] = fields["version"]

if installed != required:
    missing = sorted(set(required) - set(installed))
    extra = sorted(set(installed) - set(required))
    wrong = sorted(name for name in set(required) & set(installed) if required[name] != installed[name])
    raise SystemExit(f"runtime package mismatch: missing={missing}, extra={extra}, wrong={wrong}")

main = (root / "Lib/site-packages/pymhf/main.py").read_text(encoding="utf-8")
injected = (root / "Lib/site-packages/pymhf/injected.py").read_text(encoding="utf-8")
entry = next((root / "Lib/site-packages").glob("nmspy-*.dist-info/entry_points.txt"))
entry_text = entry.read_text(encoding="utf-8")
if "if start_exe else {log_pid}" not in main or "Injected runtime exception" not in main:
    raise SystemExit("pyMHF attach-survival patch is absent")
if "_squinch_before_injected_shutdown" not in injected:
    raise SystemExit("pyMHF hook-restoration patch is absent")
if "pymhf_rtfunc" in entry_text or "instantiate_globals" in entry_text:
    raise SystemExit("NMSpy eager runtime-global entry point remains enabled")
for relative in (
    "python.exe",
    "python313.dll",
    "Lib/site-packages/dearpygui/_dearpygui.pyd",
    "Lib/site-packages/cyminhook/_cyminhook.cp313-win_amd64.pyd",
    "Lib/site-packages/pyrun_injected/dll.cp313-win_amd64.pyd",
    "Lib/site-packages/win32/win32gui.pyd",
):
    if not (root / relative).is_file():
        raise SystemExit(f"runtime file is absent: {relative}")
print(f"validated prepared search runtime: {root}")
PY
}

if [[ -d "$RUNTIME_ROOT" && "$rebuild" == false ]]; then
  verify_runtime "$RUNTIME_ROOT"
  exit 0
fi

runtime_parent="$(dirname -- "$RUNTIME_ROOT")"
mkdir -p -- "$runtime_parent"
stage="$(mktemp -d --tmpdir="$runtime_parent" .nmspy-runtime.XXXXXXXX)"
archive="$stage/$PYTHON_ARCHIVE"
cleanup() {
  if [[ -d "$stage" ]]; then
    gio trash "$stage" 2>/dev/null || find "$stage" -depth -delete
  fi
}
trap cleanup EXIT

curl --fail --location --proto '=https' --tlsv1.2 --output "$archive" "$PYTHON_URL"
echo "$PYTHON_SHA256  $archive" | sha256sum --check --status
unzip -q "$archive" -d "$stage"
mkdir -p -- "$stage/Lib/site-packages"
printf 'python313.zip\n.\nLib/site-packages\n\nimport site\n' > "$stage/python313._pth"
uv pip install \
  --exact \
  --python-platform x86_64-pc-windows-msvc \
  --python-version 3.13 \
  --target "$stage/Lib/site-packages" \
  --require-hashes \
  --requirements "$REQUIREMENTS_LOCK"

entry_points="$(find "$stage/Lib/site-packages" -path '*/nmspy-*.dist-info/entry_points.txt' -print -quit)"
if [[ -z "$entry_points" ]]; then
  echo "NMSpy entry_points.txt was not installed" >&2
  exit 1
fi
python3 - "$stage/Lib/site-packages" "$entry_points" <<'PY'
from pathlib import Path
import sys

site = Path(sys.argv[1])
entry = Path(sys.argv[2])

main = site / "pymhf/main.py"
text = main.read_text(encoding="utf-8")
old = '''        def close_callback(x):
            print("pyMHF exiting...")
            for _pid in {pm_binary.process_id, log_pid}:
'''
new = '''        def close_callback(x):
            exception = x.exception()
            if exception is not None:
                print(f"Injected runtime exception: {exception!r}")
            print("pyMHF exiting...")
            pids = {pm_binary.process_id, log_pid} if start_exe else {log_pid}
            for _pid in pids:
'''
if text.count(old) != 1:
    raise SystemExit("pinned pyMHF main.py no longer has the expected attach-shutdown block")
main.write_text(text.replace(old, new), encoding="utf-8")

injected = site / "pymhf/injected.py"
text = injected.read_text(encoding="utf-8")
old = '''    loop.run_forever()

    # Close the server.
'''
new = '''    loop.run_forever()

    # Restore product-owned hooks before their Python callbacks and trampolines can disappear.
    for mod in tuple(mod_manager.mods.values()):
        cleanup = getattr(mod, "_squinch_before_injected_shutdown", None)
        if cleanup is not None:
            try:
                cleanup()
            except Exception:
                logging.exception("System Search pre-shutdown cleanup failed: %s", mod._mod_name)

    # Close the server.
'''
if text.count(old) != 1:
    raise SystemExit("pinned pyMHF injected.py no longer has the expected event-loop boundary")
injected.write_text(text.replace(old, new), encoding="utf-8")

text = entry.read_text(encoding="utf-8")
old = '''[pymhf_rtfunc]
globals = nmspy.globals:globals.instantiate_globals

'''
if text.count(old) != 1:
    raise SystemExit("pinned NMSpy entry point no longer has the expected eager-global block")
entry.write_text(text.replace(old, ""), encoding="utf-8")
PY
unlink "$archive"
verify_runtime "$stage"

if [[ -e "$RUNTIME_ROOT" ]]; then
  backup="${RUNTIME_ROOT}.backup.$(date -u +%Y%m%dT%H%M%SZ)"
  mv -- "$RUNTIME_ROOT" "$backup"
  echo "moved the previous runtime to: $backup"
fi
mv -- "$stage" "$RUNTIME_ROOT"
trap - EXIT
echo "prepared search runtime: $RUNTIME_ROOT"
