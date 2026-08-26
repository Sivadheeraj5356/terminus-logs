#ifndef N8_ADDR_SNAP_H
#define N8_ADDR_SNAP_H

#include <stdint.h>

uint32_t addr_mask_parse(const char *hex);
void addr_mask_format(uint32_t mask, char *out, int out_len);
uint32_t lane_digest_fnv(const char *key, uint32_t gen, uint32_t cfg,
			 uint32_t sample, uint32_t live, char gate);
uint32_t bundle_digest_fnv(const char *payload);

#endif
