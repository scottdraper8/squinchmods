import { type FormEvent, useCallback, useEffect, useRef, useState } from "react";

type DatasetName = "colour-filters" | "icons" | "items";
type AssetRecord = Record<string, unknown>;
type Rgb = [number, number, number];

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

function numberValue(record: AssetRecord, key: string): number {
  const value = record[key];
  return typeof value === "number" ? value : 0;
}

function rgbValues(value: unknown): Rgb[] {
  if (!Array.isArray(value)) return [];
  return value.flatMap((entry) =>
    Array.isArray(entry) &&
    entry.length === 3 &&
    entry.every((channel) => typeof channel === "number")
      ? [[entry[0], entry[1], entry[2]] as Rgb]
      : [],
  );
}

function mix(left: Rgb, right: Rgb, amount: number): Rgb {
  return left.map((value, index) => value + (right[index] - value) * amount) as Rgb;
}

function cssColour(colour: Rgb): string {
  return `rgb(${colour
    .map((value) => Math.round(Math.max(0, Math.min(1, value)) * 255))
    .join(", ")})`;
}

const testColourNames = [
  "Red",
  "Orange",
  "Yellow",
  "Green",
  "Cyan",
  "Blue",
  "Magenta",
  "Dark grey",
  "Grey",
  "White",
];

const testColours: Rgb[] = [
  [0.8, 0.1, 0.1],
  [0.9, 0.5, 0.1],
  [0.8, 0.8, 0.1],
  [0.1, 0.8, 0.1],
  [0.1, 0.8, 0.8],
  [0.1, 0.1, 0.8],
  [0.8, 0.1, 0.8],
  [0.1, 0.1, 0.1],
  [0.5, 0.5, 0.5],
  [0.9, 0.9, 0.9],
];

function ColourChip({ colour }: { colour: Rgb }) {
  const css = cssColour(colour);
  return (
    <span
      title={css}
      style={{
        background: css,
        border: "1px solid currentColor",
        display: "block",
        height: "2.5rem",
        minWidth: "6rem",
      }}
    />
  );
}

function ColourFilterExplorer({ records }: { records: AssetRecord[] }) {
  const [nativeValue, setNativeValue] = useState(18);
  const [blend, setBlend] = useState(100);
  const baseline = records.find((record) => numberValue(record, "native_value") === 0);
  const selected =
    records.find((record) => numberValue(record, "native_value") === nativeValue) ?? baseline;

  useEffect(() => {
    if (records.length > 0 && !selected) {
      setNativeValue(numberValue(records[0], "native_value"));
    }
  }, [records, selected]);

  if (!baseline || !selected) return null;
  const amount = blend / 100;
  const baselineSamples = rgbValues(baseline.samples);
  const selectedSamples = rgbValues(selected.samples);
  const baselineRamp = rgbValues(baseline.grey_ramp);
  const selectedRamp = rgbValues(selected.grey_ramp);
  const description = stringValue(selected, "description") || stringValue(selected, "name");
  const fadeDistance = numberValue(selected, "fade_distance");

  return (
    <section aria-label="World colour filter comparison">
      <p>
        Compare the actual SDR colour transformations from the installed game. These are isolated
        LUT outputs, not simulated planet screenshots. Lighting, exposure, fog, HDR encoding, and
        the game&apos;s distance, storm, and effect blending are not included.
      </p>
      <p>
        <label>
          World filter{" "}
          <select
            value={numberValue(selected, "native_value")}
            onChange={(event) => setNativeValue(Number(event.target.value))}
          >
            {records.map((record) => (
              <option key={String(record["@id"])} value={numberValue(record, "native_value")}>
                {stringValue(record, "name")}
                {stringValue(record, "description")
                  ? ` — ${stringValue(record, "description")}`
                  : ""}
              </option>
            ))}
          </select>
        </label>
      </p>
      <p>
        <label>
          Blend with Default{" "}
          <input
            type="range"
            min="0"
            max="100"
            value={blend}
            onChange={(event) => setBlend(Number(event.target.value))}
          />{" "}
          <output>{blend}%</output>
        </label>
      </p>
      <p>
        {description}
        {fadeDistance ? " · The game configures distance fading for this filter." : ""}
      </p>
      <dl>
        <dt>Native value</dt>
        <dd>{numberValue(selected, "native_value")}</dd>
        <dt>SDR LUT</dt>
        <dd>
          <code>{stringValue(selected, "sdr")}</code>
        </dd>
        <dt>HDR LUT</dt>
        <dd>
          <code>{stringValue(selected, "hdr")}</code>
        </dd>
        <dt>Configured distance fade</dt>
        <dd>{fadeDistance ? `${fadeDistance} game units` : "None"}</dd>
      </dl>
      <div style={{ overflowX: "auto" }}>
        <table>
          <thead>
            <tr>
              <th>Test colour</th>
              <th>Input</th>
              <th>Default grading</th>
              <th>Selected grading</th>
            </tr>
          </thead>
          <tbody>
            {testColourNames.map((name, index) => {
              const baselineColour = baselineSamples[index];
              const selectedColour = selectedSamples[index];
              if (!baselineColour || !selectedColour) return null;
              return (
                <tr key={name}>
                  <th scope="row">{name}</th>
                  <td>
                    <ColourChip colour={testColours[index]} />
                  </td>
                  <td>
                    <ColourChip colour={baselineColour} />
                  </td>
                  <td>
                    <ColourChip colour={mix(baselineColour, selectedColour, amount)} />
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
      <h2>Grey ramp</h2>
      <div
        role="img"
        aria-label="Selected filter grey ramp"
        style={{ border: "1px solid currentColor", display: "flex", height: "3.5rem" }}
      >
        {selectedRamp.map((colour, index) => {
          const baselineColour = baselineRamp[index];
          if (!baselineColour) return null;
          return (
            <span
              key={`${numberValue(selected, "native_value")}-${colour.join("-")}`}
              style={{ background: cssColour(mix(baselineColour, colour, amount)), flex: 1 }}
            />
          );
        })}
      </div>
      <p>
        The blend slider is a comparison aid, not a reproduction of a native game control. This
        catalog includes filters with positive weight in current planet biome definitions.
        Weird-filter descriptions are analytical labels; other entries retain their internal names
        pending description. An assigned planet filter does not establish constant full-strength
        grading in every view.
      </p>
    </section>
  );
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
      if (dataset === "colour-filters") parameters.set("limit", "60");
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
    setDraftQuery("");
    setQuery("");
    setFilters({});
  }

  return (
    <main>
      <h1>Asset Wiki</h1>
      <p>
        Items, technology, world colour filters, and icon assets extracted from No Man&apos;s Sky{" "}
        {version || "7.14"}.
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
              <option value="colour-filters">World colour filters</option>
              <option value="icons">Icons</option>
            </select>
          </label>
        </p>
        {dataset !== "colour-filters" ? (
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
        ) : null}
        {dataset !== "colour-filters" &&
          Object.entries(facets).map(([field, values]) => (
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
      <p>
        {total.toLocaleString()}{" "}
        {dataset === "colour-filters" ? "world filters" : "matching records"}.
      </p>
      {error ? <p role="alert">{error}</p> : null}
      {dataset === "colour-filters" ? (
        <ColourFilterExplorer records={records} />
      ) : (
        <ol>
          {records.map((record) => (
            <AssetResult key={String(record["@id"])} dataset={dataset} record={record} />
          ))}
        </ol>
      )}
      <div ref={dataset === "colour-filters" ? undefined : sentinel}>
        {loading ? <p>Loading…</p> : null}
      </div>
      {dataset !== "colour-filters" && hasMore && !loading ? (
        <button type="button" onClick={() => void load(records.length, false)}>
          Load more
        </button>
      ) : null}
    </main>
  );
}
