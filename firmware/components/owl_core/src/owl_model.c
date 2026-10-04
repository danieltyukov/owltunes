#include "owl_model.h"

#include <string.h>

#include "owl_text.h"

void owl_player_init(owl_player_t *p)
{
    memset(p, 0, sizeof *p);
    p->status = OWL_PLAYER_UNKNOWN;
    p->repeat = OWL_REPEAT_OFF;
    p->device.volume_percent = -1;
}

uint32_t owl_player_progress_now(const owl_player_t *p, int64_t now_ms)
{
    if (!p->has_track) {
        return 0;
    }
    int64_t pos = p->progress_ms;
    if (p->status == OWL_PLAYER_PLAYING && now_ms > p->progress_at_ms) {
        pos += now_ms - p->progress_at_ms;
    }
    if (p->track.duration_ms > 0 && pos > p->track.duration_ms) {
        pos = p->track.duration_ms;
    }
    return (uint32_t)pos;
}

uint32_t owl_player_remaining_ms(const owl_player_t *p, int64_t now_ms)
{
    if (!p->has_track || p->track.duration_ms == 0) {
        return 0;
    }
    return p->track.duration_ms - owl_player_progress_now(p, now_ms);
}

void owl_list_page_init(owl_list_page_t *page, owl_list_kind_t kind, const char *source_uri)
{
    memset(page, 0, sizeof *page);
    page->kind = kind;
    owl_utf8_copy(page->source_uri, sizeof page->source_uri, source_uri);
}
