from __future__ import annotations


class InvestigationError(Exception):
    """A user-facing failure with a stable machine-readable code."""

    def __init__(self, code: str, message: str, *, details: dict | None = None):
        super().__init__(message)
        self.code = code
        self.message = message
        self.details = details or {}


class CleanupError(InvestigationError):
    def __init__(self, message: str, *, details: dict | None = None):
        super().__init__("cleanup_failed", message, details=details)
