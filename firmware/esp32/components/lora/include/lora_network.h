#pragma once
#include "lora_packet.h"

#ifdef __cplusplus
extern "C" {
#endif

typedef enum {
    TX_STATUS_SUCCESS,
    TX_STATUS_NO_ACK,
    TX_STATUS_ERROR
} tx_status_t;

// Initialise the LoRa MAC layer
void lora_network_init(void);

// Build and transmit a generic frame. Handles MAC headers and HMAC signing.
// Blocks until ACK received or timeout/retries exhausted.
tx_status_t lora_network_send_frame(uint16_t dest, uint8_t type, uint8_t flags, const uint8_t* payload, uint16_t payload_len);

// Enqueue a fast path alert uplink.
void lora_network_send_alert(const uint8_t* alert_payload, uint16_t len);

// Called continuously in the main loop to process RX/TX events
void lora_network_process(void);

#ifdef __cplusplus
}
#endif
