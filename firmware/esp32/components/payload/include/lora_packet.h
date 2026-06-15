#pragma once
#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

#define MAX_PAYLOAD_SIZE 200

// Packet Types (Header upper nibble)
#define PKT_TYPE_DATA_UPLINK   0x1
#define PKT_TYPE_DATA_ACK      0x2
#define PKT_TYPE_DATA_NACK     0x3
#define PKT_TYPE_HEARTBEAT     0x4
#define PKT_TYPE_HEARTBEAT_ACK 0x5
#define PKT_TYPE_CONFIG_PUSH   0x6
#define PKT_TYPE_CONFIG_ACK    0x7
#define PKT_TYPE_OTA_ANNOUNCE  0x8
#define PKT_TYPE_OTA_CHUNK     0x9
#define PKT_TYPE_OTA_CHUNK_ACK 0xA
#define PKT_TYPE_OTA_COMPLETE  0xB
#define PKT_TYPE_ALERT_UPLINK  0xC

// Flags (Header lower nibble)
#define FLAG_RETRY  (1 << 0)
#define FLAG_URGENT (1 << 1)
#define FLAG_FRAG   (1 << 2)

// NACK Reasons
#define NACK_REASON_HMAC_FAIL         0x01
#define NACK_REASON_SEQ_REPLAY        0x02
#define NACK_REASON_PAYLOAD_MALFORMED 0x03
#define NACK_REASON_GATEWAY_BUSY      0x04

typedef struct __attribute__((packed)) {
    uint16_t dest;
    uint16_t src;
    uint8_t  net;
    uint8_t  hdr; // upper nibble: type, lower nibble: flags
} lora_mac_header_t;

typedef struct __attribute__((packed)) {
    lora_mac_header_t header;
    uint8_t payload[MAX_PAYLOAD_SIZE];
    uint8_t hmac_t[4]; // Truncated HMAC
} lora_frame_t;

#ifdef __cplusplus
}
#endif
