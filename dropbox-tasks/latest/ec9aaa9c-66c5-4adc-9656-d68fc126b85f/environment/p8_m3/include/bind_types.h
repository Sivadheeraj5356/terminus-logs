#pragma once

#include "raw_io.h"

#include <string>

struct RowBundle {
  std::string mid;
  std::string digest_hex;
  std::string slot_line;
  std::string band;
  int cache_epoch = 0;
  std::string journal_tip_hex;
  int window_id = 0;
};

RowBundle latch_r3(const ByteDigest& dig, const BandCtx& ctx, const std::string& mid,
                   const UnitPlan& plan);
