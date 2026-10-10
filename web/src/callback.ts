// The Spotify callback: reading the redirect, handing the code to the setup tab, and the fallbacks.

export const CHANNEL = "owltunes-auth";

export type Handoff =
  | { type: "code"; code: string; state: string }
  | { type: "ack"; state: string; ok: boolean; error?: string };

export interface CallbackParams {
  code: string | null;
  state: string | null;
  error: string | null;
}

export function readCallback(search: string): CallbackParams {
  const q = new URLSearchParams(search);
  return { code: q.get("code"), state: q.get("state"), error: q.get("error") };
}

const CODE = /^[A-Za-z0-9._~-]{1,511}$/;
const OCTET = "(25[0-5]|2[0-4][0-9]|1[0-9][0-9]|[1-9]?[0-9])";
const STATE = new RegExp(`^[A-Za-z0-9_-]{22}(?:\\.(${OCTET}\\.${OCTET}\\.${OCTET}\\.${OCTET}))?$`);

export function codeValid(code: string): boolean {
  return CODE.test(code);
}

export function stateValid(state: string): boolean {
  return STATE.test(state);
}

/** 10/8, 172.16/12, 192.168/16 and link-local 169.254/16: the only places an owl can be. */
export function isPrivateIpv4(ip: string): boolean {
  const m = new RegExp(`^${OCTET}\\.${OCTET}\\.${OCTET}\\.${OCTET}$`).exec(ip);
  if (m === null) {
    return false;
  }
  const [a, b] = [Number(m[1]), Number(m[2])];
  return a === 10 || (a === 172 && b >= 16 && b <= 31) || (a === 192 && b === 168) || (a === 169 && b === 254);
}

/** The owl's address carried in the state ("<nonce>.<ipv4>"), or null. */
export function stateIp(state: string): string | null {
  const m = STATE.exec(state);
  if (m === null || m[1] === undefined) {
    return null;
  }
  const ip = state.slice(state.indexOf(".") + 1);
  return isPrivateIpv4(ip) ? ip : null;
}

/** http://<owl>/callback for the LAN fallback, or null when the state names no private address. */
export function lanCallbackUrl(state: string, code: string): string | null {
  const ip = stateIp(state);
  if (ip === null || !codeValid(code)) {
    return null;
  }
  return `http://${ip}/callback?code=${encodeURIComponent(code)}&state=${encodeURIComponent(state)}`;
}

/** The line to paste into the owl's USB console when nothing else can reach it. */
export function consoleLine(code: string, state: string): string {
  return `@owl ${JSON.stringify({ id: 1, cmd: "spotify_code", code, state })}`;
}
