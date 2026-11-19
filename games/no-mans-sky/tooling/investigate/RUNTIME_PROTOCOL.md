# NMS runtime protocol client

The investigation package owns the operator-facing client for capabilities provided by a running NMS
mod. `runtime_protocol.py` validates endpoint freshness and instance identity, negotiates an
explicit capability, writes a bounded session-local request, and waits for the matching command and
published state. Unknown endpoint schemas and protocol versions fail closed.

Search Probes currently provides protocol `search-probes.agent-control` version 1 through endpoint
schema 2:

- `search.control/v1` starts, configures, cancels, and reports a search.
- `nms.current-world/v1` classifies the loaded system and planet against current search criteria.

The current-world response acquires every field needed by the active criteria plus core visual
context such as the world colour filter. It includes every acquired native field with its numeric
value and labels, known flags and resources, the exact criteria and compiled predicates, individual
predicate verdicts, section verdicts with their `all`/`any` mode, and system, planet, and combined
target verdicts. Missing facts remain absent or `unknown`; the parent client does not invent a
classification from screenshots, save data, or stale search results.

Colour labels are derived classifications, not native NMS colour enums. Each published observation
identifies whether it came from a generated reference appearance, grass material appearance, or
flora model appearance. Generated observations retain their source scene-linear RGB, the game's
canonical tone-mapped sRGB, and the native components used to construct compound references.

The searchable daytime-sky value is a reproducible clear-day upper-sky reference: the midpoint of
the atmosphere shader's per-channel upper-to-main sky gradient, oriented away from the solar and
horizon blends, then passed through the game's canonical tone mapping. The response includes the
exact gradient progress and native gradient-speed vector used by that model. It also retains the
main, upper, solar, and sun colour components from the same generated record because one reference
sample does not describe the whole rendered dome. The world colour filter remains a separate native
criterion: applying its isolated LUT directly to an atmosphere anchor is invalid because the game
performs view-dependent scattering before runtime LUT blending. Flora may finish early once an
allowed colour is proven; in that case the response publishes the colours actually observed, every
colour category already evaluated, and `complete: false` instead of discarding the partial evidence.

With NMS on a loaded save:

```sh
tooling/squinch --tranche <id> nms-investigate current-world --json
```

The command retains the full runtime state and current-world response in the selected tranche. It
does not focus the game window, move the character, navigate, or alter the active search session.
