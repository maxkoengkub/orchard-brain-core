#pragma once
#include <stdint.h>
#include <stdbool.h>

#ifdef __cplusplus
extern "C" {
#endif

typedef enum {
    OTA_STATE_IDLE,
    OTA_STATE_ANNOUNCED,
    OTA_STATE_DOWNLOADING,
    OTA_STATE_VERIFYING,
    OTA_STATE_COMPLETE,
    OTA_STATE_ABORTED
} ota_state_t;

void ota_manager_init(void);

// Handle incoming OTA_ANNOUNCE packet
bool ota_manager_handle_announce(uint32_t version, uint32_t total_size, uint16_t chunk_count, const uint8_t* sha256);

// Handle incoming OTA_CHUNK packet
bool ota_manager_handle_chunk(uint16_t chunk_index, const uint8_t* data, uint16_t len, uint16_t crc);

ota_state_t ota_manager_get_state(void);

// Commit update and reboot if verification succeeds
void ota_manager_commit(void);

// Boot loops detection and rollback
void ota_manager_check_rollback(void);

#ifdef __cplusplus
}
#endif
