import iconsText from "#/data/no-mans-sky/asset-wiki/icons.jsonld";
import itemsText from "#/data/no-mans-sky/asset-wiki/items.jsonld";

type DatasetName = "icons" | "items";

interface JsonLdDataset {
  gameVersion: string;
  steamBuild: string;
  recordCount: number;
  "@graph": Array<Record<string, unknown>>;
}

interface IndexedRecord {
  record: Record<string, unknown>;
  search: string;
}

const datasets: Record<DatasetName, JsonLdDataset> = {
  icons: JSON.parse(iconsText) as JsonLdDataset,
  items: JSON.parse(itemsText) as JsonLdDataset,
};

const searchableFields: Record<DatasetName, string[]> = {
  icons: ["name", "path", "category", "scope"],
  items: ["id", "name", "kind", "category", "rarity", "subtitle", "description", "tags"],
};

const indexes = Object.fromEntries(
  Object.entries(datasets).map(([name, dataset]) => [
    name,
    dataset["@graph"].map((record) => ({
      record,
      search: searchableFields[name as DatasetName]
        .flatMap((field) => record[field] ?? [])
        .join(" ")
        .toLocaleLowerCase("en-US"),
    })),
  ]),
) as Record<DatasetName, IndexedRecord[]>;

const filterFields: Record<DatasetName, string[]> = {
  icons: ["category", "scope"],
  items: ["kind", "category", "rarity"],
};

function isDatasetName(value: string | null): value is DatasetName {
  return value === "icons" || value === "items";
}

function facetValues(dataset: DatasetName): Record<string, string[]> {
  return Object.fromEntries(
    filterFields[dataset].map((field) => [
      field,
      [...new Set(datasets[dataset]["@graph"].map((record) => String(record[field] ?? "")))]
        .filter(Boolean)
        .sort((left, right) => left.localeCompare(right)),
    ]),
  );
}

const facets: Record<DatasetName, Record<string, string[]>> = {
  icons: facetValues("icons"),
  items: facetValues("items"),
};

function json(value: unknown, status = 200): Response {
  return Response.json(value, {
    status,
    headers: {
      "cache-control": "public, max-age=60",
      "content-type": "application/json; charset=utf-8",
    },
  });
}

export function searchAssetWiki(request: Request): Response {
  if (request.method !== "GET") {
    return json({ error: "Only GET is supported." }, 405);
  }

  const url = new URL(request.url);
  const dataset = url.searchParams.get("dataset");
  if (!isDatasetName(dataset)) {
    return json({ error: "dataset must be items or icons." }, 400);
  }

  const query = (url.searchParams.get("q") ?? "").trim().slice(0, 120);
  const tokens = query.toLocaleLowerCase("en-US").split(/\s+/).filter(Boolean);
  const selectedFilters = Object.fromEntries(
    filterFields[dataset]
      .map((field) => [field, url.searchParams.get(field)?.trim() ?? ""])
      .filter(([, value]) => value),
  );
  const offset = Math.max(0, Number.parseInt(url.searchParams.get("offset") ?? "0", 10) || 0);
  const limit = Math.min(
    60,
    Math.max(1, Number.parseInt(url.searchParams.get("limit") ?? "40", 10) || 40),
  );

  const matches = indexes[dataset].filter(
    ({ record, search }) =>
      tokens.every((token) => search.includes(token)) &&
      Object.entries(selectedFilters).every(([field, value]) => record[field] === value),
  );
  const records = matches.slice(offset, offset + limit).map(({ record }) => record);
  const source = datasets[dataset];
  return json({
    dataset,
    query,
    offset,
    limit,
    total: matches.length,
    returned: records.length,
    hasMore: offset + records.length < matches.length,
    records,
    facets: facets[dataset],
    gameVersion: source.gameVersion,
    steamBuild: source.steamBuild,
  });
}
