# The developer console

The owl's USB console carries three kinds of lines on one serial port:

- the firmware's log, such as `I (1234) owltunes: OWL_BOOT_OK board=nano_esp32 name=OwlTunes-7DF8`,
- the setup protocol: lines that start with `@owl ` ([provisioning-protocol.md](provisioning-protocol.md)),
- developer commands: any other line the computer sends, such as `next` or `vol 40`.

The owl answers developer commands with JSON lines in the same `@owl ` framing that the setup
protocol uses for its events, so a script reads everything with one parser
(`tools/owl_serial.py`). The setup page ignores events it does not know.

To type commands by hand, run `tools/firmware.sh monitor <board>`, type a command and press
Enter. A line may end with a line feed, a carriage return or both, so the monitor's bare CR works.

## Commands

Commands are lowercase words.

| Command | What it does | Answer |
|---|---|---|
| `help` | Lists the commands | `help` |
| `info` | Describes the board and what it is doing | `info` |
| `status` | Prints the playback state the owl knows now | `player` |
| `auth` | Reports the Spotify access token the owl holds | `auth` |
| `auth refresh` | Gets a new access token from Spotify first | `auth` |
| `devices` | Lists the Spotify devices | `device` lines, then `devices` |
| `play`, `pause` | Resumes or pauses playback | `cmd` lines |
| `toggle` | Pauses while playing, plays otherwise | `cmd` lines |
| `next`, `prev` (or `previous`) | Skips forward or back | `cmd` lines |
| `vol 40`, `vol +5`, `vol -5` (or `volume`) | Sets or changes the volume, 0 to 100 | `cmd` lines |
| `like`, `unlike` | Saves the current track to Liked Songs, or removes it | `cmd` lines |
| `transfer 2`, `transfer <device id>` | Moves playback to a device: a number from the last `devices` answer, or the device's id (1 to 63 letters, digits, `_` or `-`) | `cmd` lines |

Commands for the Spotify runtime wait in a queue of eight on their way to it; when it is full they
are refused with `busy`.

Every command except `help` and `info` counts as activity. For five minutes after the last one the
owl asks Spotify for the playback state as often as it would with its screen on (every 4 s while
playing, every 15 s otherwise, and half a second after each command); after that it falls back to
the hot-standby rate: once near the end of each track, at most once a minute, and not at all while
paused (spec section 9.4).

## Lines

Each answer is `@owl ` followed by one compact JSON object and a newline, at most 1024 bytes.

### cmd

A playback command goes through these states:

| State | Meaning |
|---|---|
| `queued` | Accepted. Commands go to Spotify one at a time, in order. |
| `done` | Spotify accepted it. A `player` line with the confirmed state follows within about a second. |
| `failed` | Spotify refused it or could not be reached; `error` says why and `retry_s`, when present, says when to try again. Commands still waiting behind one that hit a rate limit, a quota lockout, a backoff or a missing access token fail with it. |
| `refused` | The owl did not send it; `error` says why. |

```text
@owl {"event":"cmd","state":"queued","cmd":"next"}
@owl {"event":"cmd","state":"done","cmd":"next"}
@owl {"event":"cmd","state":"refused","cmd":"volume","error":"volume_unsupported"}
```

`toggle` is reported as the `play` or `pause` it became, and `vol` as `volume`. Commands typed
while a request is under way wait, and all of them join the queue before the next request goes out.
Volume commands that are still waiting are merged into the newest one: three `vol +5` typed while
another request is under way go out as one request, while from idle the first goes out alone and
the two typed during it merge. A command undone by the next one (`play` right after `pause`, while
both still wait) leaves the queue without a `done`. The owl shows each command's effect before
Spotify confirms it, so a failed command is followed by a `player` line too, with the state
Spotify reports, once Spotify may be called again.

`{"event":"cmd","state":"refused","error":"unknown_cmd"}` (without `cmd`) means the line was not a
command.

| Error | State | Meaning |
|---|---|---|
| `unknown_cmd` | refused | Not a command. The owl does not repeat what it did not understand. |
| `bad_arg` | refused | The argument is missing, extra or not allowed. |
| `not_linked` | refused, failed | No Spotify login is saved. |
| `offline` | refused | Linked, but not online. |
| `busy` | refused | Too many commands are waiting. |
| `backoff` | refused, failed | The network or Spotify's servers failed; `retry_s` says when the owl tries again (2 s, then longer each time up to a minute). |
| `rate_limited` | refused, failed | Spotify asked the owl to slow down; `retry_s` says for how long. |
| `quota` | refused, failed | Spotify's quota for the app is used up (`QUOTA_EXCEEDED`). Nothing goes to the Web API until `retry_s` has passed. On the finished owl the Bluetooth media keys take over meanwhile; the dev board has none yet. |
| `no_active_device` | refused, failed | Nothing is playing anywhere. Start Spotify on a device, or use `transfer`. |
| `device_restricted` | refused | The device does not accept remote commands. |
| `volume_unsupported` | refused | The device does not allow volume changes (many phones). |
| `volume_unknown` | refused | `vol +n` before the owl knows the volume. |
| `no_track` | refused | `like` without a Spotify track playing. Episodes and local files cannot be liked here. |
| `no_such_device` | refused | `transfer n` without line `n` in the last `devices` answer. |
| `premium_required` | failed | The account is not Spotify Premium. |
| `forbidden`, `not_found`, `rejected` | failed | Spotify refused the request for another reason. |
| `auth` | failed | Spotify refused the access token twice, even after a refresh. |
| `server_error` | failed | Spotify had a server error. The owl backs off (`backoff`) before it sends anything else. |
| `network` | failed | No answer from Spotify (Wi-Fi, DNS or TLS), or no access token could be had. The owl backs off. |
| `logged_out` | failed | Spotify refused the saved login. Log in again on the setup page. |
| `login_changed` | failed | A new Spotify login replaced the one the command was typed for; it was not sent. |
| `storage` | failed | A new login from Spotify could not be written to flash yet. |
| `bad_request` | failed | The owl could not build the request (a bug: please report it). |

`devices` is refused with `backoff`, `rate_limited` or `quota` (and `retry_s`) like the playback
commands while Spotify may not be called.

### player

```text
@owl {"event":"player","status":"playing","kind":"track","title":"Night Flight","artist":"The Barn Owls","album":"Moonlit Barn","uri":"spotify:track:6rqhFgbbKwnb9MLmUQDhG6","progress_ms":44000,"duration_ms":215000,"liked":false,"device":"Kitchen speaker","device_id":"0d1841b0976bae2a3a310dd74c0f3df354899bc8","device_type":"Speaker","volume":64,"supports_volume":true,"restricted":false,"shuffle":false,"repeat":"off","context":"spotify:playlist:37i9dQZF1DXcBWIGoYBM5M","link":"api","wait_s":0}
```

The owl prints it when the playback state changes (not when only the position moves on), when it
learns whether the track is in Liked Songs, after each command it sent (with the state Spotify
reports then), and for `status`.

| Field | Meaning |
|---|---|
| `status` | `playing`, `paused`, `no_device` or `unknown` (before the first answer) |
| `kind` | `track`, `episode`, `ad` or `unknown` |
| `title`, `artist`, `album` | Shortened to 95 bytes, or 31, or left out, so the line always fits |
| `uri`, `progress_ms`, `duration_ms` | The item and where playback is now |
| `liked` | `true` or `false` once the owl has asked Spotify, `null` before |
| `device`, `device_id`, `device_type`, `volume`, `supports_volume`, `restricted` | The active device; `volume` is `null` when Spotify does not say |
| `shuffle`, `repeat` | `repeat` is `off`, `context` or `track` |
| `context` | The playlist, album or other context, when there is one |
| `link`, `wait_s` | `api`, or `ble` while a quota lockout lasts; seconds until the Web API may be called again |

### device and devices

`devices` answers with one line per device, then a summary:

```text
@owl {"event":"device","n":1,"id":"0d1841b0976bae2a3a310dd74c0f3df354899bc8","name":"Kitchen speaker","type":"Speaker","active":true,"restricted":false}
@owl {"event":"devices","state":"done","count":1}
```

`n` is the number for `transfer n`; the numbers last until the next `devices` answer, a logout or a
new login. A failed list is `{"event":"devices","state":"failed","error":"..."}` with one of the
`failed` errors above and `retry_s`, or `bad_response` (Spotify's answer could not be read) or
`no_memory`.

### api and auth

The Spotify runtime works while the owl is linked and online. It says so with
`{"event":"api","state":"ready"}`, and `{"event":"api","state":"stopped","error":"not_linked"}`
(or `"offline"`) when it stops; commands still waiting then fail with the same error. Until it
works, commands that need Spotify are refused with that error:
`{"event":"cmd","state":"refused","cmd":"next","error":"not_linked"}`.

While nothing may be sent to Spotify, the api line says why and for how long, and says `ready`
again once the wait is over and the owl holds an access token (so an outage does not flip it to
`ready` between failed refreshes; the LED stays on the same status):

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
writes a new refresh token from Spotify to flash before it uses the new access token. When the Web
API refuses a token (401), the owl gets a new one and sends the request once more.
`{"event":"auth","state":"failed","error":"network"}` says why there is no token:

| Error | Meaning |
|---|---|
| `backoff`, `rate_limited`, `quota` | No token request may go out yet; `retry_s` says when one may |
| `network` | Spotify could not be reached, or answered something unexpected; the owl tries again later |
| `storage` | Spotify sent a new login that could not be written to flash yet; the owl keeps trying the write and uses nothing before it works |
| `logged_out` | Spotify refused the saved login: log in again on the setup page |
| `not_linked` | No Spotify login is saved |

### info

```text
@owl {"event":"info","board":"nano_esp32","name":"OwlTunes-7DF8","fw":"v0.3.0","uptime_s":12,"reset":"usb","partition":"ota_0","flash_kb":16384,"psram_kb":8192,"psram_free_kb":8000,"heap_free_kb":210,"heap_min_kb":190,"status":"playing","led":"#003000","wifi":"online","ssid":"Home","rssi":-52,"ip":"192.168.1.23","linked":true,"utc":"2026-10-11T09:30:00Z"}
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

### time

`{"event":"time","state":"synced","utc":"2026-10-11T09:30:00Z"}` each time the clock is set from
NTP: soon after the network comes up, then about once an hour. TLS does not depend on the clock,
so the owl works on a network that blocks NTP; only the times in its lines stay empty.

### help

`{"event":"help","commands":"help, info, status, auth [refresh], devices, play, pause, toggle, next, prev, vol <0-100|+n|-n>, like, unlike, transfer <n|device id>"}`
