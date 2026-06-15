#pragma once
#include "sensor_data.h"
#include <stdbool.h>

#ifdef __cplusplus
extern "C" {
#endif

// Initialise PSRAM ring buffers
bool tx_buffer_init(void);

// Fast Buffer (30s samples)
bool tx_buffer_push_fast_sample(const sensor_result_t* results, uint8_t count);
bool tx_buffer_get_fast_samples(sensor_result_t* out_results, uint8_t max_count, uint8_t* out_count);

// TX Buffer (5m aggregated payloads)
bool tx_buffer_push_tx_payload(const sensor_reading_payload_t* payload);
bool tx_buffer_pop_pending_tx_payload(sensor_reading_payload_t* out_payload);
void tx_buffer_mark_delivered(uint32_t seq_num);

#ifdef __cplusplus
}
#endif
