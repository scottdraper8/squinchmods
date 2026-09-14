#!/usr/bin/env bash
set -euo pipefail

readonly SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
readonly REPO_ROOT="$(cd -- "$SCRIPT_DIR/../../../.." && pwd)"
readonly STEAM_ROOT="${SQN_STEAM_ROOT:-${HOME}/.local/share/Steam}"
readonly DEFAULT_NMS_ROOT="${STEAM_ROOT}/steamapps/common/No Man's Sky"
readonly NMS_ROOT="${SQN_NMS_GAME_ROOT:-$DEFAULT_NMS_ROOT}"
readonly MODS_ROOT="$NMS_ROOT/GAMEDATA/MODS"

for command in gio python3 readlink rg; do
  if ! command -v "$command" >/dev/null; then
    echo "required command is unavailable: $command" >&2
    exit 1
  fi
done

"$SCRIPT_DIR/prepare_search_runtime.sh" "$@"

installed_adapters=()
while IFS= read -r -d '' candidate; do
  if rg --quiet --follow --glob '*.EXML' 'SE_SQN_SS_LUSH_R08' "$candidate"; then
    installed_adapters+=("$candidate")
  fi
done < <(find "$MODS_ROOT" -mindepth 1 -maxdepth 1 -type d \
  -name 'SQUINCH_INVESTIGATION_*' -print0)

if (( ${#installed_adapters[@]} == 1 )) && \
  rg --quiet --follow --glob '*.MXML' 'Launch Saved Search Probe' "${installed_adapters[0]}" && \
  rg --quiet --follow --glob '*.EXML' 'SE_SQN_SS3_P08' "${installed_adapters[0]}" && \
  rg --quiet --follow --glob '*.EXML' 'SE_SQN_SS3_FORM' "${installed_adapters[0]}" && \
  rg --quiet --follow --glob 'WIKI.EXML' \
    'TEXTURES/UI/FRONTEND/ICONS/MISSIONS/MISSION\.BLACKHOLE\.ON\.DDS' \
    "${installed_adapters[0]}" && \
  rg --quiet --follow --glob 'WIKI.EXML' \
    'TEXTURES/UI/FRONTEND/ICONS/MISSIONS/MISSION\.BLACKHOLE\.OFF\.DDS' \
    "${installed_adapters[0]}" && \
  rg --quiet --follow --glob 'WIKI.EXML' \
    'TEXTURES/UI/HUD/ICONS/WIKI/EXPLORATION4\.DDS' "${installed_adapters[0]}" && \
  rg --quiet --follow --glob 'WIKI.EXML' \
    'TEXTURES/UI/HUD/ICONS/WIKI/EXPLORATION2\.DDS' "${installed_adapters[0]}"; then
  echo "validated installed R08 Search Probes navigation adapter"
  exit 0
fi

if python3 - <<'PY'
from pathlib import Path
import sys

for comm in Path("/proc").glob("[0-9]*/comm"):
    try:
        if comm.read_text(encoding="utf-8").strip() == "NMS.exe":
            sys.exit(0)
    except (FileNotFoundError, PermissionError, ProcessLookupError):
        pass
sys.exit(1)
PY
then
  echo "NMS must be stopped before installing the navigation adapter" >&2
  exit 1
fi

probe_json="$(
  "$REPO_ROOT/tooling/squinch" nms-investigate native-search-probe \
    --game-root "$NMS_ROOT" --probe-tag R08 --guide-preset-slots 9 --json
)"
deployment_root="$(
  python3 -c 'import json,sys; print(json.load(sys.stdin)["data"]["probe"]["deployment_root"])' \
    <<< "$probe_json"
)"
stage_json="$(
  "$REPO_ROOT/tooling/squinch" nms-investigate stage \
    --game-root "$NMS_ROOT" --mod-root "$deployment_root" --apply --json
)"
echo "$stage_json"
installed_root="$(
  python3 -c 'import json,sys; print(json.load(sys.stdin)["data"]["destination"])' \
    <<< "$stage_json"
)"
installed_root="$(readlink -f -- "$installed_root")"

# A rebuilt adapter must not coexist with an older copy of this same probe. Distinct investigation
# stages may coexist, so retire only directories carrying this product's exact R08 event marker.
while IFS= read -r -d '' candidate; do
  candidate_canonical="$(readlink -f -- "$candidate")"
  if [[ "$candidate_canonical" != "$installed_root" ]] && \
    rg --quiet --follow --glob '*.EXML' 'SE_SQN_SS_LUSH_R08' "$candidate"; then
    gio trash "$candidate"
    echo "moved superseded Search Probes adapter to Trash: $candidate"
  fi
done < <(find "$MODS_ROOT" -mindepth 1 -maxdepth 1 -type d \
  -name 'SQUINCH_INVESTIGATION_*' -print0)

echo "installed R08 Search Probes navigation adapter"
