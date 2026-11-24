import type { IndexedSurface } from './surface.js';

// INVARIANT: Index 255 is permanently reserved as binary transparent alpha (0); indices 0..254 map to active StylePack colors
export const TRANSPARENT_INDEX = 255 as const;

export type PaletteIndex = number;

export type PerspectiveMode = 'front-2.5d' | 'iso-2:1' | 'top-down' | 'side';

export type LightingAngle = 'top-left' | 'top-right' | 'top';

export type PaletteFlag = 'outline' | 'emissive' | 'shadow' | 'metal' | 'accent' | 'surface';

export interface PaletteColorSpec {
  readonly index: PaletteIndex;
  readonly name: string;
  readonly hex: `#${string}`;
  readonly flags?: readonly PaletteFlag[];
}

export interface StylePack {
  readonly id: string;
  readonly perspective: PerspectiveMode;
  readonly lightingAngle: LightingAngle;
  readonly outlineIndex: PaletteIndex;
  readonly palette: readonly PaletteColorSpec[];
  readonly variants?: Readonly<Record<string, Readonly<Record<string, `#${string}`>>>>;
}

export interface Point2D {
  readonly x: number;
  readonly y: number;
}

export interface AnchorPoint {
  readonly name: string;
  readonly x: number;
  readonly y: number;
}

export interface HitboxRect {
  readonly name: string;
  readonly x: number;
  readonly y: number;
  readonly w: number;
  readonly h: number;
}

export interface RenderContext<TState extends string = string> {
  readonly surface: IndexedSurface;
  readonly style: StylePack;
  readonly state: TState;
  readonly frame: number;
  readonly frameCount: number;
  readonly rng: () => number;
  anchor(name: string, x: number, y: number): void;
  hitbox(name: string, x: number, y: number, w: number, h: number): void;
}

export interface AssetModule<TState extends string = 'default'> {
  readonly id: string;
  readonly styleId: string;
  readonly width: number;
  readonly height: number;
  readonly perspective: PerspectiveMode;
  readonly states: readonly TState[];
  readonly frames: number;
  readonly fps?: number;
  readonly seed?: number;
  render(ctx: RenderContext<TState>): void;
}
