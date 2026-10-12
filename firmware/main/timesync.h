#pragma once

#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>

/* Wall-clock time from NTP (time.google.com, then pool.ntp.org), set each time the network comes up
 * and refreshed hourly. TLS does not depend on it: ESP-IDF does not check certificate dates by
 * default, so a network that blocks NTP costs the owl its clock but never Spotify. */
void timesync_start(void);

/* The network came up: ask for the time now instead of waiting for the next retry. Any task. */
void timesync_network_up(void);

/* True once the clock has been set since boot. Any task. */
bool timesync_done(void);

/* Wait up to timeout_ms for the first sync. True when the clock is set. */
bool timesync_wait(uint32_t timeout_ms);

/* "2026-10-11T09:30:00Z" (21 bytes with the terminator); false before the first sync. */
bool timesync_utc(char *out, size_t cap);
