import { createFileRoute, Outlet } from "@tanstack/react-router";

export const Route = createFileRoute("/games/$gameSlug")({
  component: Outlet,
});
