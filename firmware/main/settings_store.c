#include "settings_store.h"

#include "nvs.h"
#include "nvs_flash.h"

#define NAMESPACE "owl"
#define KEY "settings"

esp_err_t settings_store_init(void)
{
    esp_err_t err = nvs_flash_init();
    if (err == ESP_ERR_NVS_NO_FREE_PAGES || err == ESP_ERR_NVS_NEW_VERSION_FOUND) {
        ESP_ERROR_CHECK(nvs_flash_erase());
        err = nvs_flash_init();
    }
    return err;
}

bool settings_store_load(owl_settings_t *s)
{
    nvs_handle_t nvs;
    if (nvs_open(NAMESPACE, NVS_READONLY, &nvs) != ESP_OK) {
        return false;
    }
    size_t size = sizeof *s;
    esp_err_t err = nvs_get_blob(nvs, KEY, s, &size);
    nvs_close(nvs);
    return err == ESP_OK && size == sizeof *s;
}

esp_err_t settings_store_save(const owl_settings_t *s)
{
    nvs_handle_t nvs;
    esp_err_t err = nvs_open(NAMESPACE, NVS_READWRITE, &nvs);
    if (err != ESP_OK) {
        return err;
    }
    err = nvs_set_blob(nvs, KEY, s, sizeof *s);
    if (err == ESP_OK) {
        err = nvs_commit(nvs);
    }
    nvs_close(nvs);
    return err;
}
