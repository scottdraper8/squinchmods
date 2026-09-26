export interface GameMetadata {
  readonly slug: string;
  readonly name: string;
  readonly hostname: string;
  readonly description: string;
}

export interface ModFeature {
  readonly title: string;
  readonly detail: string;
  readonly sourceVersion: string;
}

export interface ModMetadata {
  readonly slug: string;
  readonly name: string;
  readonly minecraftVersion: string;
  readonly status: string;
  readonly loaders: readonly string[];
  readonly description: string;
  readonly features: readonly ModFeature[];
  readonly license: string;
  readonly repository: string;
}

export type GameWithMods = GameMetadata & {
  readonly mods: Record<string, ModMetadata>;
};
