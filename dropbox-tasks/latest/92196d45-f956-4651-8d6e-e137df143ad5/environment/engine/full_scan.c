#include "plan_types.h"

int full_scan_cost(const pl_table *t) {
  if (!t) {
    return 0;
  }
  return (int)t->rows;
}
