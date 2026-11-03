import type { GameMetadata } from "#/content/types";

export const minecraft = {
  slug: "minecraft",
  name: "Minecraft",
  hostname: "minecraft.squinchmods.com",
} as const satisfies GameMetadata;
