#!/usr/bin/env bash
# games/minecraft/tooling/env.sh
# Encapsulates the environment setup for Minecraft development.

# This script is intended to be sourced by other scripts or the user.
if [[ -n "${BASH_SOURCE[0]:-}" ]]; then
	script_path="${BASH_SOURCE[0]}"
else
	script_path="$0"
fi

# tooling_dir is games/minecraft/tooling/
tooling_dir="$(cd -- "$(dirname -- "${script_path}")" && pwd)"

# 1. Java Management via .sdkmanrc (now in tooling/)
sdkmanrc_path="${tooling_dir}/.sdkmanrc"
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
		fi
	fi
fi

# 2. Shared Monorepo Caches
export SQINCHMODS_CACHE_HOME="${SQINCHMODS_CACHE_HOME:-${XDG_CACHE_HOME:-${HOME}/.cache}/squinchmods}"
export GRADLE_USER_HOME="${SQINCHMODS_CACHE_HOME}/gradle"
export npm_config_cache="${SQINCHMODS_CACHE_HOME}/npm"
export YARN_CACHE_FOLDER="${SQINCHMODS_CACHE_HOME}/yarn"
export PIP_CACHE_DIR="${SQINCHMODS_CACHE_HOME}/pip"
export UV_CACHE_DIR="${SQINCHMODS_CACHE_HOME}/uv"
