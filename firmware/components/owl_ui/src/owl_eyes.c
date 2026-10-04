#include "owl_ui_internal.h"

#define EYE_SOCKET 170
#define EYE_IRIS 124
#define EYE_PUPIL 58
#define EYE_GLINT 16
#define EYE_SPACING 190
#define GAZE_RANGE 22
#define MAX_EYES 4

typedef struct {
    lv_obj_t *pupil[2];
    lv_obj_t *lid[2];
} owl_eyes_t;

static owl_eyes_t s_eyes[MAX_EYES];
static int s_eyes_used;

lv_obj_t *owl_eyes_create(lv_obj_t *parent)
{
    LV_ASSERT(s_eyes_used < MAX_EYES);
    owl_eyes_t *e = &s_eyes[s_eyes_used++];
    lv_obj_t *root = lv_obj_create(parent);
    lv_obj_remove_style_all(root);
    lv_obj_set_size(root, EYE_SPACING + EYE_SOCKET, EYE_SOCKET + 40);
    lv_obj_set_scrollable(root, false);
    lv_obj_set_clickable(root, false);

    for (int i = 0; i < 2; i++) {
        int32_t x = i == 0 ? -EYE_SPACING / 2 : EYE_SPACING / 2;
        lv_obj_t *socket = owl_ui_box(root, EYE_SOCKET, EYE_SOCKET, OWL_COLOR_BARK, LV_RADIUS_CIRCLE);
        lv_obj_set_style_clip_corner(socket, true, 0);
        lv_obj_align(socket, LV_ALIGN_TOP_MID, x, 0);
        lv_obj_t *iris = owl_ui_box(socket, EYE_IRIS, EYE_IRIS, OWL_COLOR_AMBER, LV_RADIUS_CIRCLE);
        lv_obj_center(iris);
        lv_obj_t *pupil = owl_ui_box(socket, EYE_PUPIL, EYE_PUPIL, OWL_COLOR_BG, LV_RADIUS_CIRCLE);
        lv_obj_center(pupil);
        lv_obj_t *glint = owl_ui_box(pupil, EYE_GLINT, EYE_GLINT, OWL_COLOR_CREAM, LV_RADIUS_CIRCLE);
        lv_obj_align(glint, LV_ALIGN_TOP_LEFT, 10, 10);
        lv_obj_t *lid = owl_ui_box(socket, EYE_SOCKET, 0, OWL_COLOR_BG, 0);
        lv_obj_set_style_border_side(lid, LV_BORDER_SIDE_BOTTOM, 0);
        lv_obj_set_style_border_color(lid, OWL_COLOR_AMBER, 0);
        lv_obj_align(lid, LV_ALIGN_TOP_MID, 0, 0);
        e->pupil[i] = pupil;
        e->lid[i] = lid;
    }

    lv_obj_t *beak = owl_ui_box(root, 30, 30, OWL_COLOR_AMBER, 4);
    lv_obj_set_style_transform_pivot_x(beak, 15, 0);
    lv_obj_set_style_transform_pivot_y(beak, 15, 0);
    lv_obj_set_style_transform_rotation(beak, 450, 0);
    lv_obj_align(beak, LV_ALIGN_TOP_MID, 0, EYE_SOCKET - 8);

    lv_obj_set_user_data(root, e);
    owl_eyes_set(root, OWL_MOOD_AWAKE, 0, 0);
    return root;
}

void owl_eyes_set(lv_obj_t *eyes, owl_mood_t mood, int32_t gaze_x, int32_t gaze_y)
{
    /* Percentage of each eye covered by the lid, per mood. */
    static const uint8_t lid_percent[] = {
        [OWL_MOOD_AWAKE] = 0, [OWL_MOOD_DROWSY] = 45, [OWL_MOOD_SCANNING] = 12,
        [OWL_MOOD_SLEEPY] = 62, [OWL_MOOD_ASLEEP] = 100,
    };
    owl_eyes_t *e = lv_obj_get_user_data(eyes);
    if ((unsigned)mood > OWL_MOOD_ASLEEP) {
        mood = OWL_MOOD_AWAKE;
    }
    int32_t gx = LV_CLAMP(-100, gaze_x, 100) * GAZE_RANGE / 100;
    int32_t gy = LV_CLAMP(-100, gaze_y, 100) * GAZE_RANGE / 100;
    int32_t lid_h = EYE_SOCKET * lid_percent[mood] / 100;
    for (int i = 0; i < 2; i++) {
        if (lv_obj_get_x_aligned(e->pupil[i]) != gx || lv_obj_get_y_aligned(e->pupil[i]) != gy) {
            lv_obj_align(e->pupil[i], LV_ALIGN_CENTER, gx, gy);
        }
        if (lv_obj_get_style_height(e->lid[i], LV_PART_MAIN) != lid_h) {
            lv_obj_set_height(e->lid[i], lid_h);
            lv_obj_set_style_border_width(e->lid[i], lid_h > 0 ? 4 : 0, 0);
        }
    }
}
