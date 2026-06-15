#pragma once
#include <stdint.h>
#include <stdbool.h>

#ifdef __cplusplus
extern "C" {
#endif

void nvs_manager_init(void);

bool nvs_read_u16(const char* key, uint16_t* out_val);
bool nvs_write_u16(const char* key, uint16_t val);

bool nvs_read_u32(const char* key, uint32_t* out_val);
bool nvs_write_u32(const char* key, uint32_t val);

bool nvs_read_blob(const char* key, void* out_data, size_t* len);
bool nvs_write_blob(const char* key, const void* data, size_t len);

#ifdef __cplusplus
}
#endif
