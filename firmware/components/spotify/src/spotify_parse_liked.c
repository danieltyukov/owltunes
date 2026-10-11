#include "spotify_json.h"
#include "spotify_parse.h"

spotify_parse_result_t spotify_parse_liked(const char *json, size_t len, bool *liked)
{
    if (json == NULL || len == 0) {
        return SPOTIFY_PARSE_BAD_SHAPE;
    }
    cJSON *root = cJSON_ParseWithLength(json, len);
    if (root == NULL) {
        return SPOTIFY_PARSE_BAD_JSON;
    }
    const cJSON *first = cJSON_IsArray(root) ? cJSON_GetArrayItem(root, 0) : NULL;
    spotify_parse_result_t result = SPOTIFY_PARSE_BAD_SHAPE;
    if (cJSON_IsBool(first)) {
        *liked = cJSON_IsTrue(first);
        result = SPOTIFY_PARSE_OK;
    }
    cJSON_Delete(root);
    return result;
}
