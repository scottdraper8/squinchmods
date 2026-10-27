# Minecraft Agentic Development Guide

Use `tooling/squinch --tranche <id> mc-investigate` for managed Minecraft server and client checks.
The [tool reference](../../../games/minecraft/tooling/investigate/README.md) documents current
commands and result formats. Mod-specific contracts live under
`.agent-docs/games/minecraft/mods/<mod>/`.

## Investigation inputs and outputs

Create and select a repository scratch tranche before running Minecraft tools. Store scenario TOMLs,
benchmark matrices, presets, probe packs, datapacks, and other task inputs below that tranche's
workspace. The runner rejects these inputs from source or another tranche.

Start from a specific behavior and the exact project worktree that will be checked. Supply the
loader and any task-local inputs explicitly. `--project` names the target worktree; it is not
resolved from a mod name.

FTF preset input is a complete preset supplied for the active task. The exporter output is a
generated datapack. Keep those terms distinct. Scenario TOMLs and probe packs are also task-local
inputs: do not maintain FTF catalogs or retain one-off inputs after the active work is complete.

Generated runs, worlds, logs, screenshots, measurements, Gradle build state, and manifests live in
the selected tranche workspace. Clean the tranche when the feature or fix is done. Put long-lived
behavior in CI/CD tests.

## Result authority

Match each claim to the strongest result that supports it:

1. Source inspection and static checks establish code behavior without running Minecraft.
2. FTF `cell-scan` preview is a prediction.
3. `cell-scan --mode tile` checks FTF's horizontal tile model, not final blocks.
4. A live generation probe observes an in-progress phase.
5. A finished-chunk probe observes generated world state after chunk promotion.
6. Client visual review supports player-facing claims.

A result from one stage does not establish a later stage. Use the authority reported by the tool and
avoid keeping raw outputs after the active task is complete.

## Managed sessions

Use `start` for an interactive managed server, `run` for a bounded command sequence, and `command`
for commands sent to a tracked session. Use `scenario FILE` only with a task-local scenario when the
active check needs ordered steps or assertions. Use `client` for isolated client checks. The command
help and tool reference list available options.

The runner owns process startup, readiness checks, target configuration staging, and teardown. Pass
the exact project path, loader, and runtime inputs required by the check. Prefer the managed
commands over launching an untracked Gradle or Minecraft process.

## Probes and generated datapacks

Use built-in probes where they answer the question. For behavior that needs custom instrumentation,
create a task-specific probe pack from the
[probe-pack template](../../../games/minecraft/tooling/investigate/probe-pack-template/README.md)
and remove it after the work is complete. Do not keep reusable FTF probe packs or scenario recipes
in the repository.

Use `preset-export` when the active check needs FTF's real exporter. It accepts a task-local preset
input and produces a generated datapack in run state. Exported datapacks are outputs; they are not
preset catalogs.

## Source and test work

Use the repository's Minecraft and mod guides for current contracts. Put repeatable, long-lived
behavior in CI/CD tests. Keep temporary investigation inputs and raw run outputs out of plans,
references, and routine documentation.

For vanilla or third-party source review, use `tooling/squinch mc-source` or
`tooling/squinch third-party minecraft source`; treat local checkouts as disposable source material.
