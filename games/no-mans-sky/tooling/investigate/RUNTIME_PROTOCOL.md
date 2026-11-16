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

With NMS on a loaded save:

```sh
tooling/squinch --tranche <id> nms-investigate current-world --json
```

The command retains the full runtime state and current-world response in the selected tranche. It
does not focus the game window, move the character, navigate, or alter the active search session.
Endpoint schema 1 remains compatible with `search.control/v1` only and cannot be used for native
current-world inspection.
