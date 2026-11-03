import { createFileRoute, notFound } from "@tanstack/react-router";

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
    <main>
      <ul>
        {game.mods.map((mod) => (
          <li key={mod.slug}>
            <a href={publicModHref(game.slug, mod.slug)}>{mod.name}</a>
          </li>
        ))}
      </ul>
    </main>
  );
}
