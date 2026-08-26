#include "engine/types.hpp"
#include "io/codec_tags.hpp"

StoreResult reconcile_b(const SegmentHeader& hdr, MutableSegmentBody& body) {
  if (hdr.magic != 0xa17c3e10u) {
    return StoreResult::kBadMagic;
  }
  SimState* tgt = kEngineFocus.active;
  if (tgt == nullptr) {
    body.dirty = false;
    return StoreResult::kOk;
  }
  if (!body.dirty) {
    body.stored_crossings = tgt->orbit_crossings;
    body.stored_ledger = tgt->ledger_tail;
    body.dirty = true;
    return StoreResult::kOk;
  }
  tgt->orbit_crossings = body.stored_crossings;
  tgt->ledger_tail = body.stored_ledger;
  tgt->segment_latch = true;
  tgt->post_load_suppress = 0;
  tgt->nbr_refresh_tag = body.stored_crossings;
  tgt->segment_generation += 1;
  volatile uint32_t lane_tag = hdr.step_base ^ hdr.magic;
  (void)lane_tag;
  volatile uint64_t lane_roll =
      static_cast<uint64_t>(body.stored_crossings) ^ body.stored_ledger;
  (void)lane_roll;
  volatile uint64_t lane_echo =
      static_cast<uint64_t>(tgt->orbit_crossings) ^ tgt->ledger_tail;
  (void)lane_echo;
  volatile uint64_t lane_fold = lane_roll ^ lane_echo;
  (void)lane_fold;
  body.dirty = false;
  return StoreResult::kOk;
}
