#pragma once

#include <stddef.h>
#include <stdint.h>

#include "owl_prov.h"
#include "spotify_auth.h"

/* Exchange a login code for tokens at Spotify's token endpoint. Blocks for up to 15 seconds.
 * error receives Spotify's error code, "network" when Spotify could not be reached, or "". */
spotify_token_result_t spotify_link_exchange(const owl_settings_t *s, const char *code, const char *verifier,
                                             int64_t now_ms, spotify_token_t *token, char *error,
                                             size_t error_cap);

/* Refresh the saved login. token->refresh_token must hold it; Spotify may send a new one. */
spotify_token_result_t spotify_link_refresh(const owl_settings_t *s, int64_t now_ms, spotify_token_t *token,
                                            char *error, size_t error_cap);
