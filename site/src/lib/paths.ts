export function internalGamePath(gameSlug: string): string {
  return "/games/" + gameSlug + "/";
}

export function internalModPath(gameSlug: string, modSlug: string): string {
  return "/games/" + gameSlug + "/mods/" + modSlug + "/";
}

function shouldUseInternalLinks(): boolean {
  return import.meta.env.DEV || import.meta.env.VITE_PREVIEW_BUILD;
}

export function publicHomeHref(): string {
  return shouldUseInternalLinks() ? "/" : "https://squinchmods.com/";
}

export function publicGameHref(hostname: string, gameSlug: string): string {
  return shouldUseInternalLinks() ? internalGamePath(gameSlug) : "https://" + hostname + "/";
}

export function publicModHref(gameSlug: string, modSlug: string): string {
  return shouldUseInternalLinks() ? internalModPath(gameSlug, modSlug) : "/" + modSlug + "/";
}
