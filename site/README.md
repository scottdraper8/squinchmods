# Squinchmods Site Plan

**Status:** initial implementation slice is in place. This document records the target architecture
and the verified first vertical slice.

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

| Concern                     | Choice                            | Reason                                                                                                |
| --------------------------- | --------------------------------- | ----------------------------------------------------------------------------------------------------- |
| UI and routes               | TanStack Start with React         | Familiar TSX components, file-based routes, typed navigation, and static prerendering for known pages |
| Build and local development | Vite through TanStack Start       | Fast local server with hot reload and one build pipeline                                              |
| Language                    | TypeScript in strict mode         | Type checking for route params, game/mod metadata, and shared components                              |
| Styles                      | SCSS                              | Shared variables, mixins, nesting, and component or page styles                                       |
| Hosting and deploys         | Cloudflare Pages                  | Static asset hosting, Git-based builds, preview deployments, and custom domains                       |
| Host/path adaptation        | A small Cloudflare Pages Function | Selects the pre-rendered game or mod page from the request hostname and path                          |

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
which page belongs at /, a Pages Function maps the public hostname and path to the matching
prerendered HTML file:

1. Keep an explicit, typed catalog of games and mods.
2. Prerender the portfolio, every registered game landing page, and every registered mod page.
3. Use a narrow Pages Function to map the incoming host and public path to the corresponding
   prerendered route output.
4. Let Cloudflare Pages serve images, scripts, stylesheets, and other static files directly.
   Configure function routing so requests for those assets do not invoke the Function.
5. Use a TanStack input rewrite to translate game-host URLs to internal routes. Typed URL helpers
   produce public link destinations; cross-host links use normal browser navigation.

The Function is stateless routing glue. It uses Pages' static asset binding to fetch prerendered
pages; it does not access a database or store user data. Unknown hosts and mod slugs return a
not-found response.

**Cloudflare domain constraint:** Pages does not support wildcard custom domains. Add
squinchmods.com and each active game hostname (such as minecraft.squinchmods.com) to the Pages
project explicitly. Cloudflare currently documents a limit of 100 custom domains per Free Pages
project. If the project approaches that limit, revisit hostname routing before adding more game
subdomains. See
[Pages custom domains](https://developers.cloudflare.com/pages/configuration/custom-domains/),
[wildcard DNS records](https://developers.cloudflare.com/dns/manage-dns-records/reference/wildcard-dns-records/),
and [Pages limits](https://developers.cloudflare.com/pages/platform/limits/).

Pages Function requests count against the Workers usage quota, so the route adapter should run only
for page navigations. The generated \_routes.json excludes static asset paths.

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
    ├── public/
    │   ├── _routes.json
    │   └── favicon.svg
    ├── functions/
    │   └── _middleware.ts
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
`pages:dev` scripts. Vite writes the static Pages output to `site/dist/client`, which is confirmed
by the first build.

## Cloudflare Pages CI/CD

Connect the GitHub repository to one Cloudflare Pages project. Set the project root to `site/`, use
pnpm with `pnpm-lock.yaml`, run `pnpm build`, and publish `dist/client`. The site pins Node 24.21.0
in `.node-version` and pnpm 12.6.0 in `package.json`. Set the Pages build variable
`PNPM_VERSION=12.6.0` because the current Pages build image does not infer pnpm's version from the
lockfile. Cloudflare Pages supports `.node-version` for Node selection. Git integration can build
production commits and create preview deployments for other branches without a separate GitHub
Actions workflow or a Cloudflare API token. Configure the apex domain and each game hostname as
custom domains on that same project.

The Wrangler configuration in `wrangler.jsonc` records the output directory and local Pages
settings. Avoid checking generated output into source control. See
[Cloudflare's build image documentation](https://developers.cloudflare.com/pages/configuration/build-image/)
for runtime version selection and
[Pages local development](https://developers.cloudflare.com/pages/functions/local-development/) for
the local Functions runtime.

References:
[Cloudflare Pages Git integration](https://developers.cloudflare.com/pages/get-started/git-integration/)
and
[build configuration](https://developers.cloudflare.com/pages/configuration/build-configuration/).

## First implementation check

The first vertical slice covers the portfolio, one game hostname, and one mod page. Local Pages
checks confirm that direct requests return the right pre-rendered HTML, canonical trailing-slash
redirects work, unknown hosts/mods return 404, and static assets bypass the Function. The generated
HTML links use the public hostname/path scheme. Browser interaction and hydration have not been
checked yet.

Route-specific SEO metadata and a deployed Cloudflare preview still need verification before the
site grows beyond this initial slice. This check validates the host-aware routing boundary and
static output layout locally.

## Reference documentation

- [TanStack Start static prerendering](https://tanstack.com/start/latest/docs/framework/react/guide/static-prerendering)
- [TanStack Router file-based routing](https://tanstack.com/router/latest/docs/routing/file-naming-conventions)
- [TanStack Router URL rewrites](https://tanstack.com/router/latest/docs/guide/url-rewrites)
- [Cloudflare Pages Functions routing](https://developers.cloudflare.com/pages/functions/routing/)
- [Cloudflare Pages Functions middleware](https://developers.cloudflare.com/pages/functions/middleware/)
- [Cloudflare Pages custom domains](https://developers.cloudflare.com/pages/configuration/custom-domains/)
- [Cloudflare Pages limits](https://developers.cloudflare.com/pages/platform/limits/)
- [pnpm installation and version management](https://pnpm.io/installation/)
- [direnv](https://direnv.net/)
- [SDKMAN! usage](https://sdkman.io/usage/)
