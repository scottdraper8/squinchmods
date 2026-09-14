#!/usr/bin/env bash
set -euo pipefail

readonly SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
readonly MOD_SOURCE="$(cd -- "${SCRIPT_DIR}/../../mods/search-probes/src" && pwd)"
export PYTHONPATH="${MOD_SOURCE}${PYTHONPATH:+:${PYTHONPATH}}"
readonly CLIENT="$SCRIPT_DIR/../client/launch-latest-save.py"
readonly STATE_ROOT="$SCRIPT_DIR/.resident-search"
readonly PHASE="${1:-full}"
readonly CANDIDATE_LIMIT="${SQN_MATRIX_CANDIDATE_LIMIT:-20000}"
readonly TIMEOUT="${SQN_MATRIX_TIMEOUT:-3600}"

hook_pid=""

nms_count() {
  python3 - <<'PY'
from pathlib import Path

count = 0
for comm in Path("/proc").glob("[0-9]*/comm"):
    try:
        count += comm.read_text(encoding="utf-8").strip() == "NMS.exe"
    except (FileNotFoundError, PermissionError, ProcessLookupError):
        pass
print(count)
PY
}

health_gate() {
  local label="$1"
  local expected_nms="$2"
  local output="/tmp/sqn-nms-matrix-${label}.json"
  local uninterruptible=""
  uninterruptible="$(
    python3 - <<'PY'
import time
from pathlib import Path

def blocked_processes():
    blocked = set()
    for stat in Path("/proc").glob("[0-9]*/stat"):
        try:
            raw = stat.read_text(encoding="utf-8")
            name_start = raw.find("(")
            name_stop = raw.rfind(")")
            if name_start < 0 or name_stop < name_start or len(raw) <= name_stop + 2:
                continue
            if raw[name_stop + 2] == "D":
                blocked.add(f"{stat.parent.name}:{raw[name_start + 1:name_stop]}")
        except (FileNotFoundError, PermissionError, ProcessLookupError):
            pass
    return blocked

# Kernel workers can enter D for a single display flip or device transaction. Treat a process as
# stuck only when the same PID remains uninterruptible throughout the bounded sample window.
blocked = blocked_processes()
for _ in range(9):
    time.sleep(0.5)
    blocked &= blocked_processes()
print(",".join(sorted(blocked)))
PY
  )"
  if [[ -n "$uninterruptible" ]]; then
    echo "${label^^} health gate refused uninterruptible processes: $uninterruptible" >&2
    return 1
  fi
  local attempt=""
  for attempt in $(seq 1 5); do
    tooling/squinch nms-investigate doctor --json >"$output" || true
    if python3 - "$output" "$label" "$expected_nms" <<'PY'
import json
import sys

path, label, expected_nms = sys.argv[1:]
checks = json.load(open(path, encoding="utf-8"))["data"]["checks"]
health = checks["host_health"]
processes = checks["game"]["running_processes"]
print(
    f"{label.upper()} healthy={health['healthy']} "
    f"load={'/'.join(health['load_average'])} "
    f"D={len(health['uninterruptible_processes'])} NMS={len(processes)}",
    flush=True,
)
if not health["healthy"] or len(processes) != int(expected_nms):
    raise SystemExit(f"{label} health gate refused the lifecycle")
PY
    then
      return 0
    fi
    sleep 1
  done
  return 1
}

close_nms() {
  local window=""
  window="$(timeout 5s xdotool search --name "^No Man's Sky$" 2>/dev/null | tail -1 || true)"
  if [[ -n "$window" ]]; then
    timeout 5s xdotool windowactivate --sync "$window" >/dev/null 2>&1 || true
    timeout 5s xdotool key --window "$window" Alt+F4 >/dev/null 2>&1 || true
  fi
  for _attempt in $(seq 1 20); do
    [[ "$(nms_count)" == 0 ]] && return 0
    sleep 1
  done
  steam -shutdown >/dev/null 2>&1 || true
  for _attempt in $(seq 1 60); do
    [[ "$(nms_count)" == 0 ]] && return 0
    sleep 1
  done
  return 1
}

cleanup() {
  python3 "$SCRIPT_DIR/resident_search_control.py" stop --wait=10 \
    >/dev/null 2>&1 || true
  if [[ "$(nms_count)" != 0 ]]; then
    close_nms || true
  fi
  if [[ -n "$hook_pid" ]]; then
    kill -TERM "$hook_pid" 2>/dev/null || true
    wait "$hook_pid" 2>/dev/null || true
  fi
}
trap cleanup EXIT

if [[ "$PHASE" != smoke && "$PHASE" != full ]]; then
  echo "usage: $0 [smoke|full]" >&2
  exit 2
fi

health_gate prelaunch 0
echo "AUTOMATED CLIENT LAUNCH START"
"$CLIENT" --failure-screenshot /tmp/squinch-nms-launch-failure.png
echo "GAMEPLAY WAIT COMPLETE"
health_gate prehook 1

old_session="$(
  python3 -c "import json; print(json.load(open('$STATE_ROOT/current.json')).get('session_id', ''))" \
    2>/dev/null || true
)"
SQN_RESIDENT_SEARCH_NO_OVERLAY=1 "$SCRIPT_DIR/launch_resident_search.sh" \
  >/tmp/sqn-resident-matrix-e2e.log 2>&1 &
hook_pid="$!"

session_state=""
overlay_state=""
for _attempt in $(seq 1 90); do
  if [[ -f "$STATE_ROOT/current.json" ]]; then
    new_session="$(
      python3 -c "import json; print(json.load(open('$STATE_ROOT/current.json')).get('session_id', ''))" \
        2>/dev/null || true
    )"
    if [[ -n "$new_session" && "$new_session" != "$old_session" ]]; then
      readarray -t state_values < <(
        python3 - "$STATE_ROOT" <<'PY'
import json
import pathlib
import sys

root = pathlib.Path(sys.argv[1])
current = json.load(open(root / "current.json", encoding="utf-8"))
path = root / "sessions" / current["session_id"] / "state.json"
state = json.load(open(path, encoding="utf-8")) if path.exists() else {}
print(state.get("state", ""))
print(str(state.get("overlay_enabled", "")).lower())
PY
      )
      session_state="${state_values[0]:-}"
      overlay_state="${state_values[1]:-}"
      [[ "$session_state" == ready ]] && break
    fi
  fi
  if ! kill -0 "$hook_pid" 2>/dev/null; then
    echo "ATTACH FAILED" >&2
    sed -n '1,320p' /tmp/sqn-resident-matrix-e2e.log >&2
    exit 1
  fi
  sleep 1
done

if [[ "$session_state" != ready ]]; then
  echo "ATTACH TIMEOUT" >&2
  exit 1
fi
if [[ "$overlay_state" != false ]]; then
  echo "HEADLESS ASSERTION FAILED: overlay_enabled=$overlay_state" >&2
  exit 1
fi
echo "ATTACHED session=$new_session overlay_enabled=$overlay_state"

python3 "$SCRIPT_DIR/resident_search_control.py" submit ping \
  --id matrix-e2e-start --wait=20 >/dev/null
echo "${PHASE^^} MATRIX START"
python3 -u "$SCRIPT_DIR/resident_search_matrix.py" "$PHASE" \
  --candidate-limit "$CANDIDATE_LIMIT" --timeout "$TIMEOUT"
echo "${PHASE^^} MATRIX PASSED"
python3 "$SCRIPT_DIR/resident_search_control.py" submit ping \
  --id matrix-e2e-end --wait=20 >/dev/null
health_gate postmatrix 1

python3 - "$STATE_ROOT" "$PHASE" <<'PY'
import json
import pathlib
import sys

root = pathlib.Path(sys.argv[1])
phase = sys.argv[2]
current = json.load(open(root / "current.json", encoding="utf-8"))
session = root / "sessions" / current["session_id"]
summaries = sorted(
    session.glob(f"results/matrix-{phase}-*-summary.json"),
    key=lambda path: path.stat().st_mtime_ns,
)
if not summaries:
    raise SystemExit("matrix completed without a retained summary")
summary = json.load(open(summaries[-1], encoding="utf-8"))
print(f"RETAINED_MATRIX_SUMMARY {summaries[-1].resolve()}")
print(f"MATRIX_STATUS {summary.get('status')}")
PY

python3 "$SCRIPT_DIR/resident_search_control.py" stop --wait=30
kill -TERM "$hook_pid" 2>/dev/null || true
wait "$hook_pid" 2>/dev/null || true
hook_pid=""
echo "HOOK STOPPED; CLOSING NMS"
close_nms
echo "NMS CLOSED"
trap - EXIT
