import { createFileRoute, notFound } from "@tanstack/react-router";

import { findGame, findMod } from "#/content/catalog";
import { assetWiki } from "#/content/games/no-mans-sky/mods/asset-wiki/mod";
import { AssetWikiPage, type DatasetName } from "#/content/games/no-mans-sky/mods/asset-wiki/Page";

export const Route = createFileRoute("/games/$gameSlug/mods/$modSlug_/$section")({
  component: ModWikiSectionPage,
});

function ModWikiSectionPage() {
  const { gameSlug, modSlug, section } = Route.useParams();
  const game = findGame(gameSlug);
  const mod = game ? findMod(game, modSlug) : undefined;

  const dataset = assetWiki.pages.find((page) => page === section);
  if (!game || !mod || mod.slug !== assetWiki.slug || !dataset) {
    throw notFound();
  }

  return <AssetWikiPage key={dataset} dataset={dataset as DatasetName} />;
}
