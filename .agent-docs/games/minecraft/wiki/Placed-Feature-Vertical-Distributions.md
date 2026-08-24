# Placed-Feature Vertical Distributions

Placed features generate candidate origins, pass them through placement modifiers, apply biome and
environment filters, and then invoke configured-feature logic. Candidate origins and final block
writes are different populations.

## Canonical bottom-to-terrain range

Vanilla 1.21.1's shared bottom-to-maximum-terrain placement range is:

```text
uniform(above_bottom(0), absolute(256))
```

The bottom follows the active dimension and the top remains literal Y 256. Taller dimensions can
therefore contain biome cells above the highest possible origin. Deeper dimensions extend the
sampling interval while retaining the same attempt count, reducing attempts per vertical block.

Changing the upper anchor to the dimension top restores reach but spreads the same count across an
even larger interval. A density-preserving extension instead retains the reference interval and adds
opportunities in extension bands. For the inclusive 321-coordinate reference interval, a full
321-level extension corresponds to one additional opportunity and a partial interval corresponds to
probability `extensionLength / 321`.

`BiomeFilter` still resolves ownership for every candidate, so candidate density is not a per-biome
quota.

## Remapping a discrete authored distribution

Treat an authored height provider as probability mass over integer Y cells, not as two endpoints to
stretch. If an authored cell has probability mass `p(y)` and maps into a live interval with width
`w(y)`, its live candidate intensity is:

```text
mapped intensity(y) = p(y) * w(y)
attempt scale = sum(mapped intensity)
mapped Y probability = mapped intensity / attempt scale
```

The attempt scale may be less than one. Unbiased stochastic rounding—`floor(scale)` plus a Bernoulli
trial for the fractional part—preserves the expected count without forcing every occurrence to
produce a candidate.

Piecewise mapping should use cell edges, preserve the authored provider shape, and resolve relative
anchors in the reference frame before mapping. Exact identity should delegate to the original
placement path so it consumes no additional random values. Candidate-density preservation does not
guarantee identical final block density: terrain hosts, caves, fluids, exposure rejection, feature
overlap, biome ownership, and later decoration remain independent authorities.

## Random-stream behavior

Minecraft decoration uses shared random streams. Additional draws on the main stream change later
decoration. A baseline draw on the original stream plus extension decisions derived from stable
inputs such as world seed, feature identity, and position leaves later main-stream draws unchanged.

When one authored attempt expands into several candidates, fanout must occur before the first
spatial sampler that needs independent values. Repeating only after X/Z sampling stacks candidates
in one column; repeating only after height sampling can duplicate an already-filtered result.

Concurrent neighboring-chunk generation can change aggregate write counts even when the placement
decision for each stable input is deterministic. Placement determinism and aggregate block totals
are therefore different properties.

## Configured-feature bounds

A configured feature can reject a valid origin through its own height check:

```java
if (pos.getY() >= 255 || !canReplace(...)) {
    continue;
}
```

An outer height provider cannot bypass this rejection. Multi-block configured features can also
write above or below their origin, so blocks beyond an origin boundary do not establish that origins
were sampled there.

## Semantic families

Fixed ranges carry different meanings across registrations:

- shared cave-decoration ranges describe candidate coverage;
- ore providers encode rarity and progression curves;
- springs, fossils, geodes, and vines can be bottom-relative, sea-level-relative, or absolute;
- carver ranges describe origin probability for shapes; and
- structures use independent start and piece-placement systems.

Two registrations with the same modifier shape are behaviorally indistinguishable at that layer,
even when their registry names imply different content categories. Registry tags can add product
policy that is not inferable from modifier shape.

## Pipeline observations

Each stage exposes a different fact:

| Observation                   | Meaning                                        |
| ----------------------------- | ---------------------------------------------- |
| Stored biome palette          | The target biome exists in generated chunks.   |
| Registered modifier list      | The feature's candidate-generation semantics.  |
| Candidate-origin range        | Positions emitted by placement modifiers.      |
| Biome-filter passes           | Origins accepted by biome ownership.           |
| Configured-feature invocation | Attempts that reached feature-specific logic.  |
| Final attributed writes       | Blocks surviving all later checks and overlap. |

Large cave surfaces can remain locally bare even at normal regional average density because random
origins miss surfaces, filters reject candidates, and successful writes cluster or overlap.
