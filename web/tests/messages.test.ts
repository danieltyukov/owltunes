import { expect, test } from "vitest";
import { describeError } from "../src/messages";

test("known error codes get a sentence", () => {
  expect(describeError("invalid_client")).toBe(
    "Spotify rejected the client ID. Check it on your Spotify app's page and save it again.",
  );
});

test("unknown codes are shown as they are", () => {
  expect(describeError("server_on_fire")).toBe("Something went wrong (server_on_fire).");
});
