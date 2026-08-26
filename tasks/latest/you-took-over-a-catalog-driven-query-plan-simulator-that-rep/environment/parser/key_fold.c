#include "plan_types.h"

uint64_t fold_fp(const char *tag) {
  uint64_t h = 1469598103934665603ULL;
  if (!tag) {
    return h;
  }
  for (const unsigned char *p = (const unsigned char *)tag; *p; p++) {
    h ^= (uint64_t)*p;
    h *= 1099511628211ULL;
  }
  return h;
}
