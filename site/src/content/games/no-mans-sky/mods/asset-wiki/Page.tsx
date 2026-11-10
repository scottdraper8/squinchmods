import { type FormEvent, useCallback, useEffect, useRef, useState } from "react";

type DatasetName = "icons" | "items";
type AssetRecord = Record<string, unknown>;

interface SearchResult {
  dataset: DatasetName;
  total: number;
  hasMore: boolean;
  records: AssetRecord[];
  facets: Record<string, string[]>;
  gameVersion: string;
  steamBuild: string;
}

function stringValue(record: AssetRecord, key: string): string {
  const value = record[key];
  return typeof value === "string" ? value : "";
}

function previewHref(value: string): string {
  if (typeof window !== "undefined" && window.location.hostname !== "no-mans-sky.squinchmods.com") {
    return value.replace("/asset-wiki/", "/games/no-mans-sky/mods/asset-wiki/");
  }
  return value;
}

function AssetResult({ dataset, record }: { dataset: DatasetName; record: AssetRecord }) {
  const preview = stringValue(record, "preview");
  const name = stringValue(record, "name") || stringValue(record, "path");
  return (
    <li>
      {preview ? (
        <img src={previewHref(preview)} alt="" loading="lazy" width="96" height="96" />
      ) : null}
      <h2>{name}</h2>
      {dataset === "items" ? (
        <>
          <p>
            <code>{stringValue(record, "id")}</code> — {stringValue(record, "kind")} —{" "}
            {stringValue(record, "category")} — {stringValue(record, "rarity")}
          </p>
          {stringValue(record, "description") ? <p>{stringValue(record, "description")}</p> : null}
        </>
      ) : (
        <p>
          <code>{stringValue(record, "path")}</code> — {stringValue(record, "category")} —{" "}
          {String(record.width ?? "?")}×{String(record.height ?? "?")}
        </p>
      )}
    </li>
  );
}

export function AssetWikiPage() {
  const [dataset, setDataset] = useState<DatasetName>("items");
  const [draftQuery, setDraftQuery] = useState("");
  const [query, setQuery] = useState("");
  const [filters, setFilters] = useState<Record<string, string>>({});
  const [facets, setFacets] = useState<Record<string, string[]>>({});
  const [records, setRecords] = useState<AssetRecord[]>([]);
  const [total, setTotal] = useState(0);
  const [hasMore, setHasMore] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [version, setVersion] = useState("");
  const requestGeneration = useRef(0);
  const sentinel = useRef<HTMLDivElement>(null);

  const load = useCallback(
    async (offset: number, replace: boolean) => {
      const generation = replace ? ++requestGeneration.current : requestGeneration.current;
      setLoading(true);
      setError("");
      const parameters = new URLSearchParams({
        dataset,
        q: query,
        offset: String(offset),
        limit: "40",
      });
      for (const [field, value] of Object.entries(filters)) {
        if (value) parameters.set(field, value);
      }
      try {
        const response = await fetch("/api/asset-wiki/search/?" + parameters);
        if (!response.ok) throw new Error(`Search failed (${response.status}).`);
        const result = (await response.json()) as SearchResult;
        if (generation !== requestGeneration.current) return;
        setRecords((current) => (replace ? result.records : [...current, ...result.records]));
        setTotal(result.total);
        setHasMore(result.hasMore);
        setFacets(result.facets);
        setVersion(`${result.gameVersion}; Steam build ${result.steamBuild}`);
      } catch (reason) {
        if (generation === requestGeneration.current) {
          setError(reason instanceof Error ? reason.message : "Search failed.");
        }
      } finally {
        if (generation === requestGeneration.current) setLoading(false);
      }
    },
    [dataset, filters, query],
  );

  useEffect(() => {
    void load(0, true);
  }, [load]);

  useEffect(() => {
    const node = sentinel.current;
    if (!node || !hasMore || loading) return;
    const observer = new IntersectionObserver((entries) => {
      if (entries.some((entry) => entry.isIntersecting)) void load(records.length, false);
    });
    observer.observe(node);
    return () => observer.disconnect();
  }, [hasMore, load, loading, records.length]);

  function submit(event: FormEvent) {
    event.preventDefault();
    setQuery(draftQuery.trim());
  }

  function changeDataset(value: DatasetName) {
    setDataset(value);
    setFilters({});
  }

  return (
    <main>
      <h1>Asset Wiki</h1>
      <p>
        Items, technology, and icon assets extracted from No Man&apos;s Sky {version || "7.14"}.
      </p>
      <form onSubmit={submit}>
        <p>
          <label>
            Catalog{" "}
            <select
              value={dataset}
              onChange={(event) => changeDataset(event.target.value as DatasetName)}
            >
              <option value="items">Items and technology</option>
              <option value="icons">Icons</option>
            </select>
          </label>
        </p>
        <p>
          <label>
            Search{" "}
            <input
              value={draftQuery}
              onChange={(event) => setDraftQuery(event.target.value)}
              type="search"
            />
          </label>{" "}
          <button type="submit">Search</button>
        </p>
        {Object.entries(facets).map(([field, values]) => (
          <p key={field}>
            <label>
              {field.charAt(0).toUpperCase() + field.slice(1)}{" "}
              <select
                value={filters[field] ?? ""}
                onChange={(event) =>
                  setFilters((current) => ({ ...current, [field]: event.target.value }))
                }
              >
                <option value="">All</option>
                {values.map((value) => (
                  <option key={value} value={value}>
                    {value}
                  </option>
                ))}
              </select>
            </label>
          </p>
        ))}
      </form>
      <p>{total.toLocaleString()} matching records.</p>
      {error ? <p role="alert">{error}</p> : null}
      <ol>
        {records.map((record) => (
          <AssetResult key={String(record["@id"])} dataset={dataset} record={record} />
        ))}
      </ol>
      <div ref={sentinel}>{loading ? <p>Loading…</p> : null}</div>
      {hasMore && !loading ? (
        <button type="button" onClick={() => void load(records.length, false)}>
          Load more
        </button>
      ) : null}
    </main>
  );
}
