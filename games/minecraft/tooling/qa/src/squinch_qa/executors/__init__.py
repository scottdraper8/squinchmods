from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from squinch_qa.executors.base import Executor

_REGISTRY: dict[str, type[Executor]] = {}


def register(test_id: str, cls: type[Executor]) -> None:
    _REGISTRY[test_id] = cls


def get_executor(test_id: str) -> type[Executor]:
    if test_id not in _REGISTRY:
        raise NotImplementedError(
            f"No executor registered for test '{test_id}'; "
            "register an executor before adding the test to a runnable profile"
        )
    return _REGISTRY[test_id]


def _register_defaults() -> None:
    from squinch_qa.executors.build import BuildExecutor
    from squinch_qa.executors.command_script import CommandScriptExecutor
    from squinch_qa.executors.server_smoke import ServerSmokeExecutor
    from squinch_qa.executors.pregen import PregenExecutor

    register("build", BuildExecutor)
    register("tick-freeze", CommandScriptExecutor)
    register("crafter-basic", CommandScriptExecutor)
    register("server-smoke", ServerSmokeExecutor)
    register("pregen", PregenExecutor)


_register_defaults()
