import { cp, mkdir } from "node:fs/promises";
import { fileURLToPath } from "node:url";

const siteRoot = fileURLToPath(new URL("..", import.meta.url));
const repositoryRoot = fileURLToPath(new URL("../..", import.meta.url));
const source = `${repositoryRoot}games/no-mans-sky/reference/asset-wiki/assets`;
const destination = `${siteRoot}dist/client/games/no-mans-sky/mods/asset-wiki/assets`;

await mkdir(destination, { recursive: true });
await cp(source, destination, { recursive: true, force: true });
