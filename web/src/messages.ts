// What the owl's error codes mean for the person at the keyboard.

const MESSAGES: Record<string, string> = {
  bad_request: "The owl did not understand the page. Reload this page and connect again.",
  unknown_cmd: "The owl's firmware is older than this page. Update the firmware, then try again.",
  too_long: "That value is too long for the owl.",
  bad_ssid: "The network name must be 1 to 32 characters.",
  bad_password: "Wi-Fi passwords are 8 to 64 characters. Leave it empty for an open network.",
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
};

export function describeError(code: string): string {
  return MESSAGES[code] ?? `Something went wrong (${code}).`;
}
