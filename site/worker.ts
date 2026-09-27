import { findGameByHostname, findMod } from "./src/content/catalog";
import type { GameWithMods } from "./src/content/types";

interface AssetBinding {
  fetch(input: Request | string | URL, init?: RequestInit): Promise<Response>;
}

interface Env {
  ASSETS: AssetBinding;
}

function notFound(): Response {
  return new Response("Page not found.", {
    status: 404,
    headers: { "content-type": "text/plain; charset=utf-8" },
  });
}

function internalPagePath(game: GameWithMods, publicPath: string): string | undefined {
  if (publicPath === "/") {
    return "/games/" + game.slug + "/";
  }

  const segments = publicPath.split("/").filter(Boolean);
  const modSlug = segments[0];
  if (!modSlug || !findMod(game, modSlug)) {
    return undefined;
  }

  const nestedPath = segments.slice(1).join("/");
  const modPath = "/games/" + game.slug + "/mods/" + modSlug;

  if (nestedPath.length === 0) {
    return modPath + "/";
  }

  return modPath + "/" + nestedPath + (publicPath.endsWith("/") ? "/" : "");
}

export default {
  async fetch(request: Request, env: Env): Promise<Response> {
    const requestUrl = new URL(request.url);
    const hostname = requestUrl.hostname;

    if (hostname === "squinchmods.com" || hostname.endsWith(".workers.dev")) {
      return env.ASSETS.fetch(request);
    }

    const game = findGameByHostname(hostname);
    if (!game) {
      return notFound();
    }

    if (requestUrl.pathname !== "/" && !requestUrl.pathname.endsWith("/")) {
      requestUrl.pathname += "/";
      return Response.redirect(requestUrl, 308);
    }

    const path = internalPagePath(game, requestUrl.pathname);
    if (!path) {
      return notFound();
    }

    requestUrl.pathname = path;
    return env.ASSETS.fetch(new Request(requestUrl, request));
  },
};
