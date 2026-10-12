import { describe, expect, test } from "vitest";
import {
  clientIdValid,
  defaultRedirectUri,
  normalizeClientId,
  redirectUriValid,
  ssidValid,
  wifiPasswordValid,
} from "../src/validate";

describe("client ID", () => {
  test("accepts 32 lowercase hex characters after normalising", () => {
    expect(clientIdValid(normalizeClientId("  0123456789ABCDEF0123456789abcdef \n"))).toBe(true);
  });

  test("rejects other lengths and characters", () => {
    expect(clientIdValid("0123456789abcdef")).toBe(false);
    expect(clientIdValid("0123456789abcdef0123456789abcdeg")).toBe(false);
    expect(clientIdValid("")).toBe(false);
  });
});

describe("redirect URI", () => {
  test("accepts HTTPS and loopback", () => {
    expect(redirectUriValid("https://danieltyukov.github.io/owltunes/callback/")).toBe(true);
    expect(redirectUriValid("http://127.0.0.1:18080/callback")).toBe(true);
  });

  test("rejects plain HTTP, quotes, spaces and long values", () => {
    expect(redirectUriValid("http://example.com/callback")).toBe(false);
    expect(redirectUriValid("http://localhost:8080/callback")).toBe(false);
    expect(redirectUriValid('https://example.com/"x')).toBe(false);
    expect(redirectUriValid("https://example.com/a b")).toBe(false);
    expect(redirectUriValid(`https://example.com/${"a".repeat(140)}`)).toBe(false);
  });
});

describe("Wi-Fi", () => {
  test("SSIDs are 1 to 32 bytes", () => {
    expect(ssidValid("Home")).toBe(true);
    expect(ssidValid("")).toBe(false);
    expect(ssidValid("\u00e9".repeat(17))).toBe(false);
  });

  test("passwords are empty or 8 to 64 bytes", () => {
    expect(wifiPasswordValid("")).toBe(true);
    expect(wifiPasswordValid("password")).toBe(true);
    expect(wifiPasswordValid("short77")).toBe(false);
    expect(wifiPasswordValid("p".repeat(65))).toBe(false);
  });

  test("names and passwords refuse control characters, as the owl does", () => {
    expect(ssidValid("Home\nTwo")).toBe(false);
    expect(ssidValid("Home\u001b[2J")).toBe(false);
    expect(ssidValid("Home\u007f")).toBe(false);
    expect(ssidValid("\u0000")).toBe(false);
    expect(wifiPasswordValid("pass\tword1")).toBe(false);
    expect(wifiPasswordValid("password\r\n")).toBe(false);
    expect(wifiPasswordValid("password\u007f")).toBe(false);
    expect(ssidValid('Caf\u00e9 "5G" ~')).toBe(true);
    expect(wifiPasswordValid("p\u00e4ss word~")).toBe(true);
  });
});

test("the default redirect URI is the callback page beside the setup page", () => {
  expect(defaultRedirectUri("https://danieltyukov.github.io/owltunes/setup/?owl=OwlTunes-1A2B")).toBe(
    "https://danieltyukov.github.io/owltunes/callback/",
  );
  expect(defaultRedirectUri("https://someone.github.io/owl-fork/setup/")).toBe(
    "https://someone.github.io/owl-fork/callback/",
  );
});
