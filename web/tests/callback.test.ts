import { describe, expect, test } from "vitest";
import { consoleLine, isPrivateIpv4, lanCallbackUrl, readCallback, stateIp, stateValid } from "../src/callback";

const NONCE = "QEFCQ0RFRkdISUpLTE1OTw";

describe("readCallback", () => {
  test("reads the code, state and error", () => {
    expect(readCallback(`?code=AQDx&state=${NONCE}.192.168.1.23`)).toEqual({
      code: "AQDx",
      state: `${NONCE}.192.168.1.23`,
      error: null,
    });
    expect(readCallback("?error=access_denied&state=x")).toMatchObject({ code: null, error: "access_denied" });
  });
});

describe("private addresses", () => {
  test("covers exactly the private and link-local ranges", () => {
    for (const ip of ["10.0.0.1", "172.16.0.1", "172.31.255.255", "192.168.1.23", "169.254.10.1"]) {
      expect(isPrivateIpv4(ip)).toBe(true);
    }
    for (const ip of ["8.8.8.8", "172.15.0.1", "172.32.0.1", "127.0.0.1", "192.169.0.1", "0.0.0.0"]) {
      expect(isPrivateIpv4(ip)).toBe(false);
    }
  });
});

describe("state", () => {
  test("is a 22-character nonce, optionally with the owl's address", () => {
    expect(stateValid(NONCE)).toBe(true);
    expect(stateValid(`${NONCE}.10.0.2.15`)).toBe(true);
    expect(stateValid(`${NONCE}x`)).toBe(false);
    expect(stateIp(NONCE)).toBeNull();
    expect(stateIp(`${NONCE}.10.0.2.15`)).toBe("10.0.2.15");
  });
});

describe("lanCallbackUrl", () => {
  test("builds the owl's callback address", () => {
    expect(lanCallbackUrl(`${NONCE}.192.168.1.23`, "AQD-code_1.x~")).toBe(
      `http://192.168.1.23/callback?code=AQD-code_1.x~&state=${NONCE}.192.168.1.23`,
    );
  });

  test("lanCallbackUrl rejects public and malformed addresses", () => {
    const bad = [
      `${NONCE}.8.8.8.8`,
      `${NONCE}.127.0.0.1`,
      `${NONCE}.evil.example`,
      `${NONCE}.192.168.1.300`,
      `${NONCE}.192.168.01.2`,
      `${NONCE}.192.168.1.2.5`,
      `${NONCE}.10.0.0.1:8080`,
      `${NONCE}.10.0.0.1/x`,
      `${NONCE}@10.0.0.1`,
      "short.10.0.0.1",
      "",
    ];
    for (const state of bad) {
      expect(lanCallbackUrl(state, "AQDcode")).toBeNull();
    }
  });

  test("refuses codes it cannot put in a URL safely", () => {
    const state = `${NONCE}.10.0.0.1`;
    expect(lanCallbackUrl(state, "AQD&grant_type=x")).toBeNull();
    expect(lanCallbackUrl(state, 'AQD"><script>')).toBeNull();
    expect(lanCallbackUrl(state, "A".repeat(1024))).toBeNull();
    expect(lanCallbackUrl(state, "")).toBeNull();
  });
});

test("accepts Spotify's long codes, up to 1023 characters", () => {
  // Spotify's codes were 563 characters long in October 2026.
  const state = `${NONCE}.192.168.123.234`;
  expect(lanCallbackUrl(state, "A".repeat(563))).not.toBeNull();
  expect(lanCallbackUrl(state, "A".repeat(1023))).not.toBeNull();
});

test("consoleLine is a ready-to-paste protocol request", () => {
  expect(consoleLine("AQDx", `${NONCE}.10.0.0.1`)).toBe(
    `@owl {"id":1,"cmd":"spotify_code","code":"AQDx","state":"${NONCE}.10.0.0.1"}`,
  );
});
