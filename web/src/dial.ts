// The volume ring on the landing page: the same detent maths as the owl's ring, 24 clicks per turn
// and 2 percent per click, kept free of the DOM so it can be tested.

export const DETENT_DEG = 15;
export const STEP = 2;

/** Angle of (x, y) around (cx, cy) in degrees, 0 at the top, growing clockwise. */
export function angleAt(x: number, y: number, cx: number, cy: number): number {
  const deg = (Math.atan2(x - cx, cy - y) * 180) / Math.PI;
  return deg < 0 ? deg + 360 : deg;
}

/** Shortest signed difference from one angle to the next, in -180..180. */
export function angleDelta(from: number, to: number): number {
  return ((to - from + 540) % 360) - 180;
}

export function clampVolume(value: number): number {
  return Math.min(100, Math.max(0, Math.round(value)));
}

/**
 * Turn the ring by `deltaDeg` with `carryDeg` left over from earlier moves. Returns the new volume,
 * how many detents were crossed and the rotation not yet worth a detent.
 */
export function turn(volume: number, carryDeg: number, deltaDeg: number): { volume: number; clicks: number; carryDeg: number } {
  const total = carryDeg + deltaDeg;
  const clicks = Math.trunc(total / DETENT_DEG);
  return { volume: clampVolume(volume + clicks * STEP), clicks, carryDeg: total - clicks * DETENT_DEG };
}
