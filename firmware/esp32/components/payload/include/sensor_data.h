#pragma once
#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

// EXACTLY 30 BYTES AS PER PHASE 1 ARCHITECTURE
typedef struct __attribute__((packed)) {
    uint16_t node_id;         // 0x00
    uint32_t timestamp;       // 0x02 - Unix epoch seconds
    uint32_t sequence_number; // 0x06 - Monotonic counter
    int16_t  temperature;     // 0x0A - °C x 100
    uint16_t humidity;        // 0x0C - % x 100
    uint16_t soil_moisture;   // 0x0E - % VWC x 100
    uint16_t ec;              // 0x10 - µS/cm x 10
    uint16_t ph;              // 0x12 - pH x 100
    uint16_t rainfall;        // 0x14 - mm x 10
    uint8_t  sensor_mask;     // 0x16 - Bit flags for channel status
    uint8_t  battery_pct;     // 0x17 - 0-100
    uint8_t  tx_reason;       // 0x18 - 0=scheduled, 1=escalation, 2=retry
    int8_t   rssi_last_rx;    // 0x19 - dBm
    uint8_t  hmac_truncated[4]; // 0x1A - first 4 bytes of HMAC-SHA256
} sensor_reading_payload_t;

#ifdef __cplusplus
}
#endif
