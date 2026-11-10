# No Man's Sky reference-site tooling

`generate_glossary.py` builds the static item and technology data used by
`games/no-mans-sky/reference/site/glossary.html`.

The input directory must contain current MBINCompiler MXML exports for these installed-game tables:

- `NMS_REALITY_GCPRODUCTTABLE.MBIN`
- `NMS_REALITY_GCSUBSTANCETABLE.MBIN`
- `NMS_REALITY_GCTECHNOLOGYTABLE.MBIN`
- `NMS_REALITY_GCPROCEDURALTECHNOLOGYTABLE.MBIN`
- `PROCEDURALPRODUCTTABLE.MBIN`
- every installed English localisation bank

Generate the browser-ready data after extracting and decompiling those files into task scratch:

```bash
python games/no-mans-sky/tooling/reference/generate_glossary.py \
  --decompiled-root <path-to-current-mxml-exports>
```

The generator writes `glossary-data.js` into the reference site. It resolves English display text,
retains internal IDs and source keys, and links entries to any matching WebP previews already in the
site asset tree. Re-extract from the installed game and regenerate when the supported game build is
bumped.
