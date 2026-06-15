#pragma once
#include <stdint.h>
#include <stdbool.h>

#ifdef __cplusplus
extern "C" {
#endif

typedef struct {
    uint16_t node_id;
    uint8_t network_id;
    uint8_t node_secret[16];
    uint16_t gateway_addr;
    uint8_t lora_channel;
} node_config_t;

void config_manager_init(void);

// Returns false if not provisioned
bool config_manager_is_provisioned(void);

// Load running config from NVS
bool config_manager_load(node_config_t* out_config);

// Save new config push to NVS
bool config_manager_save(const node_config_t* config);

// Get monotonic sequence number
uint32_t config_manager_get_next_seq(void);

#ifdef __cplusplus
}
#endif
