# Redstone Backport engineering references

- [Active implementation contract](implementation-contract.md): approved standalone all-in-one
  direction, actual minimum baseline, source/ownership boundaries, and release acceptance gates.
- [Source, asset, and distribution boundaries](asset-provenance.md): existing project licensing,
  independent implementation, official local resource acquisition, and third-party limits.
- [Scope, implementation audit, and existing backports](refs/scope-and-existing-backports.md):
  initial implementation discrepancies, competing source trees, and earlier scope analysis. Its
  narrow-companion recommendation was not approved and is superseded by the active contract.
- [Vanilla redstone update inventory](refs/vanilla-redstone-update-inventory.md): stable changes,
  redstone-adjacent mechanics, and the separate snapshot watchlist.

Development is active in the `redstone-backport-release` tranche. Its task-local research,
orchestration, worktrees, build state, and runtime results are temporary inputs/outputs, not a
persistent investigation archive. Shared vanilla and third-party source caches remain separate.

The research references are evidence inputs, not release qualification. Runtime parity and companion
compatibility remain unqualified until the active contract's gates pass. Read the Minecraft
investigation guide before implementation or runtime work; the focused references link to active
task evidence, which must be promoted into maintained tests or removed at completion.
