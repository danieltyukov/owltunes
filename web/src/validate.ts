// Input checks that mirror the firmware's, so the page can explain a problem before the owl refuses it.

const encoder = new TextEncoder();
const byteLength = (s: string): number => encoder.encode(s).length;

/** Spotify shows client IDs as 32 lowercase hex characters; accept pasted ones with spaces or capitals. */
export function normalizeClientId(input: string): string {
  return input.trim().toLowerCase();
}

export function clientIdValid(id: string): boolean {
  return /^[0-9a-f]{32}$/.test(id);
}

/** Same rule as spotify_redirect_uri_valid: HTTPS or loopback, under 160 characters, no spaces or quotes. */
export function redirectUriValid(uri: string): boolean {
  if (uri.length >= 160 || !(uri.startsWith("https://") || uri.startsWith("http://127.0.0.1:"))) {
    return false;
  }
  return /^[!#-&(-;=?-[\]-~]+$/.test(uri);
}

export function ssidValid(ssid: string): boolean {
  const n = byteLength(ssid);
  return n >= 1 && n <= 32;
}

/** Open networks have no password; WPA passwords are 8 to 64 bytes. */
export function wifiPasswordValid(password: string): boolean {
  const n = byteLength(password);
  return n === 0 || (n >= 8 && n <= 64);
}

/** The callback page next to this one, so a fork's own site works without changes. */
export function defaultRedirectUri(pageUrl: string): string {
  return new URL("../callback/", pageUrl).href;
}
