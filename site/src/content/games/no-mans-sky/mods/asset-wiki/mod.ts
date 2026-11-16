import type { ModMetadata } from "#/content/types";

export const assetWiki = {
  slug: "asset-wiki",
  name: "Asset Wiki",
  pages: ["items", "icons", "colour-filters"],
} as const satisfies ModMetadata;
