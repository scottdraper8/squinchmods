import type { ModMetadata } from "#/content/types";

export const redstoneBackport = {
  slug: "redstone-backport",
  name: "Redstone Backport",
  minecraftVersion: "1.20.1",
  status: "Alpha",
  loaders: ["Fabric", "Quilt", "Forge"],
  description:
    "Brings selected redstone features from later Minecraft releases to Minecraft Java 1.20.1.",
  features: [
    {
      title: "/tick command",
      detail: "Freeze, step, sprint, and control the server tick rate.",
      sourceVersion: "1.20.3",
    },
    {
      title: "Crafter",
      detail:
        "Automate crafting with redstone pulses, disabled slots, and hopper or dropper input.",
      sourceVersion: "1.21",
    },
    {
      title: "Witch redstone drops",
      detail: "Witches drop 4–8 redstone dust, with Looting affecting the amount.",
      sourceVersion: "1.21",
    },
  ],
  license: "CC BY-NC-ND 4.0",
  repository: "https://github.com/scottdraper8/squinchmods",
} as const satisfies ModMetadata;
