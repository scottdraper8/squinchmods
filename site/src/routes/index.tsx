import { createFileRoute } from "@tanstack/react-router";

import { SiteShell } from "#/components/layout/SiteShell";
import { games } from "#/content/catalog";
import { publicGameHref } from "#/lib/paths";

export const Route = createFileRoute("/")({
  component: HomePage,
});

function HomePage() {
  const game = games.minecraft;
  const mod = game.mods["redstone-backport"];

  return (
    <SiteShell>
      <section className="hero-panel">
        <p className="eyebrow">MODS, WORLDS, AND HOW THEY WORK</p>
        <h1>
          Small worlds.
          <br />
          Big ideas.
        </h1>
        <p className="hero-copy">A home for the Minecraft mods and experiments I build.</p>
        <a className="text-link" href={publicGameHref(game.hostname, game.slug)}>
          Explore {game.name} <span aria-hidden="true">↗</span>
        </a>
      </section>

      <section className="landing-card" aria-labelledby="featured-mod-title">
        <div>
          <p className="eyebrow">FEATURED MOD</p>
          <h2 id="featured-mod-title">{mod.name}</h2>
          <p>{mod.description}</p>
        </div>
        <span className="version-badge">Minecraft {mod.minecraftVersion}</span>
      </section>
    </SiteShell>
  );
}
