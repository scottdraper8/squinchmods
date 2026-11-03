# Squinchmods Site

The root domain lists games, and each game has its own subdomain for its mods and mod pages. The
current site is a deliberately minimal proof of concept: pages use semantic HTML and browser default
styling. The SCSS entry point stays connected but is intentionally empty. Do not treat the current
content as a finished design direction.

## Public routes

| Host                          | Path                  | Page                      |
| ----------------------------- | --------------------- | ------------------------- |
| `squinchmods.com`             | `/`                   | List of games             |
| `minecraft.squinchmods.com`   | `/`                   | List of Minecraft mods    |
| `minecraft.squinchmods.com`   | `/redstone-backport/` | Redstone Backport page    |
| `no-mans-sky.squinchmods.com` | `/`                   | List of No Man's Sky mods |
| `no-mans-sky.squinchmods.com` | `/generous-giver/`    | Generous Giver page       |
| `no-mans-sky.squinchmods.com` | `/search-probes/`     | Empty Search Probes page  |

The Worker maps these public host and path pairs to internal prerendered routes. For example,
`minecraft.squinchmods.com/redstone-backport/` maps to `/games/minecraft/mods/redstone-backport/`.

## Content and routes

`src/content/catalog.ts` is the source of truth for games and their mods. Each game has a slug,
hostname, and metadata in `src/content/games/<game>/game.ts`. Each mod has metadata and a page under
`src/content/games/<game>/mods/<mod>/`. Add games and mods to the catalog to include them in the
home and game lists; Vite prerenders their internal routes from that catalog.

```text
site/src/
├── content/
│   ├── catalog.ts
│   ├── types.ts
│   └── games/
│       ├── minecraft/
│       │   ├── game.ts
│       │   └── mods/redstone-backport/
│       │       ├── mod.ts
│       │       └── Page.tsx
│       └── no-mans-sky/
│           ├── game.ts
│           └── mods/
│               ├── generous-giver/
│               │   ├── mod.ts
│               │   └── Page.tsx
│               └── search-probes/
│                   ├── mod.ts
│                   └── Page.tsx
├── routes/
├── lib/
└── styles/main.scss
```

## Architecture

- **UI and routes:** React with TanStack Start and TanStack Router.
- **Build:** Vite prerenders game and mod routes as static HTML in `dist/client`.
- **Language and styles:** strict TypeScript and SCSS. The root route imports `styles/main.scss`;
  keep that pipeline wired even while the stylesheet is empty.
- **Runtime:** `worker.ts` maps hostnames and public paths to prerendered pages. Unknown hosts or
  mod slugs return 404. Game-host paths without a trailing slash redirect to the canonical URL.
- **Hosting:** Cloudflare Workers Static Assets serves the generated pages and files. The `ASSETS`
  binding lets the Worker fetch mapped pages; `assets.run_worker_first` sends page routes through
  the Worker while static asset paths bypass it.
- **Data:** static site with no database, accounts, or user-submitted content.

The Worker is named `squinchmods`. `wrangler.jsonc` defines its entry point, static asset directory,
binding, compatibility date, and local development settings. The Worker is also available on its
`workers.dev` hostname. Custom domains are attached separately in Cloudflare, which creates their
DNS records and certificates.

## Deployment and credentials

[`../.github/workflows/deploy-site.yml`](../.github/workflows/deploy-site.yml) deploys production.
Pushes to `main` that change `site/` or the workflow install dependencies from the committed
lockfile, build the site, and run `wrangler deploy` from `site/`. The workflow can also be started
manually. Cloudflare Workers Builds and its GitHub connection are not used.

GitHub Actions uses these repository secrets:

- `CLOUDFLARE_API_TOKEN`: account API token named `squinchmods-site`, with the **Editor** role
  scoped to the `squinchmods` Worker.
- `CLOUDFLARE_ACCOUNT_ID`: the account that owns the Worker.

The `squinchmods-site` API token expires **2027-09-27**. Rotate it before then and update the
`CLOUDFLARE_API_TOKEN` GitHub secret.

## Local development

Run commands from `site/`:

```sh
pnpm install --frozen-lockfile
pnpm run dev
pnpm run workers:dev
```

`pnpm run dev` starts Vite on port 3000 with hot reload. Its links use internal routes, such as
`/games/minecraft/` and `/games/no-mans-sky/`, so the pages can be previewed without local DNS or
Cloudflare configuration. `pnpm run workers:dev` builds the site and runs Wrangler locally on
port 8788. `pnpm run build` creates the production output, and `pnpm run typecheck` checks
TypeScript.
