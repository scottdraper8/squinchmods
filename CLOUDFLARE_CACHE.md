# Cloudflare Cache Optimization & Automation

This document outlines the strategy for maximizing documentation performance
using Cloudflare's "Cache Everything" rule and automating cache purging within
the GitHub Actions deployment workflow.

## 1. Cloudflare Configuration: "Cache Everything"

By default, Cloudflare does not cache HTML files. Since our documentation is
entirely static, we can achieve significantly faster load times by forcing
Cloudflare to cache every asset (including HTML) at the edge.

### Implementation Steps

1. Log in to the Cloudflare Dashboard.
2. Navigate to **Caching** > **Cache Rules** (or **Rules** > **Page Rules** on
   older accounts).
3. Create a new rule:
   - **If incoming request matches...** (Custom filter): `Hostname equals
     docs.squinchmods.com` (or your specific domain).
   - **Then...** (Cache eligibility): **Eligible for cache**.
4. In **Settings**, add the following:
   - **Cache Level**: Set to `Cache Everything`.
   - **Edge Cache TTL**: Set to a long duration (e.g., `7 days` or `1 month`).
   - **Browser Cache TTL**: Set to a shorter duration (e.g., `4 hours`) to
     ensure browsers check back for updates occasionally.

---

## 2. GitHub Actions: Automated Cache Purge

When "Cache Everything" is active with a long Edge TTL, Cloudflare will continue
serving old content even after you push an update to GitHub. We must automate a
"Purge Cache" command.

### Step A: Generate Cloudflare API Token

1. Go to your **Cloudflare Profile** > **API Tokens**.
2. Create a token using the **Clear Cache** template.
3. Scope it to your specific Zone (domain).
4. Save this token as a **GitHub Secret** named `CLOUDFLARE_API_TOKEN` in the
   repository settings (either the monorepo or the submodule).
5. Also, find your **Zone ID** on the domain Overview page and save it as
   `CLOUDFLARE_ZONE_ID`.

### Step B: Update `deploy-docs.yml`

Add the following step to the `deploy` job in `.github/workflows/deploy-docs.yml`:

```yaml
  deploy:
    # ... existing configuration ...
    steps:
      - name: Deploy to GitHub Pages
        id: deployment
        uses: actions/deploy-pages@v4

      - name: Purge Cloudflare Cache
        uses: nathanvaughn/cloudflare-purge-action@v3
        with:
          cloudflare_zone_id: ${{ secrets.CLOUDFLARE_ZONE_ID }}
          cloudflare_api_token: ${{ secrets.CLOUDFLARE_API_TOKEN }}
          # Optional: Purge only the specific docs path
          # purge_urls: '["https://docs.squinchmods.com/*"]'
```

## Benefits

- **Zero Latency**: HTML is served directly from the data center closest to the
  user.
- **Atomic Updates**: Users see the new documentation immediately after the
  GitHub Action finishes.
- **Lower Origin Load**: GitHub Pages servers are only hit once per data center
  per update cycle.
