// INVARIANT: Index 255 is permanently reserved as binary transparent alpha (0); indices 0..254 map to active StylePack colors
export const TRANSPARENT_INDEX = 255 as const;

export type PaletteIndex = number;
