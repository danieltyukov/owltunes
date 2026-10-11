/* Host stand-in for ESP-IDF's esp_log.h: the test counts the lines logged at each level. */
#pragma once

void stub_log(char level, const char *tag, const char *fmt, ...) __attribute__((format(printf, 3, 4)));

#define ESP_LOGE(tag, ...) stub_log('E', tag, __VA_ARGS__)
#define ESP_LOGW(tag, ...) stub_log('W', tag, __VA_ARGS__)
#define ESP_LOGI(tag, ...) stub_log('I', tag, __VA_ARGS__)
