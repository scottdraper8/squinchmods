# Local No Man's Sky data

Personal, persistent save-derived data lives below `games/no-mans-sky/local/`. Git ignores that
directory, and tranche cleanup does not remove it. The save CLI publishes the current combined
entity library to `games/no-mans-sky/local/save-library/`, including complete `bases.json`,
`starships.json`, `multitools.json`, and authoritative `systems.json` objects plus a hash manifest.
Refresh entity inventories with `library-publish`; it preserves an existing systems authority.
Publish a newly combined systems authority with `library-publish-systems`. Both workflows archive
the prior published library before replacement.
