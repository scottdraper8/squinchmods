export interface GameMetadata {
  readonly slug: string;
  readonly name: string;
  readonly hostname: string;
}

export interface ModMetadata {
  readonly slug: string;
  readonly name: string;
  readonly pages?: readonly string[];
}

export type GameWithMods = GameMetadata & {
  readonly mods: readonly ModMetadata[];
};
