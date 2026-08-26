#include "plan_types.h"

double upper_join_bound(uint32_t left_rows, uint32_t right_rows) {
  return (double)left_rows + (double)right_rows + 1.0;
}
