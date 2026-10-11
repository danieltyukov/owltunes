// The setup page: connect to the owl, save Wi-Fi and the Spotify client ID, and relay the login code.

import { $ } from "./dom";
import { CHANNEL, type Handoff } from "./callback";
import { describeError, describeEvent, describeNetworkFailure } from "./messages";
import { OwlClient, OwlError, type OwlEvent, type OwlReply, type Transport } from "./protocol";
import { openSerial, serialSupported } from "./serial";
import { clientIdValid, defaultRedirectUri, normalizeClientId, redirectUriValid, ssidValid, wifiPasswordValid } from "./validate";

const redirectUri = defaultRedirectUri(location.href);
let client: OwlClient | null = null;
let pendingState: string | null = null; /* the state of the login this page started */
let codeSent = false; /* the code of that login has gone to the owl */

const REDIRECT_INVALID_HINT =
  "The owl cannot use this page's address as a redirect URI. Open the page at http://127.0.0.1 instead of localhost, or from the https site.";
const REDIRECT_MISMATCH_HINT =
  "The owl's client ID was saved with a different setup page. Press Save client ID on this page so the login returns here.";

function status(text: string): void {
  $("status").textContent = text;
}

function fail(err: unknown): void {
  status(err instanceof OwlError ? describeError(err.code) : `Something went wrong: ${String(err)}`);
}

function owl(): OwlClient {
  if (client === null) {
    throw new OwlError("disconnected", "page");
  }
  return client;
}

function networkText(ip: unknown): string {
  return typeof ip === "string" && ip !== "" ? `Online at ${ip}.` : "Not on Wi-Fi yet.";
}

function renderNetworks(ssids: string[]): void {
  $("wifi-list").replaceChildren(
    ...ssids.map((ssid) => {
      const item = document.createElement("li");
      item.textContent = ssid;
      const remove = document.createElement("button");
      remove.type = "button";
      remove.textContent = "Remove";
      remove.addEventListener("click", () => void removeNetwork(ssid));
      item.append(remove);
      return item;
    }),
  );
}

/** Why Log in must stay off even though the owl holds a client ID, or null when it can go ahead. */
function loginBlocker(hello: OwlReply): string | null {
  if (!redirectUriValid(redirectUri)) {
    return REDIRECT_INVALID_HINT;
  }
  const clientId = typeof hello.client_id === "string" ? hello.client_id : "";
  if (clientId !== "" && hello.redirect_uri !== redirectUri) {
    return REDIRECT_MISMATCH_HINT;
  }
  return null;
}

function showOwl(hello: OwlReply): void {
  $("owl-name").textContent = String(hello.name ?? "");
  $("owl-fw").textContent = String(hello.fw ?? "");
  $("owl-network").textContent = networkText(hello.ip);
  renderNetworks(Array.isArray(hello.networks) ? hello.networks.map(String) : []);
  const clientId = typeof hello.client_id === "string" ? hello.client_id : "";
  if (clientId !== "") {
    $<HTMLInputElement>("client-id").value = clientId;
  }
  $<HTMLButtonElement>("login-button").disabled = clientId === "" || loginBlocker(hello) !== null;
  for (const id of ["owl", "wifi", "spotify-app", "login"]) {
    $(id).hidden = false;
  }
}

async function refresh(): Promise<OwlReply> {
  const hello = await owl().request("hello");
  showOwl(hello);
  return hello;
}

/** The owl may still be booting right after the port opens, so the first hello gets a few tries. */
async function firstHello(): Promise<OwlReply> {
  for (let attempt = 1; ; attempt++) {
    try {
      return await refresh();
    } catch (err) {
      if (!(err instanceof OwlError && err.code === "timeout") || attempt === 3) {
        throw err;
      }
    }
  }
}

function onEvent(event: OwlEvent): void {
  if (event.event === "network" && event.state === "failed") {
    // Failures queue behind the newest up/down state, so this says nothing about the current network.
    status(describeNetworkFailure(typeof event.ssid === "string" ? event.ssid : "", typeof event.error === "string" ? event.error : undefined));
  } else if (event.event === "network") {
    $("owl-network").textContent = networkText(event.state === "up" ? event.ip : "");
  } else if (event.event === "spotify") {
    if (event.state === "linking") {
      status("Your owl is linking to Spotify...");
    } else if (event.state === "linked") {
      if (codeSent) {
        pendingState = null;
        codeSent = false;
      }
      status("Linked. Your owl is ready: start Spotify on your phone or computer and press play.");
    } else if (event.state === "failed" || event.state === "logged_out") {
      pendingState = null;
      codeSent = false;
      status(describeEvent(event.state, typeof event.error === "string" ? event.error : undefined));
    }
  }
}

async function connect(): Promise<void> {
  // One owner per port: let go of an earlier connection before opening another.
  const previous = client;
  client = null;
  previous?.close();
  let next: OwlClient | null = null;
  let opened: Transport | null = null;
  try {
    const transport = await openSerial(
      (chunk) => next?.receive(chunk),
      () => {
        next?.close();
        if (client === next) {
          client = null;
          status(describeError("disconnected"));
        }
      },
    );
    next = new OwlClient(transport);
    opened = transport;
    next.onEvent(onEvent);
    client = next;
    status("Connected.");
    const hello = await firstHello();
    status(
      loginBlocker(hello) ??
        (hello.linked === true ? "This owl is already linked to Spotify. Log in again to switch accounts." : ""),
    );
  } catch (err) {
    // A failed connect must not leave the port open, or choosing it again would be refused.
    next?.close();
    if (client === next) {
      client = null;
    }
    await opened?.close().catch(() => undefined);
    if (err instanceof DOMException && err.name === "NotFoundError") {
      status("No port chosen. Press Connect over USB and pick the owl.");
    } else {
      fail(err);
    }
  }
}

async function addNetwork(event: SubmitEvent): Promise<void> {
  event.preventDefault();
  const ssid = $<HTMLInputElement>("wifi-ssid").value;
  const password = $<HTMLInputElement>("wifi-password").value;
  if (!ssidValid(ssid)) {
    status(describeError("bad_ssid"));
    return;
  }
  if (!wifiPasswordValid(password)) {
    status(describeError("bad_password"));
    return;
  }
  try {
    await owl().request("wifi_add", { ssid, password });
    $<HTMLInputElement>("wifi-password").value = "";
    status(`Saved ${ssid}.`);
    await refresh();
  } catch (err) {
    fail(err);
  }
}

async function removeNetwork(ssid: string): Promise<void> {
  try {
    await owl().request("wifi_remove", { ssid });
    status(`Removed ${ssid}.`);
    await refresh();
  } catch (err) {
    fail(err);
  }
}

async function saveClient(event: SubmitEvent): Promise<void> {
  event.preventDefault();
  const clientId = normalizeClientId($<HTMLInputElement>("client-id").value);
  if (!clientIdValid(clientId)) {
    status(describeError("bad_client_id"));
    return;
  }
  try {
    await owl().request("spotify_client", { client_id: clientId, redirect_uri: redirectUri });
    status("Client ID saved. Now log in.");
    await refresh();
  } catch (err) {
    fail(err);
  }
}

async function logIn(): Promise<void> {
  // Open the tab inside the click so popup blockers allow it, then point it at Spotify.
  const tab = window.open("", "_blank");
  try {
    const reply = await owl().request("spotify_begin");
    const url = new URL(String(reply.authorize_url));
    if (url.origin !== "https://accounts.spotify.com") {
      throw new OwlError("bad_authorize_url", "spotify_begin");
    }
    pendingState = url.searchParams.get("state");
    codeSent = false;
    if (tab === null) {
      status("Your browser blocked the Spotify tab. Allow pop-ups for this page and press Log in again.");
      return;
    }
    tab.opener = null;
    tab.location.href = url.href;
    status("Log in to Spotify in the new tab.");
  } catch (err) {
    tab?.close();
    fail(err);
  }
}

/** The callback tab sends the code here; the owl's verdict goes back so that tab can tell the person. */
async function onHandoff(message: Handoff, channel: BroadcastChannel): Promise<void> {
  if (message.type !== "code" || client === null || pendingState === null || message.state !== pendingState) {
    return;
  }
  try {
    await client.request("spotify_code", { code: message.code, state: message.state });
    codeSent = true;
    channel.postMessage({ type: "ack", state: message.state, ok: true } satisfies Handoff);
    status("Spotify login received. Your owl is linking...");
  } catch (err) {
    const code = err instanceof OwlError ? err.code : "unknown";
    channel.postMessage({ type: "ack", state: message.state, ok: false, error: code } satisfies Handoff);
    fail(err);
  }
}

function start(): void {
  $("redirect-uri").textContent = redirectUri;
  if (!redirectUriValid(redirectUri)) {
    status(REDIRECT_INVALID_HINT);
  }
  $("copy-redirect").addEventListener("click", () => void navigator.clipboard.writeText(redirectUri));
  if (!serialSupported()) {
    $<HTMLButtonElement>("connect-button").disabled = true;
    $("connect-help").hidden = false;
  }
  $("connect-button").addEventListener("click", () => void connect());
  $<HTMLFormElement>("wifi-form").addEventListener("submit", (e) => void addNetwork(e));
  $<HTMLFormElement>("client-form").addEventListener("submit", (e) => void saveClient(e));
  $("login-button").addEventListener("click", () => void logIn());
  const channel = new BroadcastChannel(CHANNEL);
  channel.addEventListener("message", (e: MessageEvent<Handoff>) => void onHandoff(e.data, channel));
  window.addEventListener("pagehide", () => {
    client?.close();
    client = null;
  });
}

start();
