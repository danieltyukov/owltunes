# The developer console

The owl's USB console carries three kinds of lines on one serial port:

- the firmware's log, such as `I (1234) owltunes: OWL_BOOT_OK board=nano_esp32 ...`,
- the setup protocol: lines that start with `@owl ` ([provisioning-protocol.md](provisioning-protocol.md)),
- developer commands: any other line the computer sends, such as `info`.

The owl answers developer commands with JSON lines in the same `@owl ` framing that the setup
protocol uses for its events, so a script reads everything with one parser. The setup page ignores
events it does not know.

To type commands by hand, run `tools/firmware.sh monitor <board>`, type a command and press
Enter. A line may end with a line feed, a carriage return or both, so the monitor's bare CR works.

## Commands

Commands are lowercase words.

| Command | What it does | Answer |
|---|---|---|
| `help` | Lists the commands | `help` |
| `info` | Describes the board and what it is doing | `info` |
| `status` | Reports the playback state the Spotify runtime knows | `player` |
| `auth` | Reports the Spotify access token the owl holds | `auth` |
| `auth refresh` | Gets a new access token from Spotify first | `auth` |
| `devices` | Lists the Spotify devices | Refused with `not_ready` in this version |
| `play`, `pause`, `toggle`, `next`, `prev`, `vol <0-100\|+n\|-n>`, `like`, `unlike`, `transfer <n\|device id>` | Playback commands, sent one at a time (a device id is 1 to 63 letters, digits, `_` or `-`; a longer one is `bad_arg`) | Refused with `not_ready` in this version, which holds the Spotify login but sends no playback requests yet |

Commands for the Spotify runtime wait in a queue of eight; when it is full they are refused with
`busy`.

## Lines

Each answer is `@owl ` followed by one compact JSON object and a newline, at most 1024 bytes.

### cmd

`{"event":"cmd","state":"refused","error":"unknown_cmd"}` means the line was not a command (the
owl does not repeat what it did not understand). `{"event":"cmd","state":"refused","cmd":"info","error":"bad_arg"}`
means a known command had a missing, extra or malformed argument.

### info

```text
@owl {"event":"info","board":"nano_esp32","name":"OwlTunes-7DF8","fw":"v0.3.0","uptime_s":12,"reset":"usb","partition":"ota_0","flash_kb":16384,"psram_kb":8192,"psram_free_kb":8000,"heap_free_kb":210,"heap_min_kb":190,"status":"needs_wifi","led":"#000040","wifi":"idle","ssid":"","rssi":0,"ip":"","linked":false,"utc":""}
```

| Field | Meaning |
|---|---|
| `board`, `name`, `fw` | The board, the owl's name and the firmware version |
| `uptime_s`, `reset` | Seconds since the start, and why the chip last restarted (`poweron`, `usb`, `software`, `panic`, `watchdog`, `brownout`, `pin`, `deepsleep` or `other`) |
| `partition` | The app slot that is running (`ota_0` or `ota_1`) |
| `flash_kb`, `psram_kb`, `psram_free_kb` | Flash size, PSRAM size (0 without PSRAM) and free PSRAM |
| `heap_free_kb`, `heap_min_kb` | Free internal RAM now, and at its lowest since the start |
| `status`, `led` | The owl's status (see the LED table in [the dev board guide](dev-board-nano-esp32.md)) and the LED colour while lit |
| `wifi`, `ssid`, `rssi`, `ip` | The network: `idle` (no network saved), `joining`, `online` or `waiting` (every saved network failed; the next round starts soon) on Wi-Fi, `ethernet` or `down` in QEMU; the network being joined or used, its signal in dBm while online, and the address |
| `linked` | A Spotify login is saved |
| `utc` | The time once the clock is set, else empty |

### help

`{"event":"help","commands":"help, info, status, auth [refresh], devices, play, pause, toggle, next, prev, vol <0-100|+n|-n>, like, unlike, transfer <n|device id>"}`

### time

`{"event":"time","state":"synced","utc":"2026-10-11T09:30:00Z"}` each time the clock is set from
NTP: soon after the network comes up, then about once an hour. TLS does not depend on the clock,
so the owl works on a network that blocks NTP; only the times in its lines stay empty.

### player

`status` answers with the playback state the runtime knows, and how it reaches Spotify:
`{"event":"player","status":"unknown","shuffle":false,"repeat":"off","link":"api","wait_s":0}`.
This version does not read the playback state yet, so `status` stays `unknown`. `link` is `api`,
or `ble` while a quota lockout lasts; `wait_s` is the number of seconds until Spotify may be called
again (0 when it may).

### api and auth

The Spotify runtime works while the owl is linked and online. It says so with
`{"event":"api","state":"ready"}`, and `{"event":"api","state":"stopped","error":"not_linked"}`
(or `"offline"`) when it stops. Until then commands that need Spotify are refused with the same
error: `{"event":"cmd","state":"refused","cmd":"next","error":"not_linked"}`.

While nothing may be sent to Spotify, the api line says why and for how long, and says `ready`
again once the wait is over:

| State | Meaning |
|---|---|
| `backoff` | The network or Spotify's servers failed; the wait grows from 2 s to 60 s |
| `rate_limited` | Spotify asked the owl to slow down; the wait is its `Retry-After` |
| `quota` | The app's quota is used up; Spotify's own wait, at least a minute |

For example `{"event":"api","state":"backoff","retry_s":4}`. The waits cover the token requests to
`accounts.spotify.com` as well as the Web API, and `info` and the LED show the same three statuses.

`auth` reports the access token the runtime holds: `{"event":"auth","state":"ok","expires_in_s":3412}`.
`auth refresh` asks Spotify for a new one first. The token itself never appears on the console. The
owl refreshes the token by itself a minute before it expires (Spotify's tokens last an hour), and
writes a new refresh token from Spotify to flash before it uses the new access token.
`{"event":"auth","state":"failed","error":"network"}` says why there is no token:

| Error | Meaning |
|---|---|
| `backoff`, `rate_limited`, `quota` | No token request may go out yet; `retry_s` says when one may |
| `network` | Spotify could not be reached, or answered something unexpected; the owl tries again later |
| `storage` | Spotify sent a new login that could not be written to flash yet; the owl keeps trying the write and uses nothing before it works |
| `logged_out` | Spotify refused the saved login: log in again on the setup page |
| `not_linked` | No Spotify login is saved |
