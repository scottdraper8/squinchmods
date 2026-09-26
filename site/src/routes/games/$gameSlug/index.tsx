import { createFileRoute, notFound } from "@tanstack/react-router";

import { SiteShell } from "#/components/layout/SiteShell";
import { findGame } from "#/content/catalog";
import { publicModHref } from "#/lib/paths";

export const Route = createFileRoute("/games/$gameSlug/")({
  component: GamePage,
});

function GamePage() {
  const { gameSlug } = Route.useParams();
  const game = findGame(gameSlug);

  if (!game) {
    throw notFound();
  }

  return (
    <SiteShell>
      <section className="page-intro">
        <p className="eyebrow">GAME</p>
        <h1>{game.name}</h1>
        <p>{game.description}</p>
      </section>

      <section className="mod-list" aria-labelledby="mods-heading">
        <h2 id="mods-heading">Mods</h2>
        {Object.values(game.mods).map((mod) => (
          <article className="mod-list-card" key={mod.slug}>
            <div>
              <p className="eyebrow">{mod.status}</p>
              <h3>{mod.name}</h3>
              <p>{mod.description}</p>
            </div>
            <a className="text-link" href={publicModHref(game.slug, mod.slug)}>
              Open wiki <span aria-hidden="true">↗</span>
            </a>
          </article>
        ))}
      </section>
    </SiteShell>
  );
}
