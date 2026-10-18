#pragma once

#include <stddef.h>
#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

/* CO5300 AMOLED controller over QSPI: the command encoding, the panel RAM window and the init tables
 * of the two panels the firmware drives. Pure logic, tested on the host. */

/* Both panels are 466 x 466. */
#define OWL_CO5300_RES 466

/* QSPI framing: a command goes out on one line as a 32-bit word (opcode, 0x00, command, 0x00), its
 * parameters follow on one line; pixel data follows a write-pixels word on all four lines. */
#define OWL_CO5300_OP_WRITE_CMD 0x02
#define OWL_CO5300_OP_WRITE_PIXELS 0x32

#define OWL_CO5300_CASET 0x2A  /* column address set */
#define OWL_CO5300_RASET 0x2B  /* row address set */
#define OWL_CO5300_RAMWR 0x2C  /* memory write */
#define OWL_CO5300_MADCTL 0x36 /* memory data access control */
#define OWL_CO5300_MADCTL_BGR 0x08

/* One init command: the command byte, up to four parameter bytes and the wait after it. */
typedef struct {
    uint8_t cmd;
    uint8_t len;
    uint8_t data[4];
    uint16_t delay_ms;
} owl_co5300_cmd_t;

/* The 32-bit word esp_lcd sends before a command's parameters or before pixel data. */
uint32_t owl_co5300_cmd_word(uint8_t opcode, uint8_t cmd);

/* CASET and RASET parameters for a frame area (inclusive corners). The panel's frame column 0 is RAM
 * column col_offset, so every window shifts by it; rows have no offset. */
typedef struct {
    uint8_t caset[4];
    uint8_t raset[4];
} owl_co5300_window_t;

void owl_co5300_window(int32_t x1, int32_t y1, int32_t x2, int32_t y2, int32_t col_offset,
                       owl_co5300_window_t *out);

/* Grow an area (inclusive corners) to start on an even column and row and end on an odd one. The
 * CO5300 on many panels needs windows aligned to 2 pixels (Waveshare's BSP rounds the same way), so
 * every area LVGL redraws goes through this. With an even frame size the result stays inside the
 * frame, and an even column offset keeps the alignment in panel RAM. */
void owl_co5300_round_area(int32_t *x1, int32_t *y1, int32_t *x2, int32_t *y2);

/* VIEWE ALL-UEOL018VG-RA31-A001A (owl rev A): VIEWE's sequence of 17 October 2026, columns 6 to 471. */
#define OWL_CO5300_VIEWE_COL_OFFSET 6
extern const owl_co5300_cmd_t owl_co5300_init_viewe[];
extern const size_t owl_co5300_init_viewe_len;

/* Waveshare ESP32-S3-Touch-AMOLED-1.75: the sequence from Waveshare's ESP-IDF BSP, columns 6 to 471. */
#define OWL_CO5300_WAVESHARE_175_COL_OFFSET 6
extern const owl_co5300_cmd_t owl_co5300_init_waveshare_175[];
extern const size_t owl_co5300_init_waveshare_175_len;

#ifdef __cplusplus
}
#endif
