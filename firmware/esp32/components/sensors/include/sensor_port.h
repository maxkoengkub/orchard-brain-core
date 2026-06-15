#pragma once
#include <stdint.h>
#include <stdbool.h>

#ifdef __cplusplus
extern "C" {
#endif

typedef enum {
    PORT_STATUS_ONLINE,
    PORT_STATUS_DEGRADED,
    PORT_STATUS_OFFLINE,
    PORT_STATUS_CALIBRATING
} port_status_t;

typedef enum {
    QUALITY_GOOD,
    QUALITY_SUSPECT,
    QUALITY_BAD
} sensor_quality_t;

typedef enum {
    ERR_NONE = 0x00,
    ERR_I2C_NACK = 0x01,
    ERR_ADC_RAIL = 0x02,
    ERR_RANGE_LOW = 0x03,
    ERR_RANGE_HIGH = 0x04,
    ERR_TIMEOUT = 0x05,
    ERR_CRC = 0x06
} sensor_error_t;

typedef struct {
    float value;
    uint16_t raw_adc;
    uint32_t timestamp;
    sensor_quality_t quality;
    sensor_error_t error_code;
} sensor_result_t;

// Opaque context for sensor driver specific data
typedef struct sensor_context_t sensor_context_t;

typedef struct sensor_port_t sensor_port_t;
struct sensor_port_t {
    const char* channel_id;
    sensor_result_t (*read)(sensor_port_t* port);
    port_status_t (*status)(sensor_port_t* port);
    void (*calibrate)(sensor_port_t* port);
    bool (*self_test)(sensor_port_t* port);
    sensor_context_t* ctx;
};

#ifdef __cplusplus
}
#endif
