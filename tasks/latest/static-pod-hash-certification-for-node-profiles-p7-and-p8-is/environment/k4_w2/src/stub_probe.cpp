#include "raw_io.h"

#include <fstream>

std::string probe_one(const RawItem& item) {
  BandCtx ctx;
  ctx.band = "p7";
  ctx.annex_on = false;
  UnitPlan plan = fold_r1(item, ctx);
  ByteDigest dig = mix_r2(plan, ctx, item.mid);
  return dig.hex;
}

int write_probe_count(const std::string& out_path, int n) {
  std::ofstream out(out_path);
  if (!out) {
    return 1;
  }
  out << "{\n  \"local_matches\": " << n << "\n}\n";
  return 0;
}
