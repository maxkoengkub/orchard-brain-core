#pragma once
#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

typedef struct __attribute__((packed)) {
    uint32_t seq_num;
} data_ack_payload_t;

typedef struct __attribute__((packed)) {
    uint32_t seq_num;
    uint8_t  reason; // e.g. NACK_REASON_HMAC_FAIL
} data_nack_payload_t;

typedef struct __attribute__((packed)) {
    uint8_t command_id[16];   // UUID or string id
    uint16_t target_node;
    uint8_t actuator_type;    // 0=VALVE, 1=PUMP, 2=FERTIGATOR
    uint8_t action;           // 0=OPEN, 1=CLOSE, 2=SET
    float value;              // for SET actions
    uint32_t duration_sec;    // optional duration
} actuation_command_payload_t;

#ifdef __cplusplus
}
#endif
