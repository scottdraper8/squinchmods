<div align="center">

# Multi-Game Modding Workspace

[![Java 17 / 21](https://img.shields.io/badge/Java-17%20%2F%2021-ffb86c?logo=openjdk&logoColor=white&labelColor=6272a4)](https://dev.java/learn/)
[![Python 3.11+](https://img.shields.io/badge/Python-3.11%2B-8be9fd?logo=python&logoColor=white&labelColor=6272a4)](https://www.python.org/downloads/)
[![Rust 1.98.1](https://img.shields.io/badge/Rust-1.98.1-ff5555?logo=rust&logoColor=white&labelColor=6272a4)](https://www.rust-lang.org/)

---

Development workspace for Minecraft and No Man's Sky mods. Each maintained mod lives in a Git
submodule under `games/<game>/mods/`, alongside game-specific tools and technical references.

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
