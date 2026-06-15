#pragma once
#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

typedef struct __attribute__((packed)) {
    uint32_t config_hash;
    uint8_t lora_channel;      // 0-83
    int8_t tx_power_dbm;       // e.g. 30
    uint32_t sample_rate_sec;  // e.g. 30
} config_push_payload_t;

typedef struct __attribute__((packed)) {
    uint32_t config_hash;
} config_ack_payload_t;

#ifdef __cplusplus
}
#endif
