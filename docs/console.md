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
| `wifi`, `ssid`, `rssi`, `ip` | The network: `idle`, `joining`, `online` or `waiting` on Wi-Fi, `ethernet` or `down` in QEMU, `off` on a board without network support; the network's name, its signal in dBm, and the address |
| `linked` | A Spotify login is saved |
| `utc` | The time once the clock is set, else empty |

### help

`{"event":"help","commands":"help, info"}`
