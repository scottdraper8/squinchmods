import { createFileRoute, notFound } from "@tanstack/react-router";

import { SiteShell } from "#/components/layout/SiteShell";
import { RedstoneBackportOverview } from "#/content/games/minecraft/mods/redstone-backport/Overview";
import { redstoneBackport } from "#/content/games/minecraft/mods/redstone-backport/mod";
import { findGame, findMod } from "#/content/catalog";

export const Route = createFileRoute("/games/$gameSlug/mods/$modSlug")({
  component: ModWikiPage,
});

function ModWikiPage() {
  const { gameSlug, modSlug } = Route.useParams();
  const game = findGame(gameSlug);
  const mod = game ? findMod(game, modSlug) : undefined;

  if (!game || !mod || mod.slug !== redstoneBackport.slug) {
    throw notFound();
  }

  return (
    <SiteShell>
      <article className="wiki-page">
        <header className="page-intro">
          <p className="eyebrow">{game.name} / MOD WIKI</p>
          <h1>{mod.name}</h1>
          <p>{mod.description}</p>
        </header>
        <RedstoneBackportOverview />
      </article>
    </SiteShell>
  );
}
