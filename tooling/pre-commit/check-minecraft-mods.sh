#!/usr/bin/env bash
set -euo pipefail

script_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
repo_root="$(cd -- "${script_dir}/../.." && pwd)"
minecraft_root="${repo_root}/mods/minecraft"
gradle_home_default="${TMPDIR:-/tmp}/squinchmods-gradle"

export GRADLE_USER_HOME="${GRADLE_USER_HOME:-${gradle_home_default}}"

declare -A selected_mods=()
run_all_mods=false

normalize_path() {
    local input_path="$1"

    if [[ "${input_path}" == "${repo_root}/"* ]]; then
        printf '%s\n' "${input_path#"${repo_root}"/}"
        return
    fi

    printf '%s\n' "${input_path}"
}

collect_all_mods() {
    local mod_dir

    while IFS= read -r mod_dir; do
        selected_mods["$(basename "${mod_dir}")"]=1
    done < <(find "${minecraft_root}" -mindepth 1 -maxdepth 1 -type d | sort)
}

for raw_path in "$@"; do
    path="$(normalize_path "${raw_path}")"

    case "${path}" in
        .pre-commit-config.yaml|tooling/pre-commit/check-minecraft-mods.sh|mods/minecraft/build)
            run_all_mods=true
            ;;
        mods/minecraft/*)
            relative_path="${path#mods/minecraft/}"
            mod_name="${relative_path%%/*}"
            if [[ -n "${mod_name}" && -d "${minecraft_root}/${mod_name}" ]]; then
                selected_mods["${mod_name}"]=1
            fi
            ;;
    esac
done

if [[ "$#" -eq 0 || "${run_all_mods}" == "true" ]]; then
    collect_all_mods
fi

if [[ "${#selected_mods[@]}" -eq 0 ]]; then
    echo "No Minecraft mod workspaces require validation."
    exit 0
fi

while IFS= read -r mod_name; do
    mod_dir="${minecraft_root}/${mod_name}"

    if [[ ! -x "${mod_dir}/gradlew" ]]; then
        echo "Skipping ${mod_name}: ${mod_dir}/gradlew is missing or not executable." >&2
        continue
    fi

    echo "Validating Minecraft mod '${mod_name}'"
    (
        cd "${mod_dir}"
        ./gradlew --no-daemon spotlessCheck compileJava compileTestJava
    )
done < <(printf '%s\n' "${!selected_mods[@]}" | sort)
