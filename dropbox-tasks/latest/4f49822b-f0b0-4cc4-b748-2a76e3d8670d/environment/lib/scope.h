#ifndef DEPOT_LIB_SCOPE_H
#define DEPOT_LIB_SCOPE_H

#include <stdint.h>

uint32_t scope_intersect(uint32_t child_mask, uint32_t parent_mask);
int scope_covers(uint32_t effective_mask, uint32_t action_mask);

#endif
