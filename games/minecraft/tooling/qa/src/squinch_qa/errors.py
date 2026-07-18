from __future__ import annotations


class SquinchQAError(Exception):
    """Base class for all squinch-qa errors."""


class ConfigError(SquinchQAError):
    """Config file is missing, malformed, or schema-invalid."""


class PlanError(SquinchQAError):
    """Planning failed (logic error after config loaded successfully)."""


class MatrixLimitExceeded(SquinchQAError):
    """Planned job count exceeds the profile's max_jobs cap."""

    def __init__(self, count: int, cap: int) -> None:
        self.count = count
        self.cap = cap
        super().__init__(
            f"planned {count} jobs but profile cap is {cap}; "
            "reduce --target scope or raise max_jobs in the profile"
        )


class UnknownProfile(SquinchQAError):
    """Named profile not found in parent or mod config."""


class UnknownTarget(SquinchQAError):
    """Named target not found in mod config."""


class UnknownMod(SquinchQAError):
    """Mod slug not found under .squinch/games/minecraft/mods/."""


class ValidationError(SquinchQAError):
    """A completed run failed promotion validation (bad/missing manifest, hash mismatch, path traversal)."""

    def __init__(self, reason: str, message: str) -> None:
        self.reason = reason
        super().__init__(message)


class ReplaceError(SquinchQAError):
    """The atomic replace pipeline itself failed (cross-device root, filesystem error)."""

    def __init__(self, reason: str, message: str) -> None:
        self.reason = reason
        super().__init__(message)


class SummaryError(SquinchQAError):
    """A run's manifest/result files are missing or malformed; cannot render a summary."""
