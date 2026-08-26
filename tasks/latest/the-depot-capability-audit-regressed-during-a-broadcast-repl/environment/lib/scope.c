#include "scope.h"

uint32_t scope_intersect(uint32_t child_mask, uint32_t parent_mask) {
    return child_mask & parent_mask;
}

int scope_covers(uint32_t effective_mask, uint32_t action_mask) {
    return (action_mask & effective_mask) == action_mask;
}
