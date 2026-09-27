# Squinchmods Site Plan

**Status:** the initial static site slice and Workers host-routing adapter are in place. Local
Worker runtime checks have passed; the GitHub Actions deployment and custom-domain setup remain to
be verified.

This document is the working plan for the website in **site/**. It records the intended stack,
content model, public URLs, deployment, and the first implementation checks.

## Goals

- Publish a portfolio landing page and game-specific mod wikis.
- Use TypeScript, React TSX, and SCSS for reusable UI and interactive visualizations.
- Generate pages as static files wherever possible. The site has no accounts, database, or
  user-written data.
- Keep each game's content together, each mod's content under its game, and shared UI in one shared
  area.
- Use conventions that are familiar to React and TypeScript contributors and coding agents.

## Public URL contract

| Public URL                              | Page                          |
| --------------------------------------- | ----------------------------- |
| `https://squinchmods.com/`              | Main portfolio landing page   |
| `https://<game>.squinchmods.com/`       | Landing page for one game     |
| `https://<game>.squinchmods.com/<mod>/` | Wiki landing page for one mod |

For example, minecraft.squinchmods.com/ is the Minecraft landing page and
minecraft.squinchmods.com/redstone-backport/ is that mod's wiki. Game and mod URL slugs should be
lowercase, stable, and URL-safe.

The browser-facing URLs are intentionally independent of the app's internal route names. A typed
route catalog maps each hostname and public path to the matching game or mod page. The first
implementation includes the main landing page, Minecraft game page, and Redstone Backport wiki
overview.

## Proposed stack

| Concern                     | Choice                           | Reason                                                                                                |
| --------------------------- | -------------------------------- | ----------------------------------------------------------------------------------------------------- |
| UI and routes               | TanStack Start with React        | Familiar TSX components, file-based routes, typed navigation, and static prerendering for known pages |
| Build and local development | Vite through TanStack Start      | Fast local server with hot reload and one build pipeline                                              |
| Language                    | TypeScript in strict mode        | Type checking for route params, game/mod metadata, and shared components                              |
| Styles                      | SCSS                             | Shared variables, mixins, nesting, and component or page styles                                       |
| Hosting and deploys         | Cloudflare Workers Static Assets | Static asset hosting, Git-based builds, preview deployments, and custom domains                       |
| Host/path adaptation        | A small Cloudflare Worker        | Selects the pre-rendered game or mod page from the request hostname and path                          |

TanStack Start is used as a static site generator: file routes define page structure, and known
pages are prerendered at build time. No always-running application server is needed.

## Language toolchains and environment

Each language project keeps its own package manager and lockfile. The site targets Node 24.21.0 in
`.node-version` and pins pnpm 12.6.0 in `package.json`; its dependencies and scripts stay in
`site/`. `pnpm-workspace.yaml` sets a 24-hour package release-age gate and explicitly controls
dependency build scripts. Python projects use their existing `uv` projects and lockfiles, Rust uses
Cargo and its `rust-toolchain.toml`, and Minecraft's Gradle work uses the Java version declared by
`games/minecraft/tooling/.sdkmanrc`.

`direnv` loads environment variables when entering a directory; it does not install or select
language runtimes. Keep the existing `games/minecraft/.envrc`, which loads the Minecraft JDK and
shared cache locations. The static site has no environment-specific variables or secrets, so it does
not need an `.envrc`. There is no need to add a monorepo-wide runtime manager or Bazel unless
cross-project build dependencies become a real requirement.

## Host routing and static delivery

The same build serves the apex domain and configured game subdomains. Since the hostname changes
which page belongs at /, a Worker maps the public hostname and path to the matching prerendered HTML
file:

1. Keep an explicit, typed catalog of games and mods.
2. Prerender the portfolio, every registered game landing page, and every registered mod page.
3. Use a Worker to map the incoming host and public path to the corresponding prerendered route
   output.
4. Configure Workers Static Assets to serve images, scripts, stylesheets, and other static files
   directly. `assets.run_worker_first` sends page paths through the Worker while excluding static
   asset paths.
5. Use a TanStack input rewrite to translate game-host URLs to internal routes. Typed URL helpers
   produce public link destinations; cross-host links use normal browser navigation.

The Worker is stateless routing glue. It uses the `ASSETS` binding to fetch prerendered pages; it
does not access a database or store user data. Unknown hosts and mod slugs return a not-found
response.

Add squinchmods.com and each active game hostname (such as minecraft.squinchmods.com) as custom
domains on the Worker. The DNS zone must be managed by Cloudflare; Cloudflare creates the required
DNS records and certificates when the custom domains are attached. See
[Workers custom domains](https://developers.cloudflare.com/workers/configuration/routing/custom-domains/).

Static asset requests are served without invoking the Worker. Page requests invoke the Worker
because `assets.run_worker_first` is configured for those paths.

## Site structure

    site/
    ├── .node-version
    ├── README.md
    ├── package.json
    ├── pnpm-workspace.yaml
    ├── pnpm-lock.yaml
    ├── tsconfig.json
    ├── vite.config.ts
    ├── biome.json
    ├── wrangler.jsonc
    ├── worker.ts
    ├── public/
    │   └── favicon.svg
    └── src/
        ├── router.tsx
        ├── routeTree.gen.ts
        ├── vite-env.d.ts
        ├── routes/
        │   ├── __root.tsx
        │   ├── index.tsx
        │   └── games/
        │       ├── route.tsx
        │       ├── index.tsx
        │       └── $gameSlug/
        │           ├── route.tsx
        │           ├── index.tsx
        │           └── mods/
        │               ├── route.tsx
        │               └── $modSlug.tsx
        ├── content/
        │   ├── catalog.ts
        │   ├── types.ts
        │   └── games/
        │       └── minecraft/
        │           ├── game.ts
        │           └── mods/
        │               └── redstone-backport/
        │                   ├── mod.ts
        │                   ├── Overview.tsx
        │                   └── styles.scss
        ├── components/
        │   └── layout/
        │       └── SiteShell.tsx
        ├── styles/
        │   ├── main.scss
        │   └── _tokens.scss
        └── lib/
            ├── paths.ts
            └── url-rewrites.ts

Each game gets a directory under src/content/games/; its mods live below that game's mods/
directory. A mod owns its metadata, page components, styles, and later its own assets. Shared page
components live under src/components/.

The typed catalog is the source for valid game and mod slugs, hostnames, metadata, and prerender
paths. File-based routes define page/layout structure. TanStack generates routeTree.gen.ts; keep it
generated rather than editing it manually. The build output lives in site/dist/client and is ignored
by Git.

## Repository-level tooling

The website lives in site/, but repository-wide tooling stays at the repository root:

- Keep the existing root .gitignore, .prettierrc.yaml, and .pre-commit-config.yaml; extend them when
  site files need coverage rather than creating duplicate site copies.
- Keep the site's Biome configuration and package scripts in site/.
- Root pre-commit hooks use Biome for site TS/TSX, Prettier for Markdown, SCSS, and site config,
  markdownlint-cli2 for Markdown, and Ruff for Python. They also run the site's TypeScript and
  production build checks when relevant site files change.
- Do not create a second site-specific AGENTS.md unless the site later needs rules that differ from
  the repository instructions. This README is the site architecture and contributor plan.

The site provides `dev`, `build`, `typecheck`, `lint`, `format`, `format:check`, `check`, and
`workers:dev` scripts. Vite writes the static output to `site/dist/client`.

## GitHub Actions deployment

Production deployments run from `.github/workflows/deploy-site.yml` when changes to `site/` or the
workflow are pushed to `main`. The workflow checks out the repository without initializing Git
submodules, installs pnpm 12.6.0 and Node 24.21.0, builds the site, then runs `wrangler deploy` from
`site/`. The Worker name is `squinchmods`, as set in `wrangler.jsonc`.

Add these GitHub Actions repository secrets:

- `CLOUDFLARE_API_TOKEN`: an account API token with the `Editor` role scoped to the existing
  `squinchmods` Worker.
- `CLOUDFLARE_ACCOUNT_ID`: the Cloudflare account that owns the Worker.

The Worker is created separately in Cloudflare; GitHub Actions updates it on deployment. This setup
does not use Cloudflare Workers Builds or its GitHub integration. Add the apex and game hostnames as
custom domains on the Worker after deployment; Cloudflare creates the corresponding DNS records and
certificates.

The Wrangler configuration in `wrangler.jsonc` records the Worker entry point, static asset output
directory, binding, and local development settings. Avoid checking generated output into source
control. See
[Workers Builds image documentation](https://developers.cloudflare.com/workers/ci-cd/builds/build-image/)
for runtime version selection and
[Workers Static Assets local development](https://developers.cloudflare.com/workers/static-assets/)
for the local runtime.

References:
[Workers Git integration](https://developers.cloudflare.com/workers/ci-cd/builds/git-integration/)
and [Workers Static Assets](https://developers.cloudflare.com/workers/static-assets/).

## Workers migration check

The first vertical slice covers the portfolio, one game hostname, and one mod page. Local Worker
runtime checks confirmed that direct requests return the expected prerendered HTML, canonical
trailing-slash redirects work, unknown hosts/mods return 404, and static assets bypass the Worker.
The GitHub Actions production deployment and custom-domain behavior still need verification. Browser
interaction and hydration have not been checked yet.

## Reference documentation

- [TanStack Start static prerendering](https://tanstack.com/start/latest/docs/framework/react/guide/static-prerendering)
- [TanStack Router file-based routing](https://tanstack.com/router/latest/docs/routing/file-naming-conventions)
- [TanStack Router URL rewrites](https://tanstack.com/router/latest/docs/guide/url-rewrites)
- [Cloudflare Workers Static Assets](https://developers.cloudflare.com/workers/static-assets/)
- [Cloudflare Workers custom domains](https://developers.cloudflare.com/workers/configuration/routing/custom-domains/)
- [Cloudflare Workers Builds](https://developers.cloudflare.com/workers/ci-cd/builds/)
- [pnpm installation and version management](https://pnpm.io/installation/)
- [direnv](https://direnv.net/)
- [SDKMAN! usage](https://sdkman.io/usage/)
