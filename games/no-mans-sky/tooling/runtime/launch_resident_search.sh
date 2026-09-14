#!/usr/bin/env bash
set -euo pipefail

readonly EXPECTED_EXE_SHA256="4c3b9e0149a7b898d2d24e3899ffb5df102805579bc5e3f66fe955dfa4a6f20d"
readonly SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
readonly MOD_SOURCE="$(cd -- "${SCRIPT_DIR}/../../mods/search-probes/src" && pwd)"
readonly STEAM_ROOT="${SQN_STEAM_ROOT:-${HOME}/.local/share/Steam}"
readonly PROTON_ROOT="${SQN_NMS_PROTON_ROOT:-${STEAM_ROOT}/steamapps/common/Proton - Experimental}"
readonly DEFAULT_NMS_ROOT="${STEAM_ROOT}/steamapps/common/No Man's Sky"
readonly NMS_ROOT="${SQN_NMS_GAME_ROOT:-$DEFAULT_NMS_ROOT}"
readonly NMS_PREFIX="${SQN_NMS_PREFIX:-${STEAM_ROOT}/steamapps/compatdata/275850/pfx}"
readonly RUNTIME_ROOT="${SQN_NMS_RUNTIME_ROOT:-${STEAM_ROOT}/steamapps/compatdata/275850/nmspy-runtime}"

for command in nsenter python3 rg sha256sum ss; do
  if ! command -v "$command" >/dev/null; then
    echo "required command is unavailable: $command" >&2
    exit 1
  fi
done

mapfile -t nms_pids < <(
  python3 - <<'PY'
from pathlib import Path

for comm in Path("/proc").glob("[0-9]*/comm"):
    try:
        if comm.read_text(encoding="utf-8").strip() == "NMS.exe":
            print(comm.parent.name)
    except (FileNotFoundError, PermissionError, ProcessLookupError):
        pass
PY
)
if (( ${#nms_pids[@]} != 1 )); then
  echo "expected exactly one running NMS.exe, found ${#nms_pids[@]}" >&2
  exit 1
fi
readonly NMS_PID="${nms_pids[0]}"

actual_hash="$(sha256sum "$NMS_ROOT/Binaries/NMS.exe" | cut -d' ' -f1)"
if [[ "$actual_hash" != "$EXPECTED_EXE_SHA256" ]]; then
  echo "NMS.exe hash changed; refusing current-build runtime addresses" >&2
  exit 1
fi
if ss -H -ltn 'sport = :6770' | rg -q .; then
  echo "pyMHF executor port 6770 is already active; refusing a second attachment" >&2
  exit 1
fi
"$SCRIPT_DIR/prepare_search_runtime.sh"

launch_mode_path="$SCRIPT_DIR/.resident-search/launch-mode.json"
mkdir -p -- "$(dirname -- "$launch_mode_path")"
python3 - "$launch_mode_path" "${SQN_RESIDENT_SEARCH_NO_OVERLAY:-0}" <<'PY'
import json
import os
import sys
import tempfile

path, no_overlay = sys.argv[1:]
directory = os.path.dirname(path)
descriptor, temporary = tempfile.mkstemp(prefix=".launch-mode.", suffix=".tmp", dir=directory)
try:
    with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
        json.dump(
            {"protocol": 1, "overlay_enabled": no_overlay != "1"},
            stream,
            sort_keys=True,
            separators=(",", ":"),
        )
        stream.write("\n")
    os.replace(temporary, path)
except BaseException:
    try:
        os.unlink(temporary)
    except FileNotFoundError:
        pass
    raise
PY

if ! rg --quiet --follow --glob '*.MXML' 'Launch Saved Search Probe' "$NMS_ROOT/GAMEDATA/MODS" || \
  ! rg --quiet --follow --glob '*.EXML' 'SE_SQN_SS_LUSH_R08' "$NMS_ROOT/GAMEDATA/MODS" || \
  ! rg --quiet --follow --glob '*.EXML' 'SE_SQN_SS3_P08' "$NMS_ROOT/GAMEDATA/MODS" || \
  ! rg --quiet --follow --glob '*.EXML' 'SE_SQN_SS3_FORM' "$NMS_ROOT/GAMEDATA/MODS"; then
  echo "the current R08 Search Probes navigation adapter is not staged" >&2
  exit 1
fi

attach_marker_path="$SCRIPT_DIR/.resident-search/attached-host-process.json"
python3 - "$attach_marker_path" "$NMS_PID" <<'PY'
import json
import os
import sys
import tempfile

path, pid_text = sys.argv[1:]
pid = int(pid_text)
stat_fields = open(f"/proc/{pid}/stat", encoding="utf-8").read().split()
start_ticks = int(stat_fields[21])
try:
    existing = json.load(open(path, encoding="utf-8"))
except (FileNotFoundError, json.JSONDecodeError, OSError, TypeError, ValueError):
    existing = None
if isinstance(existing, dict) and (
    existing.get("protocol") == 1
    and existing.get("pid") == pid
    and existing.get("start_ticks") == start_ticks
):
    raise SystemExit(
        "the resident runtime has already attempted attachment to this NMS process; "
        "restart NMS before attaching again"
    )

directory = os.path.dirname(path)
descriptor, temporary = tempfile.mkstemp(prefix=".attached-host-process.", suffix=".tmp", dir=directory)
try:
    with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
        json.dump(
            {"protocol": 1, "pid": pid, "start_ticks": start_ticks},
            stream,
            sort_keys=True,
            separators=(",", ":"),
        )
        stream.write("\n")
    os.replace(temporary, path)
except BaseException:
    try:
        os.unlink(temporary)
    except FileNotFoundError:
        pass
    raise
PY

runtime_python="Z:${RUNTIME_ROOT}/python.exe"
probe_path="Z:${MOD_SOURCE}/search_probes/resident_search_probe.py"

exec nsenter --target "$NMS_PID" --mount --user --preserve-credentials -- env \
  PYTEST_VERSION=1 \
  PYTHONPATH="Z:${MOD_SOURCE}" \
  WINEPREFIX="$NMS_PREFIX" \
  WINEDEBUG=-all \
  WINEFSYNC=1 \
  WINEDLLPATH="$PROTON_ROOT/files/lib/vkd3d:$PROTON_ROOT/files/lib/wine" \
  LD_LIBRARY_PATH="$PROTON_ROOT/files/lib/x86_64-linux-gnu:$PROTON_ROOT/files/lib/i386-linux-gnu:/usr/lib/pressure-vessel/overrides/lib/x86_64-linux-gnu/aliases:/usr/lib/pressure-vessel/overrides/lib/i386-linux-gnu/aliases" \
  PATH="$PROTON_ROOT/files/bin:/usr/bin:/bin" \
  "$PROTON_ROOT/files/bin/wine" \
  "$runtime_python" \
  "$probe_path" \
  NMS.exe
