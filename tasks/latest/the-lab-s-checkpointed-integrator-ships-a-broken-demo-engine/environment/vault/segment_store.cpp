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
    tgt->segment_generation += 1;
    return StoreResult::kOk;
  }
  tgt->orbit_crossings = body.stored_crossings;
  tgt->ledger_tail = body.stored_ledger;
  tgt->segment_latch = true;
  tgt->post_load_suppress = 6;
  tgt->nbr_refresh_tag = body.stored_crossings - 1;
  body.dirty = false;
  return StoreResult::kOk;
}
