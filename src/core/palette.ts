import type { PaletteIndex, RenderContext, StylePack } from './types.js';

export type PaletteSource = StylePack | Pick<RenderContext, 'style'>;

function extractStyle(source: PaletteSource): StylePack {
  return 'style' in source ? source.style : source;
}

/**
 * Resolves named StylePack palette tokens into a lookup record of PaletteIndex values.
 * Throws an explicit error if any requested token is missing from the StylePack.
 */
export function createPaletteLookup<const TTokens extends readonly string[]>(
  source: PaletteSource,
  tokens: TTokens,
): Readonly<Record<TTokens[number], PaletteIndex>>;
export function createPaletteLookup(source: PaletteSource): Readonly<Record<string, PaletteIndex>>;
export function createPaletteLookup(
  source: PaletteSource,
  tokens?: readonly string[],
): Readonly<Record<string, PaletteIndex>> {
  const style = extractStyle(source);
  const byName = new Map<string, PaletteIndex>();
  for (const entry of style.palette) {
    byName.set(entry.name, entry.index);
  }

  const record: Record<string, PaletteIndex> = {};
  if (tokens !== undefined) {
    for (const token of tokens) {
      const idx = byName.get(token);
      if (idx === undefined) {
        throw new Error(`Missing palette token: ${token} (style: ${style.id})`);
      }
      record[token] = idx;
    }
  } else {
    for (const [name, idx] of byName) {
      record[name] = idx;
    }
  }

  // INVARIANT: Fail loudly on unknown token reads instead of returning undefined,
  // which would silently coerce to palette index 0 in Uint8Array surface writes.
  return new Proxy(record, {
    get(target, prop, receiver) {
      if (typeof prop !== 'string') {
        return Reflect.get(target, prop, receiver);
      }
      if (Object.hasOwn(target, prop)) {
        return target[prop];
      }
      if (prop === 'then') {
        return undefined;
      }
      throw new Error(`Missing palette token: ${prop} (style: ${style.id})`);
    },
  });
}
