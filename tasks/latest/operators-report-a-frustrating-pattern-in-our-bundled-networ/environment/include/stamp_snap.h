#ifndef N8_STAMP_SNAP_H
#define N8_STAMP_SNAP_H

#include <stdint.h>

typedef struct StampFoldMeta {
	uint32_t pending_gen;
	uint32_t reconfig_ticks;
} StampFoldMeta;

#endif
