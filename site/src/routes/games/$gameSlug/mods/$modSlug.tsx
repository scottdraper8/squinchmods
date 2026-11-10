import { createFileRoute, notFound } from "@tanstack/react-router";

import { findGame, findMod } from "#/content/catalog";
import { redstoneBackport } from "#/content/games/minecraft/mods/redstone-backport/mod";
import { RedstoneBackportPage } from "#/content/games/minecraft/mods/redstone-backport/Page";
import { assetWiki } from "#/content/games/no-mans-sky/mods/asset-wiki/mod";
import { AssetWikiPage } from "#/content/games/no-mans-sky/mods/asset-wiki/Page";
import { generousGiver } from "#/content/games/no-mans-sky/mods/generous-giver/mod";
import { GenerousGiverPage } from "#/content/games/no-mans-sky/mods/generous-giver/Page";
import { searchProbes } from "#/content/games/no-mans-sky/mods/search-probes/mod";
import { SearchProbesPage } from "#/content/games/no-mans-sky/mods/search-probes/Page";

export const Route = createFileRoute("/games/$gameSlug/mods/$modSlug")({
  component: ModWikiPage,
});

function ModWikiPage() {
  const { gameSlug, modSlug } = Route.useParams();
  const game = findGame(gameSlug);
  const mod = game ? findMod(game, modSlug) : undefined;

  if (!game || !mod) {
    throw notFound();
  }

  if (mod.slug === redstoneBackport.slug) {
    return <RedstoneBackportPage />;
  }

  if (mod.slug === assetWiki.slug) {
    return <AssetWikiPage />;
  }

  if (mod.slug === searchProbes.slug) {
    return <SearchProbesPage />;
  }

  if (mod.slug === generousGiver.slug) {
    return <GenerousGiverPage />;
  }

  throw notFound();
}
