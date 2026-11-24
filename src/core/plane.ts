import type { Point2D } from './types.js';

function roundInt(n: number): number {
  const r = Math.round(n);
  return r === 0 ? 0 : r;
}

/**
 * Projects normalized (u, v) coordinates onto an arbitrary angled 2D plane
 * defined by origin p0 (0, 0), u-axis endpoint p1 (1, 0), and v-axis endpoint p2 (0, 1).
 */
export function planeProject(p0: Point2D, p1: Point2D, p2: Point2D, u: number, v: number): Point2D {
  const x = roundInt(p0.x + (p1.x - p0.x) * u + (p2.x - p0.x) * v);
  const y = roundInt(p0.y + (p1.y - p0.y) * u + (p2.y - p0.y) * v);
  return { x, y };
}
