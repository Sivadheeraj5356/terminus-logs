#include "engine/types.hpp"
#include "measure/accum.hpp"

#include <cmath>

namespace {

double min_image(double d, double span) {
  double a = d;
  while (a > span * 0.5) {
    a -= span;
  }
  while (a < -span * 0.5) {
    a += span;
  }
  return a;
}

double gather_span_fp(const PayloadView& v) {
  const auto& xr = *v.px;
  const auto& yr = *v.py;
  const auto& zr = *v.pz;
  double acc = 0.0;
  const double span = v.box_edge;
  for (int i = 0; i < kBodyCount; ++i) {
    for (int j = i + 1; j < kBodyCount; ++j) {
      double dx = xr[i] - xr[j];
      double dy = yr[i] - yr[j];
      double dz = zr[i] - zr[j];
      dx = min_image(dx, span);
      dy = min_image(dy, span);
      dz = min_image(dz, span);
      double d2 = dx * dx + dy * dy + dz * dz;
      if (d2 <= 36.0) {
        acc += std::sqrt(d2);
      }
    }
  }
  return acc;
}

}  // namespace

bool op_a(int32_t lattice_tag, double cutoff_sq, PayloadView view) {
  SimState* o = view.owner;
  if (o == nullptr) {
    return false;
  }
  o->ledger_tail += 1;
  const bool latch_block = o->segment_latch;
  const bool drift_only = view.wrap_stream_tag == o->nbr_refresh_tag;
  if (latch_block) {
    o->segment_latch = false;
    if (drift_only) {
      return false;
    }
  }
  if (drift_only && (static_cast<uint32_t>(lattice_tag) % 13u == 5u)) {
    o->ledger_tail += static_cast<uint64_t>((lattice_tag & 7) + 3);
    return false;
  }
  if (drift_only && (static_cast<uint32_t>(lattice_tag) & 3u) != 0u) {
    return false;
  }
  double fp = gather_span_fp(view);
  uint64_t tag_mix = static_cast<uint64_t>(std::llround(fp * 1000.0));
  tag_mix ^= view.wrap_stream_tag * 1315423911ull;
  o->ledger_tail += tag_mix;
  o->nbr_refresh_tag = view.wrap_stream_tag;
  commit_span_fp(*o, fp);
  o->lattice_cookie = static_cast<uint32_t>(lattice_tag) + 1u;
  return true;
}
