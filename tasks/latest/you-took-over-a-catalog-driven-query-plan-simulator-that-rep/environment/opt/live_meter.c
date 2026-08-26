#include "plan_types.h"

void bump_rows_only(pl_table *t, uint32_t rows) {
  if (!t) {
    return;
  }
  t->rows = rows;
}
