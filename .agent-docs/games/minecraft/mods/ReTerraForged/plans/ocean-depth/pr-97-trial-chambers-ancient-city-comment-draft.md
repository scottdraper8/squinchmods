<!-- markdownlint-disable MD041 MD028 MD045 MD013 -->
<!-- Working draft of a GitHub PR comment. Deliberately mirrors GitHub's raw comment markdown
     (multi-paragraph blockquotes, unlabeled inline images, long prose lines) instead of this
     repo's internal doc style, since it's meant to be copy-pasted as-is. -->

## RE: Trial Chambers - Resolved by [69d2f5b](https://github.com/ETcodehome/ReTerraForged/pull/97/commits/69d2f5b3b710c1349b690eb66968d2fa422f88ba)

> spawn as large floating blobs because they don't expect oceans deeper than y0. not sure if this is
> a problem worth addressing. doesn't look great, but Im not sure it's worth special handling and
> may possible predate this PR but just not be as visible during regular generation

> [!IMPORTANT] This is a pre-existing vanilla limitation exposed by RTF allowing for configurable
> world depth, not something new introduced by this PR. Trial Chambers (and Ancient Cities turns
> out) pick their spawn height from a fixed `y` range.

> [!WARNING] This is a bugfix addressing vanilla MC limitations, so it's unconditionally active. Not
> gated behind a config flag.

---

### Cause

Ancient City and Trial Chambers both use the same vanilla structure type under the hood. When
Minecraft decides to generate one, it picks a starting `y` using `start_height` with no check
against the real terrain.

For Ancient City that's explicitly `y = -27`. For Trial Chambers it's a random pick between
`y = -40` and `y = -20`. Both assume that range is always safely underground (because it is safe in
vanilla). But the assumption is wrong for RTF because `oceanDepth`/`worldDepth` are configurable.
The fixed range can cause the structure to generate too high (like floating in an ocean) or too low
(like below the bedrock, in which case the structure just skips and can never be placed).

### Subsequent Investigation

Since Ocean Monuments was similar (but not the same exact bug), I checked every other overworld
structure vanilla has to see if any of them shared it. Fortunately, it turns out almost everything
else already is dynamic. Ancient City and Trial Chambers were the only two that never check
anything.

<details><summary><strong>Structure placement details, if you're interested</strong></summary>

| Structure                                                      | Reacts to real terrain?              |
| -------------------------------------------------------------- | ------------------------------------ |
| Ancient City                                                   | No, fixed in this PR                 |
| Bastion Remnant                                                | No, but Nether. Irrelevant           |
| Trial Chambers                                                 | No, fixed in this PR                 |
| Ocean Monument                                                 | No, fixed in this PR                 |
| Mineshaft, Stronghold                                          | Yes, snaps to real sea level/terrain |
| Buried Treasure, Ocean Ruins, Shipwrecks                       | Yes, resamples real terrain          |
| Desert Pyramid, Igloo, Jungle Temple, Ruined Portal, Swamp Hut | Yes, resamples real terrain          |
| Pillager Outpost, Trail Ruins, Villages                        | Yes, self corrects up front          |
| Woodland Mansion                                               | Yes, scans real terrain, fills gaps  |

</details>
<br>

I also tested both ends of the depth spectrum ("shallow" and deep world depths) instead of just the
deep ocean case that got reported.

- In a very deep ocean, the fixed placement misses the real floor by hundreds of blocks and the
  structure floats.
- In a very shallow world, that same fixed range can sit entirely below the world's actual bottom,
  so there's nowhere valid for for the structure to be placed and it just gets skipped.

That ruled out just pushing structures down until they hit ground. What needed to happen was:

- Push down wherever the real terrain sits lower than expected
- Pull up into whatever space actually exists when the world is too shallow

### Solution

I added one mixin, `MixinJigsawStructure`, that reimplements the placement logic for just these two
structures. It uses vanilla's (poorly named)`OCEAN_FLOOR_WG` heightmap, which basically just means
"first solid, non liquid block". It works the same for dry land and actual ocean floors.

Fix is robust enough to work (and proven to work) with mods/datapacks that affect vanilla structure
generation, like [Luki's Ancient Cities](https://modrinth.com/datapack/lukis-ancient-cities) and
[Luki's Crazy Chambers](https://modrinth.com/datapack/lukis-crazy-chambers).

<table align="center" width="100%">
  <tbody>
    <tr>
      <td align="center" width="33%">
        <kbd><img src="PASTE_SCREENSHOT_URL_HERE" width="100%"></kbd>
      </td>
      <td align="center" width="33%">
        <kbd><img src="PASTE_SCREENSHOT_URL_HERE" width="100%"></kbd>
      </td>
      <td align="center" width="33%">
        <kbd><img src="PASTE_SCREENSHOT_URL_HERE" width="100%"></kbd>
      </td>
    </tr>
    <tr valign="top">
      <td width="33%">Trial Chambers floating in open ocean before the fix (<code>oceanDepth=677</code>, <code>worldDepth=624</code>)</td>
      <td width="33%">Same location and settings after the fix, properly buried under the real ocean floor</td>
      <td width="33%">Trial Chambers generating correctly in a very shallow world (<code>worldDepth=16</code>)</td>
    </tr>
  </tbody>
</table>

Ancient City's currently can't "float" like trial chambers, nor can they even protrude into the
ocean. 2 things prevent that:

1. Ancient Cities must be placed in the Deep Dark
1. Biome temperature banding issues actually prevent the Deep Dark from generating close enough to
   ocean floors for the cities to protrude through.

So this table is just showing the fix working correctly across settings:

<table align="center" width="100%">
  <tbody>
    <tr>
      <td align="center" width="50%">
        <kbd><img src="PASTE_SCREENSHOT_URL_HERE" width="100%"></kbd>
      </td>
      <td align="center" width="50%">
        <kbd><img src="PASTE_SCREENSHOT_URL_HERE" width="100%"></kbd>
      </td>
    </tr>
    <tr valign="top">
      <td width="50%">Ancient City properly buried after the fix, relocated from its blind spawn height down into real <code>deep_dark</code> terrain (<code>oceanDepth=677</code>, <code>worldDepth=624</code>)</td>
      <td width="50%">Ancient City generating correctly in a very shallow world (<code>worldDepth=16</code>)</td>
    </tr>
  </tbody>
</table>

<details>
<summary><strong>More details on the solution, if you're interested</strong></summary>
<br>

Trial Chambers are built from 100+ small rooms and tunnels placed one at a time out from a single
anchor point, sprawling out somewhat randomly each time it generates. Because of that, there's no
reliable way to know ahead of time how much room a specific instance actually needs, so rather than
guessing, the fix waits until the whole structure has actually built for real, then checks whether
what got placed actually fits where it landed. That holds up no matter how big or oddly shaped a
real instance turns out to be, since it's checking the real result instead of a fixed assumption
about it.

Ancient Cities are a lot simpler. It's basically the same size and shape every time, always
extending exactly 37 blocks straight down from its anchor, so its outcome is much easier to predict
once that anchor lands somewhere safe.

Both structures pick that first anchor point through the exact same vanilla mechanism though
(`JigsawStructure`), since all it has to do is correct that one shared starting point. Here's the
process that runs every time the game tries to place one of these two structures:

- **Step 1, get vanilla's blind guess:** The game picks a `y` using its normal fixed rule.
- **Step 2, sample the real terrain in both directions:** Both structures can sprawl out from their
  anchor by up to 116 blocks in any direction (`max_distance_from_center`), so a 7x7 grid of points
  gets sampled across that whole radius. That same pass tracks the deepest solid floor found
  anywhere in the grid (the "worst floor") and the shallowest solid surface found anywhere (the
  "best surface").
- **Step 3, figure out where's actually "safe":** Using the worst floor, work out a push down target
  the same way vanilla effectively would, land 10 blocks below it as a buffer. Check whether that
  target actually fits somewhere between the world's real bottom and the best surface point. If it
  fits, keep it (this reproduces normal generation when nothing needs correcting). If it doesn't fit
  but there's still a safe range somewhere in this column, retarget to the middle of that range,
  giving the structure room in both directions instead of only ever pushing it deeper. If there's no
  safe range at all, stop here and skip. No point building something that's guaranteed broken.
- **Step 4, cheap biome check.** Some biomes aren't valid for these structures (`deep_dark` excludes
  Trial Chambers, for example). Check the biome at the chosen Y and bail early if it's not allowed,
  before paying for the expensive step below.
- **Step 5, actually build it, for real.** Instead of guessing whether the structure will fit,
  Minecraft's own dungeon generation actually assembles it: real rooms, real connectors, anchored at
  the chosen Y. This is genuine generation, not a preview.
- **Step 6, measure what actually got built.** Ask the real structure for its exact bounding box,
  the smallest box that contains every room that got placed.
- **Step 7, resample the ground directly above it.** The surface point from step 2 was sampled
  across a wide area before anything existed, so it can end up describing a hill nowhere near where
  the structure actually ended up sprawling. Now that the real footprint is known, sample again,
  this time only across the real structure's own footprint, and take the lowest point found there.
- **Step 8, final check, both directions.** Reject if the real bottom sits suspiciously close to the
  world's actual floor (it got clipped), or if the real top sits suspiciously close to the freshly
  resampled surface point (it's probably poking out). Otherwise, keep it.

I tested this on a very deep ocean preset, a vanilla depth preset, and a very shallow world.

</details>
