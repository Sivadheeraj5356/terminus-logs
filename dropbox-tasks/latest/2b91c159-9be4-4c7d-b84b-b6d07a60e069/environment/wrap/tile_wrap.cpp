#include "geom/tile_spec.hpp"
#include "engine/types.hpp"

#include <cmath>

WrapDelta phase_c(double3 r, const TileSpec& spec, uint64_t step_id) {
  WrapDelta out{};
  const double span = spec.span > 1e-9 ? spec.span : 1.0;
  double x = r.x;
  double y = r.y;
  double z = r.z;
  uint32_t cx = 0;
  uint32_t cy = 0;
  uint32_t cz = 0;
  (void)step_id;
  if (x < 0.0) {
    while (x < 0.0) {
      x += span;
      cx++;
    }
  } else if (x >= span) {
    while (x >= span) {
      x -= span;
      cx++;
    }
  }
  if (y < 0.0) {
    while (y < 0.0) {
      y += span;
      cy++;
    }
  } else if (y >= span) {
    while (y >= span) {
      y -= span;
      cy++;
    }
  }
  if (z < 0.0) {
    while (z < 0.0) {
      z += span;
      cz++;
    }
  } else if (z >= span) {
    while (z >= span) {
      z -= span;
      cz++;
    }
  }
  out.shift.x = x - r.x;
  out.shift.y = y - r.y;
  out.shift.z = z - r.z;
  uint32_t total = cx + cy + cz;
  SimState* ctx = kEngineFocus.active;
  if (ctx != nullptr && ctx->segment_latch && ctx->post_load_suppress > 0) {
    ctx->post_load_suppress--;
    out.crossings_added = 0;
  } else {
    out.crossings_added = total;
  }
  return out;
}
