#pragma once

#include <map>
#include <string>
#include <vector>

struct RawItem {
  std::string mid;
  std::string name;
  std::string ns;
  std::map<std::string, std::string> labels;
  std::map<std::string, std::string> annots;
};

struct BandCtx {
  std::string band;
  bool annex_on;
  std::string scope_letter;
  std::string set_stem;
};

struct UnitPlan {
  std::vector<std::string> slots;
  int gen = 0;
  std::string parent_tip_hex;
  std::string ns;
};

struct ByteDigest {
  std::string hex;
  std::string wire;
  int epoch = 0;
  int window_id = 0;
};

struct AbBundle {
  UnitPlan plan;
  ByteDigest dig;
};

RawItem load_item_json(const std::string& path);
BandCtx load_band_ctx(const std::string& profile_path);

UnitPlan fold_r1(const RawItem& in, const BandCtx& ctx);
ByteDigest mix_r2(const UnitPlan& plan, const BandCtx& ctx, const std::string& mid);
