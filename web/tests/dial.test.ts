import { describe, expect, test } from "vitest";
import { angleAt, angleDelta, clampVolume, DETENT_DEG, STEP, turn } from "../src/dial";

describe("ring angle", () => {
  test("is 0 at the top and grows clockwise", () => {
    expect(angleAt(0, -10, 0, 0)).toBeCloseTo(0);
    expect(angleAt(10, 0, 0, 0)).toBeCloseTo(90);
    expect(angleAt(0, 10, 0, 0)).toBeCloseTo(180);
    expect(angleAt(-10, 0, 0, 0)).toBeCloseTo(270);
  });

  test("takes the short way across the top", () => {
    expect(angleDelta(350, 10)).toBe(20);
    expect(angleDelta(10, 350)).toBe(-20);
  });
});

describe("turning the ring", () => {
  test("one detent changes the volume by one step", () => {
    expect(turn(50, 0, DETENT_DEG)).toEqual({ volume: 50 + STEP, clicks: 1, carryDeg: 0 });
    expect(turn(50, 0, -DETENT_DEG)).toEqual({ volume: 50 - STEP, clicks: -1, carryDeg: 0 });
  });

  test("keeps rotation that is not yet a detent", () => {
    const first = turn(50, 0, 10);
    expect(first.clicks).toBe(0);
    expect(turn(first.volume, first.carryDeg, 10)).toEqual({ volume: 52, clicks: 1, carryDeg: 5 });
  });

  test("stops at 0 and 100", () => {
    expect(turn(98, 0, 5 * DETENT_DEG).volume).toBe(100);
    expect(turn(2, 0, -5 * DETENT_DEG).volume).toBe(0);
    expect(clampVolume(-3)).toBe(0);
  });
});
