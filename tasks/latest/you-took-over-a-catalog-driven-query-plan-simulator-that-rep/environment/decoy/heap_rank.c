#include "plan_types.h"

int rank_heap(const pl_table *t) {
  if (!t) {
    return -1;
  }
  return (int)(t->distinct % 17);
}
