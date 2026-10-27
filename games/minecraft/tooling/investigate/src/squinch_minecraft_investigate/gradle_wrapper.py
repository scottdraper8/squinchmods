from __future__ import annotations

from pathlib import Path
from typing import Any

from .errors import InvestigationError

GRADLE_WRAPPER_SCRIPT = Path("gradlew")
GRADLE_WRAPPER_PROPERTIES = Path("gradle/wrapper/gradle-wrapper.properties")
GRADLE_WRAPPER_JAR = Path("gradle/wrapper/gradle-wrapper.jar")


def validate_gradle_wrapper_bootstrap(
    project: Path,
    *,
    require_jar: bool = True,
    error_prefix: str = "gradle_wrapper",
) -> dict[str, Any]:
    """Validate tracked wrapper files and, optionally, the ignored bootstrap JAR."""
    project_root = project.resolve()
    script = project / GRADLE_WRAPPER_SCRIPT
    missing_code = f"{error_prefix}_bootstrap_missing"
    invalid_code = f"{error_prefix}_bootstrap_invalid"

    if (
        script.is_symlink()
        or not script.is_file()
        or not script.resolve().is_relative_to(project_root)
    ):
        raise InvestigationError(
            missing_code,
            "project/worktree is missing its regular root Gradle wrapper script; ensure the "
            f"sparse checkout includes {GRADLE_WRAPPER_SCRIPT}",
            details={
                "project": str(project),
                "missing_path": GRADLE_WRAPPER_SCRIPT.as_posix(),
            },
        )

    properties = project / GRADLE_WRAPPER_PROPERTIES
    if properties.is_symlink() or (
        properties.exists()
        and (
            not properties.is_file()
            or not properties.resolve().is_relative_to(project_root)
        )
    ):
        raise InvestigationError(
            invalid_code,
            f"Gradle wrapper properties are not a regular in-project file: {properties}",
            details={"properties_path": str(properties)},
        )

    standard_wrapper = properties.is_file()
    if not standard_wrapper:
        try:
            with script.open("rb") as script_file:
                standard_wrapper = b"gradle-wrapper.jar" in script_file.read(256 * 1024)
        except OSError as exc:
            raise InvestigationError(
                invalid_code,
                f"could not inspect Gradle wrapper script {script}: {exc}",
            ) from exc
    if standard_wrapper and not properties.is_file():
        raise InvestigationError(
            missing_code,
            "the standard Gradle wrapper script requires missing wrapper properties; ensure the "
            f"sparse checkout includes {properties}",
            details={
                "script_path": str(script),
                "properties_path": str(properties),
                "missing_path": GRADLE_WRAPPER_PROPERTIES.as_posix(),
            },
        )

    jar = project / GRADLE_WRAPPER_JAR
    if standard_wrapper and not jar.parent.resolve().is_relative_to(project_root):
        raise InvestigationError(
            invalid_code,
            f"Gradle wrapper JAR destination escapes the project/worktree: {jar}",
            details={"jar_path": str(jar)},
        )
    if standard_wrapper and (
        jar.is_symlink()
        or (
            jar.exists()
            and (not jar.is_file() or not jar.resolve().is_relative_to(project_root))
        )
    ):
        raise InvestigationError(
            invalid_code,
            f"Gradle wrapper JAR is not a regular in-project file: {jar}",
            details={"jar_path": str(jar)},
        )
    if standard_wrapper and require_jar and not jar.is_file():
        raise InvestigationError(
            missing_code,
            "the standard Gradle wrapper properties exist but the required wrapper JAR is "
            f"missing: {jar}",
            details={
                "properties_path": str(properties),
                "jar_path": str(jar),
                "missing_path": GRADLE_WRAPPER_JAR.as_posix(),
            },
        )

    return {
        "script": script,
        "properties": properties,
        "jar": jar,
        "standard_wrapper": standard_wrapper,
    }
