import { minecraft } from "./games/minecraft/game.ts";
import { redstoneBackport } from "./games/minecraft/mods/redstone-backport/mod.ts";
import type { GameWithMods } from "./types.ts";

export const games = {
  minecraft: {
    ...minecraft,
    mods: {
      [redstoneBackport.slug]: redstoneBackport,
    },
  },
} as const satisfies Record<string, GameWithMods>;

export function findGame(slug: string): GameWithMods | undefined {
  return Object.values(games).find((game) => game.slug === slug);
}

export function findGameByHostname(hostname: string): GameWithMods | undefined {
  return Object.values(games).find((game) => game.hostname === hostname);
}

export function findMod(
  game: GameWithMods,
  slug: string,
): GameWithMods["mods"][string] | undefined {
  return Object.values(game.mods).find((mod) => mod.slug === slug);
}
