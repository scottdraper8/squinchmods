<div align="center">

# Multi-Game Modding Workspace

[![Python 3.11+](https://img.shields.io/badge/Python-3.11+-bd93f9?logo=python&logoColor=white&labelColor=6272a4)](https://www.python.org/downloads/)
[![pre-commit](https://img.shields.io/badge/pre--commit-4.6-50fa7b?logo=pre-commit&logoColor=282a36&labelColor=6272a4)](https://github.com/pre-commit/pre-commit)
[![SDKMAN!](<https://img.shields.io/badge/SDKMAN!-Java_21_(Temurin)-ffb86c?labelColor=6272a4>)](https://sdkman.io/)

---

Workspace for all of squinchmods' game mod where each mod lives as its own git submodule. This repo
centralizes all orchestration, reference material, and QA tooling so submodules stay clean.

---

</div>

## Mods as Submodules

Each mod is a separate git repository, added as a submodule under `games/<game>/mods/<mod>/`. Some
mods are forks intended for upstream contribution and are kept clean of anything
squinchmods-specific.

## `.agent-docs/`

Planning notes, architecture references, and per-mod investigation docs live here, not scattered
across mod submodules.

**If you're an agent working in this repo, look there first** for structural and implementation
detail beyond what this README covers, starting with `.agent-docs/README.md`.
