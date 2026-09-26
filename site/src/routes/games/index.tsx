import { createFileRoute } from "@tanstack/react-router";

import { SiteShell } from "#/components/layout/SiteShell";

export const Route = createFileRoute("/games/")({
  component: GamesIndexPage,
});

function GamesIndexPage() {
  return (
    <SiteShell>
      <section className="page-intro">
        <p className="eyebrow">GAME LIBRARY</p>
        <h1>Games</h1>
        <p>Explore mods and projects by game.</p>
      </section>
    </SiteShell>
  );
}
