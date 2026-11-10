# No Man's Sky Asset Wiki ETL

The maintained Asset Wiki lives at `https://no-mans-sky.squinchmods.com/asset-wiki/`. Its compact
JSON-LD datasets live under `site/src/data/no-mans-sky/asset-wiki/`, and its generated WebP previews
live under `games/no-mans-sky/reference/asset-wiki/assets/` for the site build to copy. There is no
second reference-site frontend.

The source corpus contains these installed-game tables plus every installed English localisation
bank:

- `NMS_REALITY_GCPRODUCTTABLE.MBIN`
- `NMS_REALITY_GCSUBSTANCETABLE.MBIN`
- `NMS_REALITY_GCTECHNOLOGYTABLE.MBIN`
- `NMS_REALITY_GCPROCEDURALTECHNOLOGYTABLE.MBIN`
- `PROCEDURALPRODUCTTABLE.MBIN`

Create a task tranche and extract the current source corpus. Extraction performs read-only MBIN
decompilation, so it remains available when the installed build is newer than the compiler's
recompilation allowlist:

```bash
tooling/squinch tranche create <id>
tooling/squinch --tranche <id> nms-investigate asset-wiki-source --json
```

The run manifest retains the tables, localisation banks, full icon catalog, every additional DDS
referenced by the tables, hashes, and archive provenance. Use it to refresh the WebP previews and
both JSON-LD datasets in one operation:

```bash
python games/no-mans-sky/tooling/reference/refresh_asset_wiki.py \
  --source-manifest <asset-wiki-source-manifest.json>
```

Pass `--reuse-previews` only when validating unchanged source DDS files. The JSON-LD remains
server-side Worker data: the browser queries bounded result batches and never loads a complete
catalog during normal use.
