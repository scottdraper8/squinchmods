# Development Roadmap

## psiber

### Correctional / Compatibility Releases

> Addressing significant stability and third party mod compatibility concerns (ongoing)

### Standalone Lakes

> Reimplement standalone lakes. Treat as river variant that dont generate river sections between
> their isolated pools. (conceptual stage)

### Fix River Banding

> When rivers change vertical height they generate uniform banding and step distances which is
> unnatural. The bands spread onto the surrounding valley floors due to the height uplift
> implementation. We can fix this. (local branch has microterraces implemented, working on valley

<!-- markdownlint-disable MD013 MD027 -->

> floor model update)
> <img alt="Example of river banding" src="https://github.com/user-attachments/assets/b647cedb-0cfc-4244-be0f-d26ca9377833" />

<!-- markdownlint-enable MD013 MD027 -->

### Update SnowDecorator

> Got sent some code that reportedly makes mountain snow look better. Review and productionize if
> reasonable (needs review / productionizing)

### Volcano Pipes

> FreeTerraForged already generates volcano pipes, though rarely. Make them a usable source of lava
> and integrate cleanly to surrounding landscape in a cool way. (early draft pull request)

### Wiki Documentation & Settings Audit

> Actually document all the settings so you can just point people at supporting documentation which
> will be important if bulk popularity (Started at the
> [World Generation Settings screen guide](world-generation-settings))

### Settings Migration

> Migrating to align settings with 0.0.7 codebase for interoperability and easier settings addition
> for developers (proven, at implementation stage)

### ErodeFeature -> ErodeSurfaceDecorator

> Migrate Erode feature from a feature to a surface decorator so its more correctly earlier in the
> worldgen pipeline and has to cleanup fewer artifacts like grass block removal. (conceptual stage)

---

### squinch

#### Worldgen Compatibility Runtime

> Refactor all compatibility code in FTF and consolidate in one layer. Increase not only general
> compatibility but maintenance as well. Should resolve biome blending issues as a side-effect.
> ([WIP PR](https://github.com/ETcodehome/FreeTerraForged/pull/206))

#### Biome Seed Offset Config

> Following the completion of the Worldgen Compatibility Runtime, add a preset option to offset
> biomes from the seed. Feature request filed on issue
> [#169](https://github.com/ETcodehome/FreeTerraForged/issues/169)

---

### broke && skel

#### Preset Updates / Standardisation

> Generating a more complete set of valid and sensible presets for incorporation (wip)

#### Promotional Materials

> Preparation of video materials showing the capabilities of the mod in the best light for
> promotional purposes (actively progressing)
