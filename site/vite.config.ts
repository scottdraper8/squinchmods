import { tanstackStart } from "@tanstack/react-start/plugin/vite";
import viteReact from "@vitejs/plugin-react";
import { defineConfig } from "vite";
import { games } from "./src/content/catalog.ts";

const prerenderPages = Object.values(games).flatMap((game) => [
  {
    path: "/games/" + game.slug + "/",
    prerender: { enabled: true },
  },
  ...Object.values(game.mods).map((mod) => ({
    path: "/games/" + game.slug + "/mods/" + mod.slug + "/",
    prerender: { enabled: true },
  })),
]);

const config = defineConfig({
  define: {
    "import.meta.env.VITE_PREVIEW_BUILD": JSON.stringify(
      process.env.WORKERS_CI === "1" &&
        process.env.WORKERS_CI_BRANCH !== (process.env.SQUINCHMODS_PRODUCTION_BRANCH ?? "main"),
    ),
  },
  resolve: { tsconfigPaths: true },
  plugins: [
    tanstackStart({
      prerender: {
        enabled: true,
        crawlLinks: false,
        failOnError: true,
      },
      pages: prerenderPages,
    }),
    viteReact(),
  ],
});

export default config;
