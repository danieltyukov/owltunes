# OwlTunes setup protocol

The setup page and the owl talk in short JSON lines. The same lines travel over the USB console
now and are meant to travel over Bluetooth later, so the console can also be used by hand.

## Framing

- One message per line: the prefix `@owl ` (with its space), compact JSON, then a newline. A
  line also ends at a carriage return, so CR LF and a bare CR work too.
- A line is at most 1024 bytes, prefix and newline included. Longer lines are dropped whole.
- Lines the owl prints without the prefix are the firmware's log; the setup page skips them. Lines
  the computer sends without the prefix are not ignored: the owl treats them as developer
  commands ([console.md](console.md)) and answers with `@owl` events this page does not list, which
  the setup page ignores. Before the developer console existed, the owl dropped such lines.
- Requests carry a number `id` that the reply repeats. Events have no `id`.

```text
@owl {"id":1,"cmd":"hello"}
@owl {"id":1,"ok":true,"name":"OwlTunes-1A2B","fw":"0.2.0","protocol":1,"setup":"needs_spotify","linked":false,"client_id":"","redirect_uri":"","ip":"10.0.2.15","networks":["Home"]}
```

## Replies

Success is `{"id":N,"ok":true, ...}` with the fields below. Failure is
`{"id":N,"ok":false,"error":"<code>"}`. A line the owl cannot parse is answered with id 0 and
`bad_request`.

## Commands

| Command | Parameters | Reply fields | Errors |
|---|---|---|---|
| `hello` | none | `name`, `fw`, `protocol` (1), `setup` (`needs_wifi`, `needs_spotify` or `ready`), `linked`, `client_id`, `redirect_uri`, `ip` (empty when offline), `networks` (saved SSIDs) | |
| `wifi_add` | `ssid` (1 to 32 bytes), `password` (empty for an open network, else 8 to 64 bytes); neither may contain control characters (bytes below 0x20, and 0x7f) | none | `bad_ssid`, `bad_password`, `full` (four networks saved) |
| `wifi_remove` | `ssid` | none | `not_found` |
| `spotify_client` | `client_id` (32 lowercase hex characters), `redirect_uri` (`https://...` or `http://127.0.0.1:<port>...`, under 160 characters) | none | `bad_client_id`, `bad_redirect_uri` |
| `spotify_begin` | none | `authorize_url` | `offline`, `no_client_id`, `too_long` |
| `spotify_code` | `code`, `state` | `accepted` (true) | `no_session`, `expired`, `bad_state`, `bad_code`, `busy` |
| `spotify_logout` | none | none | |

Any command can also fail with `bad_request` (not a JSON object, or no `cmd`), `unknown_cmd`, or
`too_long` (the reply would not fit in one line).

Saving a different client ID or redirect URI forgets the saved login, because Spotify ties a
refresh token to both.

## Events

| Event | States | Fields |
|---|---|---|
| `network` | `up`, `down`, `failed` (joining a saved Wi-Fi network did not work; the owl goes on to the next saved network and keeps trying) | `ip` when up; `ssid` and `error` when failed |
| `spotify` | `linking` (exchanging a code), `linked` (the login is saved in flash, after a code exchange or after the saved login passed its check at boot), `failed` (the login did not complete), `logged_out` (Spotify refused the saved login) | `error` for `failed` and `logged_out` |

An event looks like `@owl {"event":"spotify","state":"failed","error":"invalid_grant"}`.

The owl writes a new login to flash before it reports `linked`. If the write fails, it reports
`failed` with `error` `storage` instead and tries the write again later.

## Error codes

Errors in a reply (`"ok":false`):

| Code | Meaning |
|---|---|
| `bad_request` | The line is not a JSON object, or has no `cmd`. |
| `unknown_cmd` | The `cmd` is not one of the commands above. |
| `too_long` | The reply, or the authorize URL for `spotify_begin`, would not fit in one line. |
| `bad_ssid`, `bad_password`, `full`, `not_found` | Wi-Fi network checks, see the table above. |
| `bad_client_id`, `bad_redirect_uri` | Client ID or redirect URI checks, see the table above. |
| `offline` | `spotify_begin` while the owl is not online. The login could not finish without a network. It also means the owl makes the PKCE verifier only while its Wi-Fi is enabled, which ESP-IDF documents as the condition for true random numbers from the chip's generator (the radio may still sleep between beacons, and the emulator uses the host's generator). A login that is already open stays open. |
| `no_client_id` | `spotify_begin` before a client ID and redirect URI were saved. |
| `no_session` | `spotify_code` without an open login. |
| `expired` | The login was opened more than 10 minutes ago. |
| `bad_state` | The `state` does not match the open login. |
| `bad_code` | The code is empty, longer than 511 characters, or has characters outside `A-Z a-z 0-9 - . _ ~`. |
| `busy` | The owl is already exchanging a code. |

The `error` of a `spotify` event:

| Code | Event | Meaning |
|---|---|---|
| Spotify's own code (`invalid_client`, `invalid_grant`, ...) | `failed`, `logged_out` | What the token endpoint answered. |
| `http_<status>` (for example `http_503`) | `failed`, `logged_out` | Spotify answered with that HTTP status and no error code of its own, such as a server error or a request to slow down. |
| `network` | `failed` | The owl could not reach Spotify. |
| `no_memory` | `failed` | The owl had no memory for the request. |
| `too_long` | `failed` | Spotify's answer was larger than the owl can read. |
| `bad_request` | `failed` | The owl could not build the token request. |
| `no_refresh_token` | `failed` | Spotify accepted the code but sent no refresh token, so there is nothing to save. |
| `storage` | `failed` | The login worked but could not be written to flash. |

The `error` of a `network` event:

| Code | Meaning |
|---|---|
| `wifi_not_found` | The network is not in range, uses 5 GHz only, or uses security the owl does not support. |
| `wifi_wrong_password` | The network refused the password. |
| `wifi_no_address` | The owl joined but got no address within 20 seconds. |
| `wifi_failed` | Any other reason. |

## The Spotify login

1. The page sends `spotify_client` with the person's client ID and, as the redirect URI, the
   address of the callback page next to it.
2. `spotify_begin`, sent while the owl is online, makes the owl create a PKCE verifier (64 random
   bytes), its S256 challenge and a `state`: 16 random bytes in base64url, then `.` and the owl's
   IPv4 address. The reply is the full authorize URL. The login stays open for 10 minutes; a new
   `spotify_begin` replaces it.
3. Spotify sends the browser to the redirect URI with `code` and `state`. The code reaches the owl
   by one of three routes, all ending in the same check:
   - the callback page posts `{"type":"code","code":...,"state":...}` on
     `BroadcastChannel("owltunes-auth")`; the setup tab that started this login sends
     `spotify_code` and posts back `{"type":"ack","state":...,"ok":true}`, or `"ok":false` with
     `"error"`;
   - `GET http://<owl-ip>/callback?code=...&state=...`, which the owl serves on port 80 only while a
     login is open and the owl is online. The callback page offers it only when the state ends
     in a private address (10/8, 172.16/12, 192.168/16 or 169.254/16). The reply page never
     repeats anything from the request;
   - the line `@owl {"id":1,"cmd":"spotify_code","code":"...","state":"..."}` pasted into the USB
     console.
4. The owl accepts a code only for an open, unexpired login whose state matches exactly (compared
   in constant time), and only when the code is 1 to 511 URL-safe characters
   (`A-Z a-z 0-9 - . _ ~`). It exchanges the code at `https://accounts.spotify.com/api/token`
   itself, saves the refresh token to flash, and then reports `spotify` `linked`, or `failed`
   when the exchange or the save did not work. The verifier, access token and refresh token never
   leave the owl.
5. At every start with a saved login, once the owl is online, it refreshes the login once. A new
   refresh token from Spotify replaces the saved one. `invalid_grant`, `invalid_client` and
   `unauthorized_client` forget the saved login and the owl asks to log in again. If Spotify
   cannot be reached or answers with a server error, the owl keeps the login and checks again
   after 5 minutes.

## Versions

`hello` reports `protocol`. It goes up when a command changes in a way an older page cannot
handle.
