<div align="center">

# Multi-Game Modding Workspace

[![Java 17 / 21](https://img.shields.io/badge/Java-17%20%2F%2021-ffb86c?logo=openjdk&logoColor=white&labelColor=6272a4)](https://dev.java/learn/)
[![Python 3.11+](https://img.shields.io/badge/Python-3.11%2B-8be9fd?logo=python&logoColor=white&labelColor=6272a4)](https://www.python.org/downloads/)
[![Rust 1.98.1](https://img.shields.io/badge/Rust-1.98.1-ff5555?logo=rust&logoColor=white&labelColor=6272a4)](https://www.rust-lang.org/)

---

Development workspace for all of squinchmods, where each mod lives as its own git submodule. This
repo centralizes all orchestration, reference material, and QA tooling so submodules stay clean and
lean.

By adhering to this paradigm, all mods ship as lightweight as possible and development is
streamlined with reusable tooling.

---

</div>

## Mods as Submodules

Each mod is a separate git repository, added as a submodule under `games/<game>/mods/<mod>/`.

```text
games/
├── minecraft/
│   └── mods/
│       ├── FreeTerraForged/   — Customizable overworld terrain generation for Minecraft
│       └── redstone-backport/ — Backports redstone additions to older Minecraft versions
└── no-mans-sky/
    └── mods/
        └── search-probes/     — Customizable massive-scale searches for No Man's Sky systems and planets
```

## Agents

**If you're an agent working in this repo, look in `.agent-docs/` first** for structural and
implementation detail beyond what this README covers, starting with `.agent-docs/README.md`.
Additionally, be sure to strictly adhere to `AGENTS.md`.
