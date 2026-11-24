import { type PaletteIndex, type Point2D, TRANSPARENT_INDEX } from './types.js';

const CARDINAL_DIRS: readonly (readonly [number, number])[] = [
  [0, -1],
  [1, 0],
  [0, 1],
  [-1, 0],
];

function normalizeIndex(color: PaletteIndex): number {
  const idx = color | 0;
  if (idx < 0 || idx > TRANSPARENT_INDEX) {
    throw new RangeError(`Palette index ${color} out of range [0..${TRANSPARENT_INDEX}]`);
  }
  return idx;
}

function roundPoint(p: Point2D): Point2D {
  const x = Math.round(p.x);
  const y = Math.round(p.y);
  return { x: x === 0 ? 0 : x, y: y === 0 ? 0 : y };
}

/**
 * Deterministic integer-grid indexed framebuffer backed by a Uint8Array.
 * Index 255 is permanently reserved as binary transparent alpha (0).
 */
export class IndexedSurface {
  readonly width: number;
  readonly height: number;
  readonly data: Uint8Array;

  constructor(width: number, height: number, initialData?: Uint8Array) {
    const w = width | 0;
    const h = height | 0;
    if (w <= 0 || h <= 0) {
      throw new RangeError(`Surface dimensions must be positive, got ${width}x${height}`);
    }
    this.width = w;
    this.height = h;
    if (initialData) {
      if (initialData.length !== w * h) {
        throw new RangeError(
          `Expected buffer length ${w * h} for ${w}x${h} surface, got ${initialData.length}`,
        );
      }
      this.data = new Uint8Array(initialData);
    } else {
      this.data = new Uint8Array(w * h);
      this.data.fill(TRANSPARENT_INDEX);
    }
  }

  inBounds(x: number, y: number): boolean {
    const ix = x | 0;
    const iy = y | 0;
    return ix >= 0 && ix < this.width && iy >= 0 && iy < this.height;
  }

  get(x: number, y: number): PaletteIndex {
    const ix = x | 0;
    const iy = y | 0;
    if (ix < 0 || ix >= this.width || iy < 0 || iy >= this.height) {
      return TRANSPARENT_INDEX;
    }
    return this.data[iy * this.width + ix] ?? TRANSPARENT_INDEX;
  }

  put(x: number, y: number, color: PaletteIndex): void {
    // INVARIANT: Truncate to integer grid and clamp OOB silently to prevent mixels or scanline wrap
    const ix = x | 0;
    const iy = y | 0;
    if (ix < 0 || ix >= this.width || iy < 0 || iy >= this.height) {
      return;
    }
    this.data[iy * this.width + ix] = normalizeIndex(color);
  }

  clear(color: PaletteIndex = TRANSPARENT_INDEX): void {
    this.data.fill(normalizeIndex(color));
  }

  clone(): IndexedSurface {
    return new IndexedSurface(this.width, this.height, this.data);
  }

  rect(x: number, y: number, w: number, h: number, color: PaletteIndex, fill = true): void {
    const ix = x | 0;
    const iy = y | 0;
    const iw = w | 0;
    const ih = h | 0;
    if (iw <= 0 || ih <= 0) return;

    const c = normalizeIndex(color);
    if (fill) {
      this.fillRectClamped(ix, iy, iw, ih, c);
      return;
    }
    this.strokeRectClamped(ix, iy, iw, ih, c);
  }

  private fillRectClamped(x: number, y: number, w: number, h: number, color: number): void {
    const x0 = Math.max(0, x);
    const y0 = Math.max(0, y);
    const x1 = Math.min(this.width, x + w);
    const y1 = Math.min(this.height, y + h);
    for (let py = y0; py < y1; py++) {
      const rowOffset = py * this.width;
      this.data.fill(color, rowOffset + x0, rowOffset + x1);
    }
  }

  private strokeRectClamped(x: number, y: number, w: number, h: number, color: number): void {
    const x1 = x + w - 1;
    const y1 = y + h - 1;
    for (let px = x; px <= x1; px++) {
      this.put(px, y, color);
      this.put(px, y1, color);
    }
    for (let py = y + 1; py < y1; py++) {
      this.put(x, py, color);
      this.put(x1, py, color);
    }
  }

  quad(p0: Point2D, p1: Point2D, p2: Point2D, p3: Point2D, color: PaletteIndex): void {
    const c = normalizeIndex(color);
    const verts: readonly [Point2D, Point2D, Point2D, Point2D] = [
      roundPoint(p0),
      roundPoint(p1),
      roundPoint(p2),
      roundPoint(p3),
    ];

    let minY = verts[0].y;
    let maxY = verts[0].y;
    for (let i = 1; i < 4; i++) {
      const vy = verts[i]?.y ?? minY;
      if (vy < minY) minY = vy;
      if (vy > maxY) maxY = vy;
    }

    const yStart = Math.max(0, minY);
    const yEnd = Math.min(this.height - 1, maxY);
    const xs: number[] = [];

    for (let y = yStart; y <= yEnd; y++) {
      xs.length = 0;
      for (let i = 0; i < 4; i++) {
        const a = verts[i] as Point2D;
        const b = verts[(i + 1) & 3] as Point2D;
        if ((a.y <= y && b.y > y) || (b.y <= y && a.y > y)) {
          xs.push(a.x + ((y - a.y) * (b.x - a.x)) / (b.y - a.y));
        }
      }
      xs.sort((a, b) => a - b);
      for (let i = 0; i + 1 < xs.length; i += 2) {
        const x0 = Math.round(xs[i] as number);
        const x1 = Math.round(xs[i + 1] as number);
        this.hSpan(x0, x1, y, c);
      }
    }

    // INVARIANT: Stroke perimeter edges after scanline fill so horizontal/degenerate edges are never dropped
    for (let i = 0; i < 4; i++) {
      const a = verts[i] as Point2D;
      const b = verts[(i + 1) & 3] as Point2D;
      this.line(a.x, a.y, b.x, b.y, c);
    }
  }

  line(x0: number, y0: number, x1: number, y1: number, color: PaletteIndex): void {
    let ix0 = x0 | 0;
    let iy0 = y0 | 0;
    const ix1 = x1 | 0;
    const iy1 = y1 | 0;
    const c = normalizeIndex(color);

    const dx = Math.abs(ix1 - ix0);
    const dy = -Math.abs(iy1 - iy0);
    const sx = ix0 < ix1 ? 1 : -1;
    const sy = iy0 < iy1 ? 1 : -1;
    let err = dx + dy;

    while (true) {
      this.put(ix0, iy0, c);
      if (ix0 === ix1 && iy0 === iy1) break;
      const e2 = 2 * err;
      if (e2 >= dy) {
        err += dy;
        ix0 += sx;
      }
      if (e2 <= dx) {
        err += dx;
        iy0 += sy;
      }
    }
  }

  circle(cx: number, cy: number, radius: number, color: PaletteIndex, fill = true): void {
    const icx = cx | 0;
    const icy = cy | 0;
    const r = radius | 0;
    if (r < 0) return;

    const c = normalizeIndex(color);
    if (r === 0) {
      this.put(icx, icy, c);
      return;
    }

    let x = r;
    let y = 0;
    let err = 1 - r;
    while (x >= y) {
      if (fill) {
        this.hSpan(icx - x, icx + x, icy + y, c);
        this.hSpan(icx - x, icx + x, icy - y, c);
        this.hSpan(icx - y, icx + y, icy + x, c);
        this.hSpan(icx - y, icx + y, icy - x, c);
      } else {
        this.plotOctants(icx, icy, x, y, c);
      }
      y++;
      if (err < 0) {
        err += 2 * y + 1;
      } else {
        x--;
        err += 2 * (y - x) + 1;
      }
    }
  }

  private hSpan(x0: number, x1: number, y: number, color: number): void {
    if (y < 0 || y >= this.height) return;
    const start = Math.max(0, x0);
    const end = Math.min(this.width - 1, x1);
    if (start > end) return;
    const rowOffset = y * this.width;
    this.data.fill(color, rowOffset + start, rowOffset + end + 1);
  }

  private plotOctants(cx: number, cy: number, x: number, y: number, color: number): void {
    this.put(cx + x, cy + y, color);
    this.put(cx - x, cy + y, color);
    this.put(cx + x, cy - y, color);
    this.put(cx - x, cy - y, color);
    this.put(cx + y, cy + x, color);
    this.put(cx - y, cy + x, color);
    this.put(cx + y, cy - x, color);
    this.put(cx - y, cy - x, color);
  }

  fill(x: number, y: number, color: PaletteIndex): void {
    const ix = x | 0;
    const iy = y | 0;
    if (!this.inBounds(ix, iy)) return;

    const target = this.get(ix, iy);
    const replacement = normalizeIndex(color);
    if (target === replacement) return;

    const stack: number[] = [ix, iy];
    while (stack.length > 0) {
      const sy = stack.pop() as number;
      const sx = stack.pop() as number;
      if (this.get(sx, sy) !== target) continue;

      let lx = sx;
      while (lx > 0 && this.get(lx - 1, sy) === target) lx--;
      let rx = sx;
      while (rx < this.width - 1 && this.get(rx + 1, sy) === target) rx++;

      const rowOffset = sy * this.width;
      this.data.fill(replacement, rowOffset + lx, rowOffset + rx + 1);

      this.scanNeighborRow(lx, rx, sy - 1, target, stack);
      this.scanNeighborRow(lx, rx, sy + 1, target, stack);
    }
  }

  private scanNeighborRow(
    lx: number,
    rx: number,
    ny: number,
    target: number,
    stack: number[],
  ): void {
    if (ny < 0 || ny >= this.height) return;
    let spanActive = false;
    for (let px = lx; px <= rx; px++) {
      const matches = this.get(px, ny) === target;
      if (matches && !spanActive) {
        stack.push(px, ny);
        spanActive = true;
      } else if (!matches) {
        spanActive = false;
      }
    }
  }

  spr(
    grid: readonly string[],
    x: number,
    y: number,
    colorMap: Readonly<Record<string, PaletteIndex>>,
  ): void {
    const ox = x | 0;
    const oy = y | 0;
    for (let row = 0; row < grid.length; row++) {
      const line = grid[row];
      if (!line) continue;
      for (let col = 0; col < line.length; col++) {
        const ch = line[col];
        if (!ch || ch === '.' || ch === ' ') continue;
        const idx = colorMap[ch];
        if (idx !== undefined && idx !== TRANSPARENT_INDEX) {
          this.put(ox + col, oy + row, idx);
        }
      }
    }
  }

  blitLayer(src: IndexedSurface, dx = 0, dy = 0): void {
    const ox = dx | 0;
    const oy = dy | 0;
    for (let sy = 0; sy < src.height; sy++) {
      const ty = oy + sy;
      if (ty < 0 || ty >= this.height) continue;
      for (let sx = 0; sx < src.width; sx++) {
        const tx = ox + sx;
        if (tx < 0 || tx >= this.width) continue;
        const px = src.data[sy * src.width + sx] ?? TRANSPARENT_INDEX;
        if (px !== TRANSPARENT_INDEX) {
          this.data[ty * this.width + tx] = px;
        }
      }
    }
  }

  autoOutline(outlineColor: PaletteIndex): void {
    const c = normalizeIndex(outlineColor);
    const snapshot = new Uint8Array(this.data);
    for (let y = 0; y < this.height; y++) {
      for (let x = 0; x < this.width; x++) {
        const idx = y * this.width + x;
        if ((snapshot[idx] ?? TRANSPARENT_INDEX) !== TRANSPARENT_INDEX) continue;
        if (this.hasOpaqueCardinalNeighbor(snapshot, x, y)) {
          this.data[idx] = c;
        }
      }
    }
  }

  private hasOpaqueCardinalNeighbor(snapshot: Uint8Array, x: number, y: number): boolean {
    for (const [dx, dy] of CARDINAL_DIRS) {
      const nx = x + dx;
      const ny = y + dy;
      if (nx < 0 || nx >= this.width || ny < 0 || ny >= this.height) continue;
      if ((snapshot[ny * this.width + nx] ?? TRANSPARENT_INDEX) !== TRANSPARENT_INDEX) {
        return true;
      }
    }
    return false;
  }

  edgeMask(topColor?: PaletteIndex, bottomColor?: PaletteIndex): void {
    const topC = topColor !== undefined ? normalizeIndex(topColor) : undefined;
    const botC = bottomColor !== undefined ? normalizeIndex(bottomColor) : undefined;
    if (topC === undefined && botC === undefined) return;

    const snapshot = new Uint8Array(this.data);
    for (let y = 0; y < this.height; y++) {
      for (let x = 0; x < this.width; x++) {
        const idx = y * this.width + x;
        if ((snapshot[idx] ?? TRANSPARENT_INDEX) === TRANSPARENT_INDEX) continue;

        const aboveEmpty =
          y === 0 ||
          (snapshot[(y - 1) * this.width + x] ?? TRANSPARENT_INDEX) === TRANSPARENT_INDEX;
        const belowEmpty =
          y === this.height - 1 ||
          (snapshot[(y + 1) * this.width + x] ?? TRANSPARENT_INDEX) === TRANSPARENT_INDEX;

        if (aboveEmpty && topC !== undefined) {
          this.data[idx] = topC;
        } else if (belowEmpty && botC !== undefined) {
          this.data[idx] = botC;
        }
      }
    }
  }
}

export function createSurface(width: number, height: number): IndexedSurface {
  return new IndexedSurface(width, height);
}
