# Security policy

## Reporting a vulnerability

Please report security problems privately through GitHub's
[private vulnerability reporting](https://github.com/danieltyukov/owltunes/security/advisories/new)
rather than in a public issue. You will get a reply within a week.

## What OwlTunes stores

- Your Spotify refresh token, in the device's non-volatile storage.
- Your Wi-Fi network names and passwords, in the same storage.

OwlTunes never needs a Spotify client secret. Builders who want stronger protection can enable
ESP32-S3 flash encryption and secure boot; see the ESP-IDF security guide.
