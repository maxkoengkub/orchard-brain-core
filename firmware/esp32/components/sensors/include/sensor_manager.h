#pragma once
#include "sensor_data.h"

#ifdef __cplusplus
extern "C" {
#endif

// Initialise the sensor subsystem
void sensor_manager_init(void);

// Run a self-test across all registered sensors
bool sensor_manager_self_test(void);

// Acquire a fast sample from all sensors (e.g. every 30s)
void sensor_manager_acquire_fast_sample(void);

// Aggregate accumulated fast samples into a payload (e.g. every 5m)
void sensor_manager_aggregate(sensor_reading_payload_t* out_payload);

// Determine if conditions warrant escalation based on critical thresholds
bool sensor_manager_check_escalation(void);

#ifdef __cplusplus
}
#endif
