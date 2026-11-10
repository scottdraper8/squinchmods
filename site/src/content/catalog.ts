import { minecraft } from "./games/minecraft/game.ts";
import { redstoneBackport } from "./games/minecraft/mods/redstone-backport/mod.ts";
import { noMansSky } from "./games/no-mans-sky/game.ts";
import { assetWiki } from "./games/no-mans-sky/mods/asset-wiki/mod.ts";
import { generousGiver } from "./games/no-mans-sky/mods/generous-giver/mod.ts";
import { searchProbes } from "./games/no-mans-sky/mods/search-probes/mod.ts";
import type { GameWithMods } from "./types.ts";

export const games = {
  minecraft: {
    ...minecraft,
    mods: [redstoneBackport],
  },
  noMansSky: {
    ...noMansSky,
    mods: [assetWiki, generousGiver, searchProbes],
  },
} as const satisfies Record<string, GameWithMods>;

export function findGame(slug: string): GameWithMods | undefined {
  return Object.values(games).find((game) => game.slug === slug);
}

export function findGameByHostname(hostname: string): GameWithMods | undefined {
  return Object.values(games).find((game) => game.hostname === hostname);
}

export function findMod(game: GameWithMods, slug: string) {
  return game.mods.find((mod) => mod.slug === slug);
}
