#pragma once
#include <stdint.h>
#include <stdbool.h>

#ifdef __cplusplus
extern "C" {
#endif

typedef struct lora_driver_t lora_driver_t;

typedef struct {
    void (*on_rx)(const uint8_t* data, uint16_t len, int8_t rssi);
    void (*on_tx_done)(void);
    void (*on_error)(void);
} lora_callbacks_t;

// Abstract interface for the E220 UART driver
struct lora_driver_t {
    bool (*init)(lora_callbacks_t cb);
    bool (*transmit)(const uint8_t* data, uint16_t len);
    void (*set_mode_rx)(void);
    void (*set_mode_tx)(void);
    void (*set_mode_sleep)(void);
    bool (*reset)(void);
};

#ifdef __cplusplus
}
#endif
