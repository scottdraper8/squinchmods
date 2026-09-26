import type { GameMetadata } from "#/content/types";

export const minecraft = {
  slug: "minecraft",
  name: "Minecraft",
  hostname: "minecraft.squinchmods.com",
  description: "Mods and projects for Minecraft Java Edition.",
} as const satisfies GameMetadata;
