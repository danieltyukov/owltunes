# OwlTunes system design

Status: approved design, 2026-10-04
Scope: the whole product (device, desk perch, firmware, setup page, enclosure, companion app roadmap)

## 1. Summary

OwlTunes is an owl-shaped remote control for Spotify. It does not play audio. Music keeps
playing on your phone, computer or speakers, and OwlTunes lets you control it without taking
your phone out: skip, pause, change volume, like a track, browse your playlists and library,
search, manage the queue and move playback between devices.

The product has two parts:

- **The owl**: a battery-powered handheld (about 66 x 84 x 22 mm, about 110 g) with a round
  1.75 inch AMOLED touch display set inside a rotating ring that forms the owl's facial disc,
  two ear-tuft buttons on top and a beak button below the screen.
- **The perch**: a weighted desk dock shaped like a branch. The owl snaps onto it with magnets,
  charges through spring contacts and switches to an always-on desk mode. The perch holds the
  owl firmly enough that turning the ring or tapping the screen does not move it.

The design takes Spotify's Car Thing (2022, discontinued and remotely disabled in December 2024)
as its reference and aims to improve on it in every area that users and reviewers criticised.

## 2. Goals and non-goals

### Goals

1. Control Spotify from a pocket or a desk with the same reach as the phone app for playback
   control and library browsing, within what Spotify's public Web API allows.
2. Work as a carry-around device (battery, wake on pickup, blind physical controls) and as a
   stationary desk device (perch, always-on screen, firm footing).
3. Reach the Spotify app without the phone in hand, at home (Wi-Fi) and away (phone hotspot in
   v1, Bluetooth companion bridge in v2), with a basic offline fallback that always works.
4. Be fully open source: firmware, software, PCB and enclosure, buildable by one person from
   ordered parts with no soldering.
5. Reach demo and pitch quality: industrial design, renders, documentation and a demo video good
   enough to present to Spotify.

### Non-goals

- Playing audio or acting as a Spotify Connect speaker.
- Voice control. Spotify's Developer Policy prohibits voice-control integrations.
- Selling assembled units. Spotify's Developer Terms do not allow commercial use of an
  integration that controls playback; a commercial product would need Spotify's written
  approval, which is the purpose of the pitch.
- iPhone-specific features in v1. The v1 design works with any phone, but the v2 companion
  bridge targets Android first.

## 3. Decisions and assumptions

| Topic | Decision |
|---|---|
| Primary user phone | Android |
| Spotify account | Premium (playback control through the Web API requires it) |
| Form factor | "Owl face": round display in a rotating ring, ear-tuft and beak buttons |
| Away-from-Wi-Fi strategy | Phased: v1 phone hotspot plus Bluetooth media keys, v2 Android companion bridge |
| Desk use | Weighted magnetic perch dock with spring-contact charging |
| Assembly | PCB fully assembled by JLCPCB; battery, display and haptic motor on connectors |
| Location for sourcing | The Netherlands; optimise for quality, then total cost, then delivery time |
| Licences | MIT for software, CERN-OHL-P-2.0 for hardware and enclosure |
| Private material | Purchasing BOM, order plans, quotes and local agent configuration are kept out of git |

## 4. What makes it better than Car Thing

| Car Thing (2022) | OwlTunes |
|---|---|
| No battery, USB-powered in a car mount | Battery owl for the pocket, perch dock for the desk |
| Needed the Spotify phone app as its only backend, over Bluetooth | Talks to Spotify directly over Wi-Fi and can control any Spotify Connect device |
| Useless without a connection | Bluetooth and USB media keys work with no internet at all |
| Mount wobbled when the knob was pressed | Ring rotates without pressing; weighted magnetic perch |
| Fixed mechanical knob | Smooth ring with programmable haptic detents and end-of-list bumps |
| Four preset buttons that reviewers found hard to hit | Preset wheel: hold an ear, turn the ring, release |
| LCD, laggy UI reported by reviewers | AMOLED with true black, LVGL UI targeted at 50-60 fps with partial updates |
| No device switching | Pick any Spotify Connect device as the output |
| Closed, remotely disabled | Open source, local control, over-the-air updates from public releases |

## 5. Platform constraints (Spotify, as of 2026-10-04)

These constraints were verified against Spotify's developer documentation and blog and shape
the design throughout.

1. **Development Mode only.** Spotify's Extended Quota is available only to registered
   organisations with at least 250k monthly active users. Every OwlTunes user creates their own
   free Development Mode app (client ID). Since February 2026 a Development Mode app allows at
   most 5 authorised users, the owner must have Premium, and some endpoints are unavailable.
2. **Player endpoints are available and Premium-only**: playback state, play, pause, next,
   previous, seek, volume, shuffle, repeat, devices, transfer and queue (get and add). Commands
   must be sent one at a time because Spotify does not guarantee their order of execution.
3. **Library limits for new apps**: playlist items can only be read for playlists the user owns
   or collaborates on; search returns at most 10 results per page; recommendations, related
   artists, audio features and Spotify-owned editorial or algorithmic playlists are unavailable.
   Followed playlists can still be listed and played as a whole by context URI.
4. **Phones are fragile playback targets.** An idle phone app drops off the device list and the
   Web API cannot wake it. Phones often report `supports_volume: false`.
5. **OAuth**: redirect URIs must be HTTPS except loopback addresses. Authorization Code with PKCE
   works without a client secret. Access tokens last 1 hour; refresh tokens expire 6 months after
   the original authorisation and may rotate on every refresh.
6. **Rate limits**: a rolling 30-second limit plus a per-developer quota, neither published.
   A public report shows polling every 3 seconds around the clock exhausting the quota within a
   day, followed by a lockout of about 5 hours. A `429` with `QUOTA_EXCEEDED` must never be
   retried before `Retry-After`.
7. **No push events** are available to third parties. Spotify's internal websocket is off limits.
8. **Branding**: the name must not contain "Spotify" or start with "Spot"; album art must not be
   cropped or overlaid with controls; metadata and art must be shown with the Spotify logo or
   icon (at least 70 px); artwork corner radius 4 px on small and medium screens.
9. **Terms grey area**: Spotify's terms describe approved devices as desktops, laptops, tablets,
   phones and devices Spotify approves in writing. A microcontroller remote is not on that list.
   The project is a personal, non-commercial, user-built integration; the README says so and
   states that OwlTunes is not affiliated with Spotify.

## 6. System architecture

```
                         +------------------------- the owl --------------------------+
                         |                                                             |
   Spotify Web API  <----+-- Wi-Fi (home network or phone hotspot) --- ESP32-S3        |
   (HTTPS)               |                                              |   |   |      |
                         |   Phone / computer  <-- BLE HID media keys --+   |   |      |
                         |   Computer          <-- USB HID + console ------+   |      |
                         |   Setup page        <-- BLE GATT (provisioning) ---+      |
                         |                                                             |
                         |   AMOLED + touch, ring sensor, buttons, haptics, IMU, ALS,  |
                         |   charger, fuel gauge, battery                              |
                         +----------------------------+--------------------------------+
                                                      | spring contacts + magnets
                                              +-------+--------+
                                              |   the perch    |  USB-C power in
                                              +----------------+

   v2: Android companion app  <-- BLE -->  owl     (app relays Web API calls and pushes
                                                    player state using the phone's internet)
```

### 6.1 Control paths

1. **Wi-Fi to the Spotify Web API (primary).** Full features: now playing with art, library,
   search, queue, devices, like, presets. Works at home and through a phone hotspot.
2. **Bluetooth LE HID consumer control (always on, paired once with the phone).** Play/pause,
   next, previous, volume up and down. Works with no internet. Also used for volume whenever the
   active Spotify device is the paired phone and the Web API reports `supports_volume: false`.
3. **USB HID consumer control** when the owl is plugged into a computer.
4. **v2: Android companion bridge over BLE.** The phone app proxies Web API requests, uses the
   Spotify app SDK to wake Spotify and push state changes, so no polling and no hotspot are needed.

The firmware picks the richest available path per command and shows the active path as a small
status glyph.

## 7. Industrial design

### 7.1 The owl

- **Overall**: about 66 mm wide, 84 mm tall, 22 mm deep, about 110 g. Rounded owl silhouette
  with a flat back so it stands upright on its own.
- **Face**: 1.75 inch round AMOLED (466 x 466) under a protective window, surrounded by a
  rotating ring about 8 mm wide that reads as the owl's facial disc.
- **Ear tufts**: two buttons on the top edge, reachable through pocket fabric.
- **Beak**: one button centred below the screen.
- **Feathers**: relief texture on the belly and back. Minimum feature size 0.5 mm for MJF prints;
  finer detail only on an optional SLA shell.
- **Back**: three gold-plated contact pads (VBUS, GND, DOCK_DET), two magnets and two alignment
  recesses for the perch.
- **Window for the ambient light sensor**: a small aperture in the brow.
- **Antenna**: the ESP32-S3 module's PCB antenna sits at the top of the head between the ear
  tufts with a 15 mm keep-out from metal and from the ring mechanism.

### 7.2 The ring mechanism

The ring is smooth (no mechanical detents). Feel comes from the haptic motor (section 8.3).
Two variants are printed in the first test round and chosen by feel and measured wobble:

1. a thin-section ball bearing (6710 class); a steel bearing is kept only if the Wi-Fi RSSI test
   in section 15 passes, otherwise a plastic or ceramic bearing is used, and
2. a printed bushing with damping grease and an O-ring for camera-lens-style drag.

The ring carries 24-32 small alternating-polarity magnets read by a 3D Hall sensor on the PCB.
If neither variant feels right, the fallback is an internal gear driving an EC11 encoder, which
needs a PCB change and is therefore decided before PCB rev A is ordered.

### 7.3 The perch

- Branch-shaped cradle on a weighted base: a steel insert of about 200 g and a silicone
  non-slip pad.
- Three spring-loaded pogo pins meet the owl's pads; magnets pull the owl into a seat with a
  15-20 degree viewing tilt. The seat geometry resists the torque of turning the ring.
- USB-C power input on the back of the perch.
- Dock magnets are placed as far as possible from the ring sensor; the firmware recalibrates the
  ring sensor's static offset whenever docking is detected.

### 7.4 Materials and finish

- Body, ring and perch: MJF PA12 dyed black (tough, takes snap fits and heat-set inserts).
- Optional premium shell: SLA tough resin or vapour-smoothed MJF.
- Screws: M2 into heat-set inserts in MJF parts only.

## 8. Electronics

### 8.1 Main board (4-layer, JLCPCB assembled)

| Block | Part | Notes |
|---|---|---|
| MCU | ESP32-S3-WROOM-1-N16R8 | 16 MB flash, 8 MB octal PSRAM, Wi-Fi 4, BLE 5, native USB |
| Low-power clock | 32.768 kHz crystal | Cuts BLE light-sleep current from about 3.3 mA to about 0.23 mA |
| Display | 1.75 inch round AMOLED, 466 x 466, CO5300 over QSPI, CST9217 touch, 31-pin FPC | Same panel family as the Waveshare ESP32-S3-Touch-AMOLED-1.75 dev kit; pinout taken from the purchased panel's datasheet |
| Display power | Load switch (TPS22917 or SY6280A) | Full power-off in sleep |
| Ring sensing | TMAG5273A2 3D Hall sensor, magnets in the ring | Wake-on-rotation at about 1 uA |
| Haptics | DRV2605L + 8 mm coin LRA on a 2-pin connector | Detents, bumps, confirmations |
| Charger | BQ24073 with power path | Runs from USB or the perch while charging |
| Regulator | TPS63802 buck-boost to 3.3 V | Uses the battery down to 3.0 V |
| Fuel gauge | MAX17048 | No sense resistor |
| Battery | 1S LiPo about 1000 mAh (803040) with protection circuit and 10k NTC, JST-PH | Bought with leads fitted; polarity checked before plugging in |
| IMU | LIS2DW12 | Wake on pickup, sleep on set-down, pocket detection |
| Ambient light | I2C ambient light sensor | Auto brightness |
| USB | USB-C receptacle, USBLC6-2SC6 ESD, 5.1k CC resistors | Flashing, console, HID |
| Dock input | Three contact pads; VBUS combined with USB VBUS through Schottky diodes | DOCK_DET to a GPIO |
| Buttons | Two side-actuated tact switches (ear tufts), one top-actuated (beak) | Plus BOOT and RESET pads for recovery |

Parts are chosen from JLCPCB's library where possible. Stock and Basic or Extended status are
checked again at order time. Alternates are listed for low-stock parts (DRV2605L, BQ24074).

### 8.2 Perch board (2-layer)

USB-C receptacle, ESD protection, three pogo pins, a resistor that identifies the dock on
DOCK_DET, and mounting holes for the perch body.

### 8.3 Power budget (estimates, to be measured on the dev kits)

| State | Current | 1000 mAh battery |
|---|---|---|
| Screen on, Wi-Fi active | about 110-180 mA | about 6 h |
| Screen off, Wi-Fi associated (hot standby) | about 3 mA | about 12 days |
| Wi-Fi off, BLE advertising | about 0.5-1 mA | 5-10 weeks |
| Deep sleep, display powered off | about 30 uA | over a year |
| Typical day: 1 h use, deep sleep otherwise | | about 6 days |

Policy: after use the owl stays in hot standby for a few minutes so the next interaction is
instant, then enters deep sleep. Waking from deep sleep takes 1-3 s before the first Spotify
call; BLE media keys respond immediately. On the perch the owl is always powered.

## 9. Firmware

### 9.1 Platform

- ESP-IDF v6.1, written in C, CMake components.
- LVGL 9 for the UI, with partial rendering and an even-aligned rounder for the CO5300.
- FreeRTOS tasks: UI on core 1; networking and Spotify on core 0; input and haptics at high
  priority; power management.

### 9.2 Components

| Component | Responsibility | Depends on |
|---|---|---|
| `owl_core` | App state store, event bus, state machine. Pure C, compiled and tested on the host | nothing hardware-specific |
| `spotify` | HTTPS client, endpoint wrappers, JSON parsing, token refresh, command queue, poll scheduler | `owl_core`, esp_http_client, cJSON |
| `owl_ui` | LVGL screens and widgets; compiled for the device and for the desktop simulator | `owl_core`, LVGL |
| `owl_input` | Ring decoding, buttons, touch gestures, input locking | BSP |
| `owl_haptics` | DRV2605L driver and named haptic patterns | BSP |
| `owl_power` | Sleep policy, fuel gauge, charger status, IMU wake, display power | BSP |
| `owl_net` | Multi-network Wi-Fi, provisioning, time sync, OTA with rollback | ESP-IDF |
| `owl_ble` | BLE HID consumer control and the provisioning GATT service | NimBLE |
| `owl_usb` | TinyUSB composite: CDC console and HID consumer control | TinyUSB |
| `owl_store` | NVS settings, tokens, album-art cache on LittleFS | ESP-IDF |
| BSPs | `bsp_waveshare_amoled175`, `bsp_waveshare_knob18`, `bsp_owltunes_reva` | selected by Kconfig |

### 9.3 Data flow

Input events (ring, buttons, touch, IMU) go onto the event bus. The state machine turns them into
UI state changes and Spotify commands. Commands go into a single serial queue: they are applied
optimistically to the UI, sent one at a time, and reconciled with the next playback-state poll.
Repeated volume changes are coalesced so only the latest value is sent. Responses update the state
store, and UI screens observe the store.

### 9.4 Poll scheduler

| Situation | Polling |
|---|---|
| Screen on, playing | every 4 s, progress interpolated locally in between |
| Screen on, paused or no active device | every 15 s |
| After any command | one poll 500 ms later |
| Predicted end of track | one poll, plus art prefetch for the next track from the queue |
| Hot standby, screen off | only at predicted track end, at most once per 60 s |
| Deep sleep | none |
| `429` | wait `Retry-After`; `QUOTA_EXCEEDED` switches to BLE-only mode until it expires |

Expected load at one hour of active use per day is under 2,000 requests, more than ten times below
the level reported to trigger the quota lockout.

### 9.5 Album art

The owl requests Spotify's 300 px image, decodes the JPEG to RGB565 in PSRAM and displays it as an
uncropped rounded square (about 320 px, the largest square inside the 466 px circle) with the 4 px
corner radius Spotify specifies for small screens. The last 32 images are cached as JPEG files on LittleFS, keyed by URL hash.

### 9.6 Error handling

| Condition | Behaviour |
|---|---|
| No internet | BLE-only mode; status glyph; physical controls keep working |
| No active Spotify device | "Open Spotify on your phone" screen with an owl animation; when a device reappears, offer one-press transfer |
| Device refuses volume | Volume through BLE HID if the phone is paired, otherwise the ring seeks in 5 s steps |
| Refresh token expired (6 months) or revoked | Show a re-authorisation QR code; everything else keeps working |
| Refresh token rotated | Persist the new token atomically before it is used |
| TLS or certificate change | Full CA bundle (no pinning), OTA updates |
| Brownout or power loss | NVS writes are atomic; OTA keeps the previous image and rolls back on a failed boot |

### 9.7 Security

- No client secret anywhere: PKCE only.
- HTTPS to Spotify with the ESP-IDF certificate bundle.
- The local HTTP callback server runs only during an authorisation window (10 minutes) and accepts
  only a `state` value the device generated.
- The provisioning GATT service requires LE Secure Connections pairing confirmed by a button press
  on the owl.
- Refresh tokens live in NVS. Flash encryption and secure boot are documented as optional
  hardening for builders who want them.

## 10. Setup and account linking

1. **Firmware.** Flash from the browser with the web flasher (desktop Chrome or Edge over USB),
   or build with ESP-IDF.
2. **First boot.** The owl shows "Hoot! Set me up" with a QR code for the setup page and starts
   BLE provisioning.
3. **Setup page** (static, hosted on GitHub Pages, works in Chrome on Android and desktop):
   connects over Web Bluetooth, takes one or more Wi-Fi networks (home and phone hotspot) and the
   user's Spotify client ID. It walks the user through creating the Spotify app with the redirect
   URI `https://danieltyukov.github.io/owltunes/callback/`.
4. **Spotify login.** The owl generates the PKCE verifier and a `state` value and hands the
   authorize URL to the page. Spotify redirects to the GitHub Pages callback, which returns the
   one-time code to the owl:
   - primary: over Web Bluetooth (the user taps "Send to OwlTunes"),
   - fallback: a full-page navigation to `http://<owl-ip>/callback` on the local network,
   - last resort: pasting the code into the USB console.
   The owl exchanges the code for tokens itself.
5. **Bluetooth media keys.** The owl asks to pair as a media remote with the phone.
6. **Re-authorisation** every 6 months repeats step 4 from a QR code on the owl.

## 11. User experience

### 11.1 Controls

| Control | Action |
|---|---|
| Ring | Volume on Now Playing; scroll in lists (one haptic tick per item, bump at the ends) |
| Tap album art | Play or pause |
| Swipe left or right | Next or previous track |
| Swipe up | Library |
| Left ear, short | Previous track |
| Right ear, short | Next track |
| Left ear, hold | Preset wheel: turn the ring to choose one of 8 presets, release to play |
| Right ear, hold | Like or unlike the current track |
| Beak, short | Back |
| Beak, hold | Home (Now Playing) |
| Beak, double press | Play or pause without looking |
| Pick up | Wake |
| In pocket (screen off and the light sensor reads dark) | Ring locked; buttons stay active |

### 11.2 Screens

Now Playing (home), Library (Playlists, Liked Songs, Albums, Recently Played), Search (alphabet ring
around the screen edge with live results), Queue (view and add), Devices (choose output),
Presets (8 slots around the circle; long-press a slot to assign the current context), Settings
(Wi-Fi, account, haptic strength, brightness, sleep timer, about), and Desk Mode when docked
(dimmed now playing and clock, with pixel shifting).

Lists on the round screen use a centre-weighted layout with about five rows, a 28-32 px main font
and scaling towards the edges.

### 11.3 Owl personality

| State | Owl |
|---|---|
| Playing | Eyes open with a gentle idle motion |
| Paused | Eyes half closed |
| Looking for a device | Eyes scanning left and right |
| Offline | Sleepy |
| Low battery | Yawning |
| Docked at night | Asleep beside a dim clock |

Static elements move slightly over time to protect the AMOLED from burn-in.

### 11.4 Haptic vocabulary

Tick (list item), bump (end of list), confirm (action done), heartbeat (like), buzz (error),
preset click (each preset slot).

## 12. Repository and licensing

```
owltunes/
  README.md  LICENSE (MIT)  LICENSE-HARDWARE (CERN-OHL-P-2.0)  CONTRIBUTING.md  SECURITY.md
  docs/            design spec, architecture notes, build and assembly guides, Spotify setup guide
  firmware/        ESP-IDF project: main/, components/, boards/
  sim/             LVGL desktop simulator and headless screenshot tool
  web/             setup page and web flasher (GitHub Pages)
  hardware/        KiCad 10 projects: owl-mainboard/, perch-dock/, lib/ (symbols, footprints, 3D)
  enclosure/       build123d sources for the owl, ring and perch; exports go to build/
  companion/       v2 Android bridge app
  tools/           scripts for fab outputs and BOM generation (outputs go to private/)
  .github/         CI workflows
```

Kept out of git: `private/` (purchasing BOM, order plan, quotes, receipts), generated fabrication
outputs (published on GitHub Releases instead), local agent and MCP configuration (`.mcp.json`,
`.claude/`, `CLAUDE.md`), build outputs, and KiCad or FreeCAD backup files.

## 13. Testing strategy

| Layer | Tests |
|---|---|
| Core logic | Host unit tests (CTest) for the state machine, command queue, poll scheduler and gesture recogniser |
| Spotify client | Parser tests against recorded, anonymised API responses, including error and rate-limit cases |
| UI | Desktop simulator renders every screen to PNG; golden-image comparison in CI |
| Firmware | CI builds for every BSP; QEMU boot smoke test |
| Hardware bring-up | Scripted serial test menu on the dev kits and rev A: display, touch, ring, buttons, haptics, IMU, gauge, charger, Wi-Fi RSSI |
| Setup page | Unit tests for PKCE and state handling; browser end-to-end test against a mock Spotify |
| PCB | KiCad ERC and DRC in CI; design review before ordering |
| Enclosure | Scripted dimension checks, interference and clearance against the PCB STEP export, printability check |
| Power | USB power meter measurements on the dev kits and rev A against section 8.3 |

## 14. Delivery phases

| Phase | Content | Exit criteria |
|---|---|---|
| P0 | Repository, licences, docs skeleton, CI, private procurement sheet; order the two dev kits | Repo public and building; kits ordered |
| P1 | Firmware core, Spotify client, UI in the simulator, setup page; bring-up on the dev kits | Full control of Spotify from the Waveshare AMOLED kit; simulator screenshots in the README |
| P2 | Main board rev A, perch board, enclosure v1 and ring variants; one JLCPCB order with assembly and test prints | ERC/DRC clean, fit checks pass, order placed (target before about 1 November 2026 to avoid the new EU per-item fee) |
| P3 | Assembly, bring-up, measurements, fixes; premium final print | Owl and perch working together; battery figures measured |
| P4 | Android companion bridge, demo video, pitch materials | Hotspot no longer needed away from home; demo ready |

## 15. Risks

| Risk | Mitigation |
|---|---|
| Ring feels cheap or wobbles | Two variants in the first test print; gear plus EC11 fallback decided before PCB rev A |
| Antenna detuned by the ring or magnets | Antenna at the top with keep-out; RSSI test on the first prints; -1U module with external antenna as fallback |
| Dock magnets disturb the ring sensor | Physical separation; recalibration on dock detect |
| AMOLED burn-in | Pixel shifting, dimming and screen timeouts |
| Display FPC pinout differs between vendors | Buy the panel first; take the pinout from its datasheet; same panel family as the dev kit |
| Spotify changes the Web API or its policy again | Thin endpoint layer, OTA updates, BLE media keys as a permanent fallback |
| Quota lockout | Poll scheduler budget, `Retry-After` handling, BLE-only mode during a lockout |
| Low stock of specific ICs | Alternates listed; stock checked at order time |
| LRA with wire leads | Connector on the board and pre-wired motors |

## 16. References

- Spotify Web API Development Mode changes, February 2026: https://developer.spotify.com/blog/2026-02-06-update-on-developer-access-and-platform-security
- February 2026 migration guide: https://developer.spotify.com/documentation/web-api/tutorials/february-2026-migration-guide
- Refresh token expiration, June 2026: https://developer.spotify.com/blog/2026-06-18-refresh-token-expiration
- Redirect URI rules: https://developer.spotify.com/documentation/web-api/concepts/redirect_uri
- Rate limits: https://developer.spotify.com/documentation/web-api/concepts/rate-limits
- Spotify design guidelines: https://developer.spotify.com/documentation/design
- Developer Terms and Policy: https://developer.spotify.com/terms , https://developer.spotify.com/policy
- ESP32-S3 low-power Wi-Fi modes: https://docs.espressif.com/projects/esp-idf/en/stable/esp32s3/api-guides/low-power-mode/low-power-mode-wifi.html
- CO5300 driver component: https://components.espressif.com/components/espressif/esp_lcd_co5300
- TMAG5273: https://www.ti.com/product/TMAG5273
- Car Thing community reconstruction (reference only, not reused): https://github.com/ThingLabsOSS/superbird-webapp
