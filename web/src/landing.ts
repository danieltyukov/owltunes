// Landing page: the volume ring you can turn with a pointer, the mouse wheel or the arrow keys.

import { angleAt, angleDelta, clampVolume, DETENT_DEG, STEP, turn } from "./dial";
import { $ } from "./dom";

const ARC_LENGTH = 100; // the arc's pathLength, so the dash length is the volume in percent

const ring = $<HTMLElement>("ring");
const arc = $<HTMLElement>("ring-arc");
const knob = $<HTMLElement>("ring-knob");
const readout = $<HTMLElement>("ring-value");

let volume = 62;
let rotation = volume * (DETENT_DEG / STEP);
let carry = 0;
let last: number | null = null;

function render(): void {
  arc.setAttribute("stroke-dasharray", `${volume} ${ARC_LENGTH}`);
  knob.style.transform = `rotate(${rotation}deg)`;
  readout.textContent = String(volume);
  ring.setAttribute("aria-valuenow", String(volume));
  ring.setAttribute("aria-valuetext", `Volume ${volume} percent`);
}

function click(clicks: number): void {
  if (clicks !== 0 && "vibrate" in navigator) {
    navigator.vibrate(6);
  }
}

function centre(): { cx: number; cy: number } {
  const box = ring.getBoundingClientRect();
  return { cx: box.left + box.width / 2, cy: box.top + box.height / 2 };
}

function rotateBy(deltaDeg: number): void {
  const before = volume;
  const next = turn(volume, carry, deltaDeg);
  volume = next.volume;
  // At either end the ring stops: no carry builds up against the bump.
  carry = volume === before && next.clicks !== 0 ? 0 : next.carryDeg;
  rotation += (volume - before) * (DETENT_DEG / STEP);
  click(volume - before);
  render();
}

function setVolume(value: number): void {
  const target = clampVolume(value);
  rotation += (target - volume) * (DETENT_DEG / STEP);
  click(target - volume);
  volume = target;
  carry = 0;
  render();
}

ring.addEventListener("pointerdown", (event) => {
  const { cx, cy } = centre();
  last = angleAt(event.clientX, event.clientY, cx, cy);
  ring.setPointerCapture(event.pointerId);
  event.preventDefault();
});

ring.addEventListener("pointermove", (event) => {
  if (last === null) {
    return;
  }
  const { cx, cy } = centre();
  const now = angleAt(event.clientX, event.clientY, cx, cy);
  rotateBy(angleDelta(last, now));
  last = now;
});

const release = (): void => {
  last = null;
};
ring.addEventListener("pointerup", release);
ring.addEventListener("pointercancel", release);

ring.addEventListener(
  "wheel",
  (event) => {
    event.preventDefault();
    rotateBy(event.deltaY < 0 ? DETENT_DEG : -DETENT_DEG);
  },
  { passive: false },
);

ring.addEventListener("keydown", (event) => {
  const keys: Record<string, number> = {
    ArrowUp: volume + STEP,
    ArrowRight: volume + STEP,
    ArrowDown: volume - STEP,
    ArrowLeft: volume - STEP,
    PageUp: volume + 10,
    PageDown: volume - 10,
    Home: 0,
    End: 100,
  };
  if (event.key in keys) {
    event.preventDefault();
    setVolume(keys[event.key]);
  }
});

render();
