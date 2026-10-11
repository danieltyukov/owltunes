import { expect, type Page, test } from "@playwright/test";
import { type FakeOwlOptions, type FakeOwlState, installFakeOwl } from "./fake-owl";

const CLIENT_ID = "0123456789abcdef0123456789abcdef";
const NONCE = "QEFCQ0RFRkdISUpLTE1OTw";

async function openSetup(page: Page, options: Partial<FakeOwlOptions> = {}): Promise<void> {
  const owl: FakeOwlOptions = { exchange: "linked", ip: "192.168.1.23", ...options };
  await page.addInitScript(installFakeOwl, owl);
  // Stand in for Spotify: send the browser straight back to the redirect URI with a code.
  await page.context().route("https://accounts.spotify.com/authorize**", async (route) => {
    const url = new URL(route.request().url());
    const back = new URL(url.searchParams.get("redirect_uri") ?? "");
    back.search = new URLSearchParams({ code: "AQDtest-code", state: url.searchParams.get("state") ?? "" }).toString();
    await route.fulfill({ status: 302, headers: { location: back.href } });
  });
  await page.goto("setup/");
  await page.getByRole("button", { name: "Connect over USB" }).click();
  await expect(page.getByText("OwlTunes-1A2B")).toBeVisible();
}

async function owlState(page: Page): Promise<FakeOwlState> {
  return page.evaluate(() => (window as unknown as { __owl: FakeOwlState }).__owl);
}

async function prepareLogin(page: Page): Promise<void> {
  await page.getByLabel("Network name").fill("Home");
  await page.getByLabel("Password").fill("password1");
  await page.getByRole("button", { name: "Save network" }).click();
  await expect(page.getByRole("listitem").filter({ hasText: "Home" })).toBeVisible();
  await expect(page.getByText("Online at 192.168.1.23.")).toBeVisible();
  await page.getByLabel("Client ID").fill(` ${CLIENT_ID.toUpperCase()} `);
  await page.getByRole("button", { name: "Save client ID" }).click();
  await expect(page.getByRole("status")).toHaveText("Client ID saved. Now log in.");
}

test("setup links an owl end to end", async ({ page }) => {
  await openSetup(page);
  await expect(page.locator("#redirect-uri")).toHaveText("http://127.0.0.1:4173/owltunes/callback/");
  await prepareLogin(page);
  const [spotifyTab] = await Promise.all([
    page.context().waitForEvent("page"),
    page.getByRole("button", { name: "Log in with Spotify" }).click(),
  ]);
  await expect(spotifyTab.getByRole("status")).toHaveText(
    "Sent to your owl. You can close this tab and watch the owl's screen.",
  );
  expect(spotifyTab.url()).not.toContain("code=");
  await expect(page.getByRole("status")).toHaveText(
    "Linked. Your owl is ready: start Spotify on your phone or computer and press play.",
  );
  const owl = await owlState(page);
  expect(owl.codes).toEqual(["AQDtest-code"]);
  expect(owl.clientId).toBe(CLIENT_ID);
  expect(owl.redirectUri).toBe("http://127.0.0.1:4173/owltunes/callback/");
});

test("setup explains a client ID that Spotify rejects", async ({ page }) => {
  await openSetup(page, { exchange: "failed" });
  await prepareLogin(page);
  const [spotifyTab] = await Promise.all([
    page.context().waitForEvent("page"),
    page.getByRole("button", { name: "Log in with Spotify" }).click(),
  ]);
  await expect(spotifyTab.getByRole("status")).toContainText("Sent to your owl");
  await expect(page.getByRole("status")).toHaveText(
    "Spotify rejected the client ID. Check it on your Spotify app's page and save it again.",
  );
});

test("setup explains a failure the owl reports without a message", async ({ page }) => {
  await openSetup(page, { exchange: "failed", failError: "" });
  await prepareLogin(page);
  await Promise.all([
    page.context().waitForEvent("page"),
    page.getByRole("button", { name: "Log in with Spotify" }).click(),
  ]);
  await expect(page.getByRole("status")).toHaveText(
    "Spotify did not give a reason. Wait a moment and log in again.",
  );
});

test("setup explains a login that could not be saved", async ({ page }) => {
  await openSetup(page, { exchange: "failed", failError: "storage" });
  await prepareLogin(page);
  await Promise.all([
    page.context().waitForEvent("page"),
    page.getByRole("button", { name: "Log in with Spotify" }).click(),
  ]);
  await expect(page.getByRole("status")).toHaveText(
    "The owl could not save the login to its memory. Try again, and update the firmware if it keeps happening.",
  );
});

test("setup keeps Log in off when the owl holds another site's redirect address", async ({ page }) => {
  await openSetup(page, { savedClientId: CLIENT_ID, savedRedirectUri: "https://example.github.io/owltunes/callback/" });
  await expect(page.getByRole("status")).toContainText("saved with a different setup page");
  await expect(page.getByRole("button", { name: "Log in with Spotify" })).toBeDisabled();
  await page.getByRole("button", { name: "Save client ID" }).click();
  await expect(page.getByRole("status")).toHaveText("Client ID saved. Now log in.");
  await expect(page.getByRole("button", { name: "Log in with Spotify" })).toBeEnabled();
});

test("a stray linked event does not cancel a login in progress", async ({ page }) => {
  await openSetup(page);
  await prepareLogin(page);
  let release: () => void = () => undefined;
  const held = new Promise<void>((resolve) => (release = resolve));
  // Hold Spotify's answer back (this route wins over the one openSetup added).
  await page.context().route("https://accounts.spotify.com/authorize**", async (route) => {
    await held;
    const url = new URL(route.request().url());
    const back = new URL(url.searchParams.get("redirect_uri") ?? "");
    back.search = new URLSearchParams({ code: "AQDtest-code", state: url.searchParams.get("state") ?? "" }).toString();
    await route.fulfill({ status: 302, headers: { location: back.href } });
  });
  const [spotifyTab] = await Promise.all([
    page.context().waitForEvent("page"),
    page.getByRole("button", { name: "Log in with Spotify" }).click(),
  ]);
  await page.evaluate(() => (window as unknown as { __owlEmit: (e: Record<string, unknown>) => void }).__owlEmit({ event: "spotify", state: "linked" }));
  release();
  await expect(spotifyTab.getByRole("status")).toHaveText(
    "Sent to your owl. You can close this tab and watch the owl's screen.",
  );
  expect((await owlState(page)).codes).toEqual(["AQDtest-code"]);
});

test("setup explains a Wi-Fi network the owl could not join", async ({ page }) => {
  await openSetup(page);
  await page.evaluate(() => {
    const emit = (window as unknown as { __owlEmit: (e: Record<string, unknown>) => void }).__owlEmit;
    emit({ event: "player", status: "playing", title: "Night Flight", link: "api" }); // console lines are ignored
    emit({ event: "network", state: "failed", ssid: "Home", error: "wifi_wrong_password" });
  });
  await expect(page.getByRole("status")).toHaveText(
    "The owl could not join Home: check the password, or move closer to the router. To change the password, remove the network and add it again.",
  );
  await expect(page.getByText("Not on Wi-Fi yet.")).toBeVisible();
});

test("a late Wi-Fi failure does not undo the network the owl is on", async ({ page }) => {
  await openSetup(page);
  await page.evaluate(() => {
    const emit = (window as unknown as { __owlEmit: (e: Record<string, unknown>) => void }).__owlEmit;
    emit({ event: "network", state: "up", ip: "192.168.1.20" });
    emit({ event: "network", state: "failed", ssid: "Old", error: "wifi_not_found" });
  });
  await expect(page.getByText("192.168.1.20")).toBeVisible();
  await expect(page.getByText("Not on Wi-Fi yet.")).toBeHidden();
});

test("setup checks input before the owl sees it", async ({ page }) => {
  await openSetup(page);
  await page.getByLabel("Network name").fill("Home");
  await page.getByLabel("Password").fill("short");
  await page.getByRole("button", { name: "Save network" }).click();
  await expect(page.getByRole("status")).toHaveText(
    "Wi-Fi passwords are 8 to 64 characters, without tabs or line breaks. Leave it empty for an open network.",
  );
  await page.getByLabel("Client ID").fill("not-a-client-id");
  await page.getByRole("button", { name: "Save client ID" }).click();
  await expect(page.getByRole("status")).toContainText("That is not a client ID.");
  expect((await owlState(page)).networks).toEqual([]);
});

test("setup tells browsers without Web Serial what to do", async ({ page }) => {
  await page.addInitScript(() => {
    Object.defineProperty(Navigator.prototype, "serial", { configurable: true, get: () => undefined });
  });
  await page.goto("setup/");
  await expect(page.getByRole("button", { name: "Connect over USB" })).toBeDisabled();
  await expect(page.getByText("This browser cannot talk to USB devices.")).toBeVisible();
});

test("callback page offers fallbacks without a setup tab", async ({ page }) => {
  const state = `${NONCE}.192.168.1.23`;
  await page.goto(`callback/?code=AQDtest-code&state=${state}`);
  await expect(page.getByRole("status")).toHaveText(
    "No setup page answered. Send the login to your owl another way:",
  );
  await expect(page.getByRole("link", { name: "Send to my owl over Wi-Fi" })).toHaveAttribute(
    "href",
    `http://192.168.1.23/callback?code=AQDtest-code&state=${state}`,
  );
  await expect(page.locator("#console-line")).toHaveValue(
    `@owl {"id":1,"cmd":"spotify_code","code":"AQDtest-code","state":"${state}"}`,
  );
  expect(page.url()).not.toContain("code=");
});

test("callback page never offers a public address", async ({ page }) => {
  await page.goto(`callback/?code=AQDtest-code&state=${NONCE}.8.8.8.8`);
  await expect(page.locator("#console-line")).toBeVisible();
  await expect(page.getByRole("link", { name: "Send to my owl over Wi-Fi" })).toBeHidden();
});

test("callback page reports a cancelled login", async ({ page }) => {
  await page.goto(`callback/?error=access_denied&state=${NONCE}`);
  await expect(page.getByRole("status")).toHaveText(
    "The Spotify login was cancelled. Start again from the setup page.",
  );
  await expect(page.locator("#fallback")).toBeHidden();
});

test("a connect that times out can be retried on the same port", async ({ page }) => {
  test.setTimeout(60_000);
  const owl: FakeOwlOptions = { exchange: "linked", ip: "192.168.1.23", silent: true };
  await page.addInitScript(installFakeOwl, owl);
  await page.goto("setup/");
  await page.getByRole("button", { name: "Connect over USB" }).click();
  await expect(page.getByRole("status")).toHaveText(
    "The owl did not answer. Check the cable and connect again.",
    { timeout: 25_000 },
  );
  await page.evaluate(() => {
    (window as unknown as { __owl: FakeOwlState }).__owl.silent = false;
  });
  await page.getByRole("button", { name: "Connect over USB" }).click();
  await expect(page.getByText("OwlTunes-1A2B")).toBeVisible();
  expect((await owlState(page)).opens).toBe(2);
});
