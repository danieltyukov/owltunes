#include <stdio.h>
#include <string.h>
#include <sys/stat.h>

#include "owl_ui.h"
#include "sim_display.h"
#include "sim_png.h"
#include "sim_scenarios.h"

#if OWL_SIM_SDL
int sim_run_sdl(const char *scenario);
#endif

static sim_world_t s_world;

static int render(const char *name, const char *out_png)
{
    const sim_scenario_t *scenario = sim_scenario_find(name);
    if (scenario == NULL) {
        fprintf(stderr, "unknown scenario: %s\n", name);
        return 2;
    }
    lv_display_t *disp = sim_display_create_headless();
    owl_ui_t *ui = owl_ui_create(disp);
    scenario->setup(&s_world);
    sim_clock_set_ms((uint32_t)s_world.now_ms);
    owl_ui_render(ui, &s_world.app, &s_world.player, &s_world.inputs, s_world.now_ms);
    if (!sim_png_write_screen(out_png)) {
        fprintf(stderr, "cannot write %s\n", out_png);
        return 2;
    }
    return 0;
}

static void png_path(char *dst, size_t cap, const char *dir, const char *name)
{
    snprintf(dst, cap, "%s/%s.png", dir, name);
}

/* Fails when the C scenario registry and the list CMake tests against disagree. */
static int verify_list(const char *expected)
{
    char built[2048] = "";
    for (size_t i = 0; i < sim_scenario_count(); i++) {
        if (i > 0) {
            strncat(built, ",", sizeof built - strlen(built) - 1);
        }
        strncat(built, sim_scenario_at(i)->name, sizeof built - strlen(built) - 1);
    }
    if (strcmp(built, expected) != 0) {
        fprintf(stderr, "scenario list mismatch\n  registry: %s\n  cmake:    %s\n", built, expected);
        return 1;
    }
    return 0;
}

int main(int argc, char **argv)
{
    char out[512], golden[512];
    if (argc == 2 && strcmp(argv[1], "list") == 0) {
        for (size_t i = 0; i < sim_scenario_count(); i++) {
            puts(sim_scenario_at(i)->name);
        }
        return 0;
    }
    if (argc == 3 && strcmp(argv[1], "verify-list") == 0) {
        return verify_list(argv[2]);
    }
    if (argc == 4 && strcmp(argv[1], "snapshot") == 0) {
        return render(argv[2], argv[3]);
    }
    if (argc == 4 && strcmp(argv[1], "update-golden") == 0) {
        png_path(golden, sizeof golden, argv[3], argv[2]);
        return render(argv[2], golden);
    }
    if (argc == 5 && strcmp(argv[1], "check") == 0) {
        mkdir(argv[4], 0755);
        png_path(out, sizeof out, argv[4], argv[2]);
        png_path(golden, sizeof golden, argv[3], argv[2]);
        int rc = render(argv[2], out);
        return rc != 0 ? rc : sim_png_compare(out, golden, 8, 0.002);
    }
#if OWL_SIM_SDL
    if (argc >= 2 && strcmp(argv[1], "sdl") == 0) {
        return sim_run_sdl(argc >= 3 ? argv[2] : "now_playing");
    }
#endif
    fprintf(stderr, "usage: owl_sim list | verify-list <a,b,c> | snapshot <scenario> <out.png> |\n"
                    "               check <scenario> <golden-dir> <out-dir> | update-golden <scenario> <golden-dir>\n");
    return 2;
}
