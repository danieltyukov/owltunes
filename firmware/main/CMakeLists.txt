set(srcs main.c demo_state.c settings_store.c console.c provisioning_task.c spotify_link.c callback_server.c)
if(CONFIG_OWL_BOARD_QEMU)
    list(APPEND srcs board_qemu.c net_qemu.c)
endif()

idf_component_register(SRCS ${srcs}
                       INCLUDE_DIRS .
                       REQUIRES owl_core spotify owl_ui provisioning esp_lcd esp_timer esp_app_format esp_event
                                esp_netif esp_eth nvs_flash esp_http_client esp_http_server mbedtls esp_driver_uart)
