# Squinchmods Site

## Purpose

The site is a home for game mods, projects, and their documentation. The main hostname is a
portfolio; each game has a landing page on its own subdomain, with mod information and wiki pages
nested below it.

## MVP status

The current site is an infrastructure MVP. Its content and appearance are temporary and will change
substantially when product and design work begins. The minimal pages currently in the site exist to
confirm static generation, hostname-based routing, Cloudflare hosting, and GitHub Actions
deployment. Treat the current visual design as disposable; the route and content organization below
describes the intended technical foundation.

## Current public route map

| Host                        | Path                  | Page                                |
| --------------------------- | --------------------- | ----------------------------------- |
| `squinchmods.com`           | `/`                   | Portfolio landing page              |
| `squinchmods.com`           | `/games/`             | Game index                          |
| `minecraft.squinchmods.com` | `/`                   | Minecraft landing page and mod list |
| `minecraft.squinchmods.com` | `/redstone-backport/` | Redstone Backport wiki overview     |

The public hostname and path are mapped to internal prerendered routes. For example,
`minecraft.squinchmods.com/redstone-backport/` maps to `/games/minecraft/mods/redstone-backport/`.
The current catalog contains one game and one mod; add more entries in `src/content/catalog.ts`.

## Source organization

```text
site/
├── .node-version
├── package.json
├── pnpm-lock.yaml
├── pnpm-workspace.yaml
├── vite.config.ts
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
    │   └── games/minecraft/
    │       ├── game.ts
    │       └── mods/redstone-backport/
    │           ├── mod.ts
    │           ├── Overview.tsx
    │           └── styles.scss
    ├── components/layout/SiteShell.tsx
    ├── lib/
    │   ├── paths.ts
    │   └── url-rewrites.ts
    └── styles/
        ├── main.scss
        └── _tokens.scss
```

`src/content/catalog.ts` is the source of truth for registered games and mods. Keep each game's
metadata under `src/content/games/<game>/`, and each mod's metadata, page components, and styles
under that game's `mods/<mod>/` directory. Shared layout, URL helpers, and global styles live in
`components/`, `lib/`, and `styles/`. TanStack Router generates `src/routeTree.gen.ts`; do not edit
it by hand.

## Architecture

- **UI and routes:** React with TanStack Start and TanStack Router.
- **Build:** Vite prerenders the known game and mod routes as static HTML in `dist/client`.
- **Language and styles:** strict TypeScript and SCSS.
- **Runtime:** a small Cloudflare Worker in `worker.ts` maps hostnames and public paths to the
  prerendered pages. Unknown hosts or mod slugs return 404; game-host paths without a trailing slash
  redirect to the canonical URL.
- **Static files:** Cloudflare Workers Static Assets serves the prerendered HTML and files. The
  `ASSETS` binding lets the Worker fetch mapped pages; `assets.run_worker_first` sends page routes
  through the Worker while static asset paths bypass it.
- **Data:** the site is static and has no database, accounts, or user-submitted content.
- **Versions:** Node is pinned in `.node-version` (24.21.0); pnpm is pinned in `package.json`
  (12.6.0). `pnpm-workspace.yaml` sets dependency release-age and build-script policies.

The Worker name is `squinchmods`. `wrangler.jsonc` defines the entry point, static asset directory,
binding, compatibility date, and local development settings. The initial deployment is available on
its `workers.dev` hostname. Custom domains are configured separately in Cloudflare, which creates
the matching DNS records and certificates when they are attached.

## Deployment and credentials

[`../.github/workflows/deploy-site.yml`](../.github/workflows/deploy-site.yml) is the production
deployment path. On pushes to `main` that change `site/` or the workflow, it checks out the
repository **without submodules**, installs the pinned Node and pnpm versions, builds the site, and
runs `wrangler deploy` from `site/`. It can also be started manually with `workflow_dispatch`.
Cloudflare Workers Builds and its GitHub connection are not used.

The existing Cloudflare Worker is deployed from this workflow. GitHub Actions uses these repository
secrets:

- `CLOUDFLARE_API_TOKEN`: account API token named `squinchmods-site`, with the **Editor** role
  scoped to the `squinchmods` Worker.
- `CLOUDFLARE_ACCOUNT_ID`: the account that owns the Worker.

The `squinchmods-site` API token expires **2027-09-27**. Rotate it before that date and update the
`CLOUDFLARE_API_TOKEN` GitHub secret.

## Local development

Run commands from `site/`:

```sh
pnpm install --frozen-lockfile
pnpm run dev
pnpm run workers:dev
```

`pnpm run dev` starts the Vite development server. `pnpm run workers:dev` builds the site and runs
the Worker locally. `pnpm run build` creates the production output, and `pnpm run typecheck` checks
TypeScript.
