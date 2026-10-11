import { expect, test } from "vitest";
import { describeError, describeEvent, describeNetworkFailure } from "../src/messages";

test("known error codes get a sentence", () => {
  expect(describeError("invalid_client")).toBe(
    "Spotify rejected the client ID. Check it on your Spotify app's page and save it again.",
  );
});

test("unknown codes are shown as they are", () => {
  expect(describeError("server_on_fire")).toBe("Something went wrong (server_on_fire).");
});

test("prototype keys are not treated as messages", () => {
  expect(describeError("constructor")).toBe("Something went wrong (constructor).");
  expect(describeError("__proto__")).toBe("Something went wrong (__proto__).");
  expect(describeEvent("failed", "toString")).toBe("Something went wrong (toString).");
});

test("every event error from the protocol has its own sentence", () => {
  for (const code of ["storage", "no_refresh_token", "no_memory", "unauthorized_client", "bad_request", "too_long"]) {
    expect(describeEvent("failed", code)).not.toContain("Something went wrong");
  }
  expect(describeEvent("failed", "http_503")).toContain("503");
});

test("an event without an error code still says something useful", () => {
  expect(describeEvent("failed", "")).not.toContain("()");
  expect(describeEvent("failed", undefined)).not.toContain("()");
});

test("a logged-out owl asks for a new login, not a redirect check", () => {
  expect(describeEvent("logged_out", "invalid_grant")).toBe(
    "Your Spotify login expired or was revoked. Log in again.",
  );
  expect(describeEvent("failed", "bad_request")).not.toBe(describeError("bad_request"));
});

test("a Wi-Fi failure names the network and what to check", () => {
  expect(describeNetworkFailure("Home", "wifi_wrong_password")).toBe(
    "The owl could not join Home: check the password, or move closer to the router. To change the password, remove the network and add it again.",
  );
  expect(describeNetworkFailure("Phone", "wifi_not_found")).toContain("2.4 GHz");
  expect(describeNetworkFailure("Home", "wifi_no_address")).toContain("no address");
});

test("an unknown Wi-Fi failure still names the network", () => {
  expect(describeNetworkFailure("Home", "wifi_failed")).toBe("The owl could not join Home (wifi_failed). It keeps trying.");
  expect(describeNetworkFailure("Home", undefined)).toContain("no reason given");
  expect(describeNetworkFailure("Home", "constructor")).toContain("(constructor)");
});
