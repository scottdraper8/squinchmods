import { createFileRoute } from "@tanstack/react-router";

import { games } from "#/content/catalog";
import { publicGameHref } from "#/lib/paths";

export const Route = createFileRoute("/games/")({
  component: GamesIndexPage,
});

function GamesIndexPage() {
  return (
    <main>
      <ul>
        {Object.values(games).map((game) => (
          <li key={game.slug}>
            <a href={publicGameHref(game.hostname, game.slug)}>{game.name}</a>
          </li>
        ))}
      </ul>
    </main>
  );
}
