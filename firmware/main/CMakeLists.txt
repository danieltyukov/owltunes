set(srcs main.c demo_state.c settings_store.c console.c provisioning_task.c spotify_link.c callback_server.c)
if(CONFIG_OWL_NET_ETH_QEMU)
    list(APPEND srcs net_qemu.c)
endif()

# Requirements must not depend on the configuration, so every board's BSP is listed; each one
# compiles its source only for its own board.
idf_component_register(SRCS ${srcs}
                       INCLUDE_DIRS .
                       REQUIRES owl_core spotify owl_ui provisioning bsp bsp_qemu esp_timer esp_app_format
                                esp_event esp_netif esp_eth nvs_flash esp_http_client esp_http_server mbedtls
                                esp_driver_uart)
