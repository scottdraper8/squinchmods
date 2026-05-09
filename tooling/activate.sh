#!/usr/bin/env bash

if ! (return 0 2>/dev/null); then
    echo "source tooling/activate.sh"
    exit 1
fi

if [[ -n "${BASH_SOURCE[0]:-}" ]]; then
    script_path="${BASH_SOURCE[0]}"
elif [[ -n "${ZSH_VERSION:-}" ]]; then
    script_path="${(%):-%N}"
else
    script_path="$0"
fi

repo_root="$(
    cd -- "$(dirname -- "${script_path}")/.." && pwd
)"

sdkmanrc_path="${repo_root}/.sdkmanrc"
sdkman_dir="${SDKMAN_DIR:-${HOME}/.sdkman}"

if [[ -f "${sdkmanrc_path}" ]]; then
    java_version="$(awk -F= '/^java=/{print $2}' "${sdkmanrc_path}" | tail -n 1)"

    if [[ -n "${java_version}" ]]; then
        java_home="${sdkman_dir}/candidates/java/${java_version}"

        if [[ -d "${java_home}" ]]; then
            export JAVA_HOME="${java_home}"

            case ":${PATH}:" in
                *":${JAVA_HOME}/bin:"*) ;;
                *) export PATH="${JAVA_HOME}/bin:${PATH}" ;;
            esac
        else
            echo "warning: expected JDK not found at ${java_home}" >&2
        fi
    fi
fi

cache_root="${SQINCHMODS_CACHE_HOME:-${XDG_CACHE_HOME:-${HOME}/.cache}/squinchmods}"
export SQINCHMODS_CACHE_HOME="${cache_root}"
export GRADLE_USER_HOME="${SQINCHMODS_CACHE_HOME}/gradle"
export npm_config_cache="${SQINCHMODS_CACHE_HOME}/npm"
export YARN_CACHE_FOLDER="${SQINCHMODS_CACHE_HOME}/yarn"
export PIP_CACHE_DIR="${SQINCHMODS_CACHE_HOME}/pip"
export UV_CACHE_DIR="${SQINCHMODS_CACHE_HOME}/uv"
