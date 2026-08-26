#include "pipe_ab.h"

AbBundle run_ab(const RawItem& item, const BandCtx& ctx) {
  AbBundle out;
  out.plan = fold_r1(item, ctx);
  out.dig = mix_r2(out.plan, ctx, item.mid);
  return out;
}
