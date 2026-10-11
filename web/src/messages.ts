// What the owl's error codes mean for the person at the keyboard.

/** Errors in the reply to a request. */
const MESSAGES = new Map<string, string>(Object.entries({
  bad_request: "The owl did not understand the page. Reload this page and connect again.",
  unknown_cmd: "The owl's firmware is older than this page. Update the firmware, then try again.",
  too_long: "That value is too long for the owl.",
  bad_ssid: "The network name must be 1 to 32 characters, without tabs or line breaks.",
  bad_password: "Wi-Fi passwords are 8 to 64 characters, without tabs or line breaks. Leave it empty for an open network.",
  full: "The owl keeps four networks. Remove one first.",
  not_found: "The owl does not know that network.",
  bad_client_id: "That is not a client ID. It is the 32 letters and digits on your Spotify app's page.",
  bad_redirect_uri: "The redirect URI must start with https://.",
  no_client_id: "Save your client ID first.",
  no_session: "That login is no longer open. Press Log in with Spotify again.",
  expired: "That login took more than 10 minutes. Press Log in with Spotify again.",
  bad_state: "That login belongs to an earlier attempt. Press Log in with Spotify again.",
  bad_code: "Spotify sent a login code the owl cannot use. Try again.",
  busy: "The owl is still linking. Wait a moment.",
  timeout: "The owl did not answer. Check the cable and connect again.",
  disconnected: "The owl was disconnected. Connect again.",
  invalid_client: "Spotify rejected the client ID. Check it on your Spotify app's page and save it again.",
  invalid_grant: "Spotify refused the login. Check the redirect URI on your Spotify app's page, then log in again.",
  network: "The owl could not reach Spotify. Check its Wi-Fi, then log in again.",
}));

/** Errors in a spotify event, which concern the login itself rather than the last request. */
const EVENT_MESSAGES = new Map<string, string>(Object.entries({
  invalid_client: MESSAGES.get("invalid_client") ?? "",
  invalid_grant: "Spotify refused the login. Check the redirect URI on your Spotify app's page, then log in again.",
  unauthorized_client: "Spotify does not allow this app to log in. Check the app on your Spotify developer dashboard.",
  network: MESSAGES.get("network") ?? "",
  no_memory: "The owl ran out of memory. Restart the owl and log in again.",
  too_long: "Spotify's answer was larger than the owl can read. Try again.",
  bad_request: "The owl could not build the login request. Check the client ID and redirect URI, then try again.",
  no_refresh_token: "Spotify did not give the owl a lasting login. Log in again.",
  storage: "The owl could not save the login to its memory. Try again, and update the firmware if it keeps happening.",
}));

/** Why the owl could not join a saved Wi-Fi network: the error of a network event in state failed. */
const WIFI_MESSAGES = new Map<string, (ssid: string) => string>(Object.entries({
  // The owl also reports a wrong password when the signal is too weak to finish the handshake.
  wifi_wrong_password: (ssid: string) =>
    `The owl could not join ${ssid}: check the password, or move closer to the router. To change the password, remove the network and add it again.`,
  wifi_not_found: (ssid: string) =>
    `The owl cannot find ${ssid}. Check the name, and that the network is in range and uses 2.4 GHz.`,
  wifi_no_address: (ssid: string) =>
    `The owl got no address from ${ssid} in time. Check that the router is working; the owl keeps trying.`,
}));

/** The sentence for a network event in state failed; the owl keeps trying the next saved network. */
export function describeNetworkFailure(ssid: string, error: string | undefined): string {
  const known = error === undefined ? undefined : WIFI_MESSAGES.get(error);
  if (known !== undefined) {
    return known(ssid);
  }
  return `The owl could not join ${ssid} (${error ?? "no reason given"}). It keeps trying.`;
}

export function describeError(code: string): string {
  return MESSAGES.get(code) ?? `Something went wrong (${code}).`;
}

/** The sentence for a failed or logged_out spotify event; `error` may be missing or empty. */
export function describeEvent(state: string, error: string | undefined): string {
  if (state === "logged_out") {
    return "Your Spotify login expired or was revoked. Log in again.";
  }
  const known = error === undefined ? undefined : EVENT_MESSAGES.get(error);
  if (known !== undefined) {
    return known;
  }
  const status = /^http_(\d{3})$/.exec(error ?? "");
  if (status !== null) {
    return `Spotify answered with an error (${status[1]}). Wait a moment and log in again.`;
  }
  if (error === undefined || error === "") {
    return "Spotify did not give a reason. Wait a moment and log in again.";
  }
  return `Something went wrong (${error}).`;
}
