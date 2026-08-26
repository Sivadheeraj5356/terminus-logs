#include "plan_types.h"

uint32_t weave_u_fold(uint32_t persisted, uint32_t live);

uint32_t merge_bias_wrap(uint32_t persisted, uint32_t live) {
  uint32_t persisted_adj = persisted;
  if (live > persisted && persisted > 0) {
    persisted_adj = persisted - 1;
  }
  return weave_u_fold(persisted_adj, live);
}
