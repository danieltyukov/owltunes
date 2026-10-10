# Setting up your owl

**Status:** the setup page and the owl's side of it work today over USB and in the QEMU emulator.
Setup over Bluetooth and joining the saved Wi-Fi networks arrive with the dev-kit firmware.

You need the owl (or the emulator, see the end), a computer with Chrome or Edge and a USB cable,
Spotify Premium, and a free Spotify developer account, which is your normal Spotify login.

## 1. Connect

Open the [setup page](https://danieltyukov.github.io/owltunes/setup/) on the computer, or scan
the QR code on the owl's screen. Plug the owl in, press **Connect over USB** and choose the owl's
port. The page shows the owl's name, which matches the one under the QR code.

## 2. Wi-Fi

Add your home network. To use the owl away from home, add your phone's hotspot as well. The owl
keeps up to four networks.

## 3. Your Spotify app

OwlTunes uses your own Spotify app, so your owl does not depend on anyone else's quota.

1. Open the [Spotify developer dashboard](https://developer.spotify.com/dashboard) and log in.
2. Press **Create app**. Any name and description will do, for example "My OwlTunes".
3. Under **Redirect URIs**, add the address the setup page shows
   (`https://danieltyukov.github.io/owltunes/callback/` on the official site). It must match
   exactly, including the slash at the end.
4. Under the question about APIs and SDKs, tick **Web API**. Accept the terms and save.
5. Open the app's settings and copy the **Client ID** (32 letters and digits). You never need the
   client secret.
6. Paste the client ID into the setup page and press **Save client ID**.

If Spotify later says the app is not available for your account, open the app's **User
Management** page and add the email address of your Spotify account.

## 4. Log in

Press **Log in with Spotify**. Spotify opens in a new tab: check the permissions and agree. That
tab hands the login to the setup page, the setup page passes it to the owl, and the owl finishes
the login with Spotify by itself. The setup page then says "Linked" and the owl leaves its setup
screen.

If the setup page was closed, the Spotify tab offers two other ways:

- **Send to my owl over Wi-Fi** opens the owl's own address on your network. It works when the
  device you logged in on is on the same Wi-Fi as the owl.
- **Paste this line into the owl's USB console**, with any serial terminal at 115200 baud (for
  example `idf.py monitor`).

Finish the login within 10 minutes of pressing **Log in with Spotify**.

## Logging in again

Spotify ends a saved login after six months, or when you remove the app's access in your Spotify
account settings. The owl notices at its next start, shows "Log in again" with the QR code, and
you repeat step 4.

## Privacy

The setup page is a static site with no server and no analytics. It never sees your Spotify
tokens: the owl exchanges the one-time code itself and keeps the tokens in its own flash. Your
Wi-Fi passwords travel from the page to the owl over the USB cable only.

If you build your own firmware and want the saved tokens and Wi-Fi passwords encrypted at rest,
turn on ESP-IDF's flash encryption and secure boot. Both are optional and off by default, because
a mistake while enabling them can lock a board.

## Trying it without hardware

With ESP-IDF v6.1 activated, build the firmware with `tools/firmware.sh build`, then run
`tools/qemu_prov_test.py --link --client-id <your client ID>`. It starts the real firmware in the
QEMU emulator and links it to your account:

- With the default redirect URI, the script prints Spotify's login address. Log in, then paste the
  address your browser ends up on.
- If you add `http://127.0.0.1:18080/callback` as a second redirect URI in your Spotify app and
  pass `--redirect-uri http://127.0.0.1:18080/callback`, Spotify sends the code straight to the
  emulated owl.

The script then restarts the emulator and checks that the saved login still works.
