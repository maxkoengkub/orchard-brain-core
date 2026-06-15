#include <stdio.h>
#include <stdbool.h>

// ESP-IDF abstractions (we use standard types here for portability of the skeleton)
#include "sensor_manager.h"
#include "lora_network.h"
#include "nvs_manager.h"
#include "config_manager.h"
#include "tx_buffer.h"
#include "ota_manager.h"

// Firmware State Machine (Architecture §1.7)
typedef enum {
    STATE_INIT,
    STATE_SELF_TEST,
    STATE_SAMPLING_FAST,
    STATE_TX_AGGREGATE,
    STATE_TX_LORA,
    STATE_CHECK_OTA,
    STATE_DEEP_SLEEP,
    STATE_ERROR
} system_state_t;

static system_state_t current_state = STATE_INIT;

void app_main(void)
{
    while (1) {
        switch (current_state) {
            case STATE_INIT:
                nvs_manager_init();
                config_manager_init();
                tx_buffer_init();
                sensor_manager_init();
                lora_network_init();
                ota_manager_init();
                ota_manager_check_rollback();
                current_state = STATE_SELF_TEST;
                break;

            case STATE_SELF_TEST:
                if (sensor_manager_self_test()) {
                    current_state = STATE_SAMPLING_FAST;
                } else {
                    current_state = STATE_ERROR;
                }
                break;

            case STATE_SAMPLING_FAST:
                // Abstract: 30-second timer triggers this
                sensor_manager_acquire_fast_sample();
                // Check if we hit the 10th sample (5 minutes)
                bool is_tx_cycle = true; // Simplified for skeleton
                if (is_tx_cycle) {
                    current_state = STATE_TX_AGGREGATE;
                } else {
                    current_state = STATE_DEEP_SLEEP;
                }
                break;

            case STATE_TX_AGGREGATE:
            {
                sensor_reading_payload_t tx_payload;
                sensor_manager_aggregate(&tx_payload);
                tx_buffer_push_tx_payload(&tx_payload);
                current_state = STATE_TX_LORA;
                break;
            }

            case STATE_TX_LORA:
            {
                sensor_reading_payload_t payload;
                if (tx_buffer_pop_pending_tx_payload(&payload)) {
                    // Assume Gateway Dest = 0x0000
                    tx_status_t status = lora_network_send_frame(0x0000, PKT_TYPE_DATA_UPLINK, 0, (uint8_t*)&payload, sizeof(payload));
                    if (status == TX_STATUS_SUCCESS) {
                        tx_buffer_mark_delivered(payload.sequence_number);
                    }
                }
                current_state = STATE_CHECK_OTA;
                break;
            }

            case STATE_CHECK_OTA:
                if (ota_manager_get_state() == OTA_STATE_ANNOUNCED) {
                    // Enter OTA Session
                }
                current_state = STATE_DEEP_SLEEP;
                break;

            case STATE_DEEP_SLEEP:
                // Enter deep sleep until next 30-second interval
                // Execution halts here in reality
                current_state = STATE_SAMPLING_FAST; // Loop for testing
                break;

            case STATE_ERROR:
                // Blink LED, retry in 60s
                current_state = STATE_INIT;
                break;
        }
    }
}
