/* A small CO5300 driver on esp_lcd's SPI panel IO in quad mode, and the LVGL glue for the display and
 * the touch controller. The command framing follows Espressif's esp_lcd_co5300 (esp-iot-solution);
 * the panel-specific init tables live in owl_co5300.c. */
#include "owl_amoled.h"

#include <stdatomic.h>

#include "driver/gpio.h"
#include "driver/i2c_master.h"
#include "driver/spi_master.h"
#include "esp_attr.h"
#include "esp_err.h"
#include "esp_heap_caps.h"
#include "esp_lcd_io_spi.h"
#include "esp_lcd_panel_io.h"
#include "esp_log.h"
#include "esp_timer.h"
#include "freertos/FreeRTOS.h"
#include "freertos/semphr.h"
#include "freertos/task.h"
#include "sdkconfig.h"

static const char *TAG = "owl_amoled";

/* Lines per draw buffer: two buffers of 466 x 20 RGB565 pixels take 37 KB of internal RAM. */
#define LINES 20
#define I2C_TIMEOUT_MS 50

typedef struct {
    esp_lcd_panel_io_handle_t io;
    int32_t col_offset;
    SemaphoreHandle_t sent; /* given from the SPI interrupt when a block of pixels has gone out */
} panel_t;

typedef struct {
    i2c_master_dev_handle_t dev;
    owl_amoled_touch_t cfg;
    atomic_bool reported; /* set by the INT edge, cleared by the read */
    bool down;
    int x; /* last point; LVGL wants it again with the release */
    int y;
    owl_touch_orient_t orient; /* from the OWL_TOUCH_ options */
    unsigned failures;
} touch_t;

static panel_t s_panel;
static touch_t s_touch;

/* At least ms milliseconds: vTaskDelay(n) can return up to a tick early. */
static void wait_ms(uint32_t ms)
{
    vTaskDelay(pdMS_TO_TICKS(ms) + 1);
}

static esp_err_t send_cmd(esp_lcd_panel_io_handle_t io, uint8_t cmd, const uint8_t *data, size_t len)
{
    return esp_lcd_panel_io_tx_param(io, (int)owl_co5300_cmd_word(OWL_CO5300_OP_WRITE_CMD, cmd), data, len);
}

/* Called from the SPI interrupt, which is in IRAM, so this must be too. */
static bool IRAM_ATTR on_pixels_sent(esp_lcd_panel_io_handle_t io, esp_lcd_panel_io_event_data_t *edata,
                                     void *ctx)
{
    (void)io;
    (void)edata;
    BaseType_t woken = pdFALSE;
    xSemaphoreGiveFromISR(((panel_t *)ctx)->sent, &woken);
    return woken == pdTRUE;
}

/* LVGL renders RGB565 in the CPU's byte order, low byte first; the panel takes each pixel high byte
 * first, so the block is swapped in place before it goes out. */
static void flush(lv_display_t *disp, const lv_area_t *area, uint8_t *px_map)
{
    panel_t *p = lv_display_get_user_data(disp);
    uint32_t px = (uint32_t)(lv_area_get_width(area) * lv_area_get_height(area));
    lv_draw_rgb565_swap(px_map, px);
    owl_co5300_window_t win;
    owl_co5300_window(area->x1, area->y1, area->x2, area->y2, p->col_offset, &win);
    esp_err_t err = send_cmd(p->io, OWL_CO5300_CASET, win.caset, sizeof win.caset);
    if (err == ESP_OK) {
        err = send_cmd(p->io, OWL_CO5300_RASET, win.raset, sizeof win.raset);
    }
    if (err == ESP_OK) {
        /* Queued for DMA: LVGL renders the next block into the other buffer meanwhile, and wait_sent
         * holds it back from reusing this one until on_pixels_sent. */
        const int ramwr = (int)owl_co5300_cmd_word(OWL_CO5300_OP_WRITE_PIXELS, OWL_CO5300_RAMWR);
        err = esp_lcd_panel_io_tx_color(p->io, ramwr, px_map, px * sizeof(uint16_t));
    }
    if (err != ESP_OK) {
        ESP_LOGE(TAG, "flush failed: %s", esp_err_to_name(err));
        lv_display_flush_ready(disp); /* nothing is on the bus, so there is nothing to wait for */
    }
}

static void wait_sent(lv_display_t *disp)
{
    panel_t *p = lv_display_get_user_data(disp);
    xSemaphoreTake(p->sent, portMAX_DELAY);
}

/* The CO5300's 2-pixel window rule, applied to every invalidated area (see owl_co5300_round_area).
 * LVGL also passes the height of each partial block through here, so blocks stay aligned too. */
static void align_area(lv_event_t *e)
{
    lv_area_t *a = lv_event_get_invalidated_area(e);
    owl_co5300_round_area(&a->x1, &a->y1, &a->x2, &a->y2);
}

lv_display_t *owl_amoled_display_create(const owl_amoled_panel_t *panel)
{
    const size_t buf_size = OWL_CO5300_RES * LINES * sizeof(uint16_t);
    const spi_bus_config_t bus = {
        .sclk_io_num = panel->pin_clk,
        .data0_io_num = panel->pin_d0,
        .data1_io_num = panel->pin_d1,
        .data2_io_num = panel->pin_d2,
        .data3_io_num = panel->pin_d3,
        .data4_io_num = -1,
        .data5_io_num = -1,
        .data6_io_num = -1,
        .data7_io_num = -1,
        .max_transfer_sz = (int)buf_size,
        .flags = SPICOMMON_BUSFLAG_QUAD,
    };
    ESP_ERROR_CHECK(spi_bus_initialize(SPI2_HOST, &bus, SPI_DMA_CH_AUTO));

    s_panel.col_offset = panel->col_offset;
    s_panel.sent = xSemaphoreCreateBinary();
    ESP_ERROR_CHECK(s_panel.sent != NULL ? ESP_OK : ESP_ERR_NO_MEM);
    const esp_lcd_panel_io_spi_config_t io_config = {
        .cs_gpio_num = panel->pin_cs,
        .dc_gpio_num = GPIO_NUM_NC,
        .spi_mode = 0,
        .pclk_hz = panel->pclk_hz,
        .trans_queue_depth = 10,
        .on_color_trans_done = on_pixels_sent,
        .user_ctx = &s_panel,
        .lcd_cmd_bits = 32,
        .lcd_param_bits = 8,
        .flags.quad_mode = 1,
    };
    ESP_ERROR_CHECK(esp_lcd_new_panel_io_spi((esp_lcd_spi_bus_handle_t)SPI2_HOST, &io_config, &s_panel.io));

    for (size_t i = 0; i < panel->init_len; i++) {
        const owl_co5300_cmd_t *c = &panel->init[i];
        ESP_ERROR_CHECK(send_cmd(s_panel.io, c->cmd, c->data, c->len));
        if (c->delay_ms > 0) {
            wait_ms(c->delay_ms);
        }
    }
    bool bgr = false;
#ifdef CONFIG_OWL_LCD_BGR
    const uint8_t madctl = OWL_CO5300_MADCTL_BGR;
    ESP_ERROR_CHECK(send_cmd(s_panel.io, OWL_CO5300_MADCTL, &madctl, 1));
    bgr = true;
#endif
    ESP_LOGI(TAG, "CO5300 up: %u init commands, column offset %ld%s", (unsigned)panel->init_len,
             (long)panel->col_offset, bgr ? ", BGR" : "");

    void *buf1 = heap_caps_malloc(buf_size, MALLOC_CAP_DMA | MALLOC_CAP_INTERNAL);
    void *buf2 = heap_caps_malloc(buf_size, MALLOC_CAP_DMA | MALLOC_CAP_INTERNAL);
    ESP_ERROR_CHECK(buf1 != NULL && buf2 != NULL ? ESP_OK : ESP_ERR_NO_MEM);
    lv_display_t *disp = lv_display_create(OWL_CO5300_RES, OWL_CO5300_RES);
    lv_display_set_color_format(disp, LV_COLOR_FORMAT_RGB565);
    lv_display_set_buffers(disp, buf1, buf2, buf_size, LV_DISPLAY_RENDER_MODE_PARTIAL);
    lv_display_set_user_data(disp, &s_panel);
    lv_display_set_flush_cb(disp, flush);
    lv_display_set_flush_wait_cb(disp, wait_sent);
    lv_display_add_event_cb(disp, align_area, LV_EVENT_INVALIDATE_AREA, NULL);
    return disp;
}

static void IRAM_ATTR on_touch_int(void *arg)
{
    atomic_store(&((touch_t *)arg)->reported, true);
}

static esp_err_t read_cst816(touch_t *t, bool *down, int *x, int *y)
{
    const uint8_t reg = OWL_CST816_REG_POINT;
    uint8_t regs[OWL_CST816_POINT_LEN];
    esp_err_t err = i2c_master_transmit_receive(t->dev, &reg, 1, regs, sizeof regs, I2C_TIMEOUT_MS);
    if (err == ESP_OK) {
        *down = owl_cst816_point(regs, x, y);
    }
    return err;
}

/* As Waveshare's esp_lcd_touch_cst9217: write the register address, wait 2 ms, read in a second
 * transfer. */
static esp_err_t read_cst9217(touch_t *t, bool *down, int *x, int *y)
{
    const uint8_t reg[2] = {OWL_CST9217_REG_POINT >> 8, OWL_CST9217_REG_POINT & 0xFF};
    uint8_t data[OWL_CST9217_POINT_LEN];
    esp_err_t err = i2c_master_transmit(t->dev, reg, sizeof reg, I2C_TIMEOUT_MS);
    if (err == ESP_OK) {
        wait_ms(2);
        err = i2c_master_receive(t->dev, data, sizeof data, I2C_TIMEOUT_MS);
    }
    if (err == ESP_OK) {
        *down = owl_cst9217_point(data, x, y);
    }
    return err;
}

/* Reads only after an INT edge or while a finger is down: the CST816S family sleeps when idle and
 * does not answer on I2C then, and an idle bus keeps the read callback cheap. Nothing is read before
 * the controller's reset wait is over; an edge from that time is kept for the first read. */
static void touch_read(lv_indev_t *indev, lv_indev_data_t *data)
{
    touch_t *t = lv_indev_get_user_data(indev);
    if (esp_timer_get_time() >= t->cfg.ready_at_us && (atomic_exchange(&t->reported, false) || t->down)) {
        bool down = false;
        int rx = 0;
        int ry = 0;
        esp_err_t err = t->cfg.chip == OWL_TOUCH_CST9217 ? read_cst9217(t, &down, &rx, &ry)
                                                         : read_cst816(t, &down, &rx, &ry);
        if (err != ESP_OK) {
            if (t->failures++ == 0) {
                ESP_LOGW(TAG, "touch read failed: %s", esp_err_to_name(err));
            }
            down = false;
        } else {
            t->failures = 0;
            if (down) {
                owl_touch_map(t->orient, OWL_CO5300_RES, rx, ry, &t->x, &t->y);
            }
        }
        t->down = down;
    }
    data->point.x = t->x;
    data->point.y = t->y;
    data->state = t->down ? LV_INDEV_STATE_PRESSED : LV_INDEV_STATE_RELEASED;
}

lv_indev_t *owl_amoled_touch_create(lv_display_t *disp, const owl_amoled_touch_t *touch)
{
    s_touch.cfg = *touch;
#ifdef CONFIG_OWL_TOUCH_SWAP_XY
    s_touch.orient.swap_xy = true;
#endif
#ifdef CONFIG_OWL_TOUCH_MIRROR_X
    s_touch.orient.mirror_x = true;
#endif
#ifdef CONFIG_OWL_TOUCH_MIRROR_Y
    s_touch.orient.mirror_y = true;
#endif
    ESP_LOGI(TAG, "touch: %s at 0x%02X, swap %d, mirror X %d, mirror Y %d",
             touch->chip == OWL_TOUCH_CST9217 ? "CST9217" : "CST816", touch->addr, s_touch.orient.swap_xy,
             s_touch.orient.mirror_x, s_touch.orient.mirror_y);
    /* Both boards have external pull-ups on SDA and SCL (Waveshare's BSP leaves the internal ones off
     * too); on rev A an internal pull-up would also feed DISP_3V3 while the panel is off. */
    const i2c_master_bus_config_t bus_config = {
        .i2c_port = touch->i2c_port,
        .sda_io_num = touch->pin_sda,
        .scl_io_num = touch->pin_scl,
        .clk_source = I2C_CLK_SRC_DEFAULT,
        .glitch_ignore_cnt = 7,
        .flags.enable_internal_pullup = 0,
    };
    i2c_master_bus_handle_t bus = NULL;
    ESP_ERROR_CHECK(i2c_new_master_bus(&bus_config, &bus));
    const i2c_device_config_t dev_config = {
        .dev_addr_length = I2C_ADDR_BIT_LEN_7,
        .device_address = touch->addr,
        .scl_speed_hz = touch->scl_hz,
    };
    ESP_ERROR_CHECK(i2c_master_bus_add_device(bus, &dev_config, &s_touch.dev));

    const gpio_config_t int_config = {
        .pin_bit_mask = 1ULL << touch->pin_int,
        .mode = GPIO_MODE_INPUT,
        .pull_up_en = touch->int_pullup ? GPIO_PULLUP_ENABLE : GPIO_PULLUP_DISABLE,
        .pull_down_en = GPIO_PULLDOWN_DISABLE,
        .intr_type = GPIO_INTR_NEGEDGE,
    };
    ESP_ERROR_CHECK(gpio_config(&int_config));
    esp_err_t err = gpio_install_isr_service(0);
    ESP_ERROR_CHECK(err == ESP_ERR_INVALID_STATE ? ESP_OK : err); /* already installed elsewhere */
    ESP_ERROR_CHECK(gpio_isr_handler_add((gpio_num_t)touch->pin_int, on_touch_int, &s_touch));

    lv_indev_t *indev = lv_indev_create();
    lv_indev_set_type(indev, LV_INDEV_TYPE_POINTER);
    lv_indev_set_read_cb(indev, touch_read);
    lv_indev_set_user_data(indev, &s_touch);
    lv_indev_set_display(indev, disp);
    return indev;
}
