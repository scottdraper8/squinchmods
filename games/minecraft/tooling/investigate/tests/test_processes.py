from __future__ import annotations

import signal
import subprocess

import pytest

from squinch_minecraft_investigate import processes
from squinch_minecraft_investigate.errors import InvestigationError


def test_signal_service_accepts_naturally_removed_transient_unit(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        processes,
        "_systemctl",
        lambda *_args, **_kwargs: subprocess.CompletedProcess(
            [], 1, "", "Failed to kill unit: Unit squinch-mc-run.service not loaded."
        ),
    )

    processes.signal_service({"unit": "squinch-mc-run.service"}, signal.SIGTERM)


def test_signal_service_preserves_real_systemd_failures(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        processes,
        "_systemctl",
        lambda *_args, **_kwargs: subprocess.CompletedProcess([], 1, "", "Access denied"),
    )

    with pytest.raises(InvestigationError, match="Access denied"):
        processes.signal_service({"unit": "squinch-mc-run.service"}, signal.SIGTERM)
