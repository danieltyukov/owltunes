// The page Spotify redirects to. It hands the code to the setup tab, or offers the fallbacks.

import { $ } from "./dom";
import { CHANNEL, codeValid, consoleLine, type Handoff, lanCallbackUrl, readCallback, stateValid } from "./callback";
import { describeError } from "./messages";

const ACK_TIMEOUT_MS = 2000;

function say(text: string): void {
  $("message").textContent = text;
}

function showFallbacks(code: string, state: string): void {
  say("No setup page answered. Send the login to your owl another way:");
  const lan = lanCallbackUrl(state, code);
  if (lan !== null) {
    $<HTMLAnchorElement>("lan-link").href = lan;
    $("lan").hidden = false;
  }
  $<HTMLTextAreaElement>("console-line").value = consoleLine(code, state);
  $("fallback").hidden = false;
}

function start(): void {
  const { code, state, error } = readCallback(location.search);
  // The code works once, but it still has no business in the history or a shared screenshot.
  history.replaceState(null, "", location.pathname);
  $("copy-line").addEventListener(
    "click",
    () => void navigator.clipboard.writeText($<HTMLTextAreaElement>("console-line").value),
  );
  if (error !== null) {
    say(
      error === "access_denied"
        ? "The Spotify login was cancelled. Start again from the setup page."
        : "Spotify could not log you in. Start again from the setup page.",
    );
    return;
  }
  if (code === null || state === null || !codeValid(code) || !stateValid(state)) {
    say("This address does not carry a usable login. Start again from the setup page.");
    return;
  }
  const channel = new BroadcastChannel(CHANNEL);
  const timer = setTimeout(() => showFallbacks(code, state), ACK_TIMEOUT_MS);
  channel.addEventListener("message", (event: MessageEvent<Handoff>) => {
    const message = event.data;
    if (message.type !== "ack" || message.state !== state) {
      return;
    }
    clearTimeout(timer);
    channel.close();
    $("fallback").hidden = true;
    say(
      message.ok
        ? "Sent to your owl. You can close this tab and watch the owl's screen."
        : `${describeError(message.error ?? "unknown")} Start again from the setup page.`,
    );
  });
  channel.postMessage({ type: "code", code, state } satisfies Handoff);
}

start();
