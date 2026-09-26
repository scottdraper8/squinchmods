<div align="center">

# Multi-Game Modding Workspace

[![Java 17 / 21](https://img.shields.io/badge/Java-17%20%2F%2021-ffb86c?logo=openjdk&logoColor=white&labelColor=6272a4)](https://dev.java/learn/)
[![Python 3.11+](https://img.shields.io/badge/Python-3.11%2B-8be9fd?logo=python&logoColor=white&labelColor=6272a4)](https://www.python.org/downloads/)
[![Rust 1.98.1](https://img.shields.io/badge/Rust-1.98.1-ff5555?logo=rust&logoColor=white&labelColor=6272a4)](https://www.rust-lang.org/)

---

Development workspace for all of squinchmods, where each mod lives as its own git submodule. This
repo centralizes all orchestration, reference material, and QA tooling so individual mods stay clean
and lean.

Also contains the code for [squinchmods.com](https://squinchmods.com), which houses each mod's wiki.

---

</div>

## Mods

<table>
  <thead>
    <tr>
      <th align="center">Game</th>
      <th align="center">Mod Name</th>
      <th align="center">Mod Description</th>
      <th align="center">Downloads</th>
      <th align="center">GitHub</th>
    </tr>
  </thead>
  <tbody>
    <!-- markdownlint-disable MD013 -->
    <tr>
      <td rowspan="2" align="center"><img src="assets/minecraft-logo.png" alt="Minecraft Java Edition logo" width="120"></td>
      <td>FreeTerraForged</td>
      <td>Customizable overworld terrain generation for Minecraft.</td>
      <td>
        <a href="https://modrinth.com/mod/freeterraforged" aria-label="Download FreeTerraForged from Modrinth"><img alt="Modrinth downloads" src="https://img.shields.io/modrinth/dt/freeterraforged?logo=modrinth&amp;logoColor=white&amp;label=Modrinth&amp;color=50fa7b&amp;labelColor=6272a4"></a><br>
        <a href="https://www.curseforge.com/minecraft/mc-mods/freeterraforged" aria-label="Download FreeTerraForged from CurseForge"><img alt="CurseForge downloads" src="https://img.shields.io/curseforge/dt/1576275?logo=curseforge&amp;logoColor=white&amp;label=CurseForge&amp;color=ffb86c&amp;labelColor=6272a4"></a>
      </td>
      <td><a href="https://github.com/scottdraper8/FreeTerraForged">Visit <img src="assets/external-link.svg" alt="" width="14" height="14"></a></td>
    </tr>
    <tr>
      <td>Redstone Backport</td>
      <td>Backports redstone additions from later Minecraft versions to older versions.</td>
      <td></td>
      <td><a href="https://github.com/scottdraper8/redstone-backport">Visit <img src="assets/external-link.svg" alt="" width="14" height="14"></a></td>
    </tr>
    <tr>
      <td align="center"><img src="assets/no-mans-sky-logo.png" alt="No Man's Sky logo" width="120"></td>
      <td>Search Probes</td>
      <td>Searches No Man's Sky systems and planets by their generated properties.</td>
      <td></td>
      <td><a href="https://github.com/scottdraper8/search-probes">Visit <img src="assets/external-link.svg" alt="" width="14" height="14"></a></td>
    </tr>
    <!-- markdownlint-enable MD013 -->
  </tbody>
</table>

## Agents

**If you're an agent working in this repo, look in `.agent-docs/` first** for structural and
implementation detail beyond what this README covers, starting with `.agent-docs/README.md`.
Additionally, be sure to strictly adhere to `AGENTS.md`.
