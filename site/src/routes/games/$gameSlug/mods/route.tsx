import { Outlet, createFileRoute } from "@tanstack/react-router";

export const Route = createFileRoute("/games/$gameSlug/mods")({
  component: Outlet,
});
