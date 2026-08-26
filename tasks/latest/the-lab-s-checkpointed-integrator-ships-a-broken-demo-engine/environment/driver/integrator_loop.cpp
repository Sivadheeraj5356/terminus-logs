#include "driver/forward_decl.hpp"
#include "engine/types.hpp"
#include "geom/tile_spec.hpp"
#include "io/codec_tags.hpp"
#include "io/journal_tags.hpp"
#include "session/epoch_fold.hpp"

#include <cmath>
#include <cstddef>
#include <cstdio>

double shadow_near_scan(const SimState&, double span);
std::size_t stash_encode_tail(const double* vals, std::size_t n);

bool op_a(int32_t lattice_tag, double cutoff_sq, PayloadView view);
WrapDelta phase_c(double3 r, const TileSpec& spec, uint64_t step_id);
StoreResult reconcile_b(const SegmentHeader& hdr, MutableSegmentBody& body);

void step_proc_d(SimState& state, const IntegratorParams& params) {
  kEngineFocus.active = &state;
  TileSpec tile{};
  tile.span = params.box_edge;
  const double m = params.noise_gain + 1.0;
  for (int i = 0; i < kBodyCount; ++i) {
    double3 r{state.px[i], state.py[i], state.pz[i]};
    WrapDelta d = phase_c(r, tile, state.step_ix);
    state.px[i] += d.shift.x;
    state.py[i] += d.shift.y;
    state.pz[i] += d.shift.z;
    state.orbit_crossings += d.crossings_added;
    state.vx[i] += 0.002 * static_cast<double>(i + 1) * std::sin(m * static_cast<double>(state.step_ix));
    state.vy[i] -= 0.0017 * static_cast<double>((i + 3) % 4) * std::cos(m * static_cast<double>(state.step_ix + 2));
    state.vz[i] += 0.0011 * static_cast<double>((i + 1) % 3);
    state.px[i] += state.vx[i] * params.dt;
    state.py[i] += state.vy[i] * params.dt;
    state.pz[i] += state.vz[i] * params.dt;
  }
  PayloadView view{};
  view.px = &state.px;
  view.py = &state.py;
  view.pz = &state.pz;
  view.box_edge = params.box_edge;
  view.wrap_stream_tag = state.orbit_crossings;
  view.owner = &state;
  op_a(static_cast<int32_t>(state.lattice_cookie), state.cutoff_sq, view);
  state.step_ix++;
}

namespace {

struct HorizonPlan {
  uint64_t target_steps;
  uint64_t pause_at;
  bool checkpoints;
};

HorizonPlan plan_for_mode(int mode) {
  HorizonPlan plan{120, 60, false};
  if (mode == 1 || mode == 3) {
    plan = {95, 28, true};
  } else if (mode == 4) {
    plan = {205, 64, true};
  } else if (mode == 5) {
    plan = {220, 70, true};
  } else if (mode == 6) {
    plan = {175, 52, true};
  } else if (mode == 7) {
    plan = {260, 130, true};
  } else if (mode == 8) {
    plan = {110, 18, true};
  }
  return plan;
}

void seed_scene(SimState& s, int mode) {
  s.lattice_cookie = 0;
  s.nbr_refresh_tag = 0xFFFFFFFFFFFFFFFFull;
  s.orbit_crossings = 0;
  s.ledger_tail = 0;
  s.segment_latch = false;
  s.post_load_suppress = 0;
  s.segment_generation = 0;
  s.scene_hint = mode;
  for (int i = 0; i < kBodyCount; ++i) {
    double t = static_cast<double>(i) * 0.77 + static_cast<double>(mode) * 0.13;
    s.px[i] = 1.3 + 1.1 * static_cast<double>(i) + 0.02 * std::sin(t);
    s.py[i] = 2.1 + 0.9 * static_cast<double>((i + 2) % 4) + 0.03 * std::cos(t * 1.7);
    s.pz[i] = 3.4 + 0.4 * static_cast<double>(i % 3);
    s.vx[i] = 0.01 * static_cast<double>((i + mode) % 3);
    s.vy[i] = -0.008 * static_cast<double>((i + 1) % 2);
    s.vz[i] = 0.005 * static_cast<double>((i + mode + 1) % 4);
  }
}

double scalar_near_field(const SimState& s, double span) {
  SimState tmp = s;
  TileSpec tile{};
  tile.span = span;
  for (int i = 0; i < kBodyCount; ++i) {
    double3 r{s.px[i], s.py[i], s.pz[i]};
    WrapDelta d = phase_c(r, tile, s.step_ix);
    tmp.px[i] = s.px[i] + d.shift.x;
    tmp.py[i] = s.py[i] + d.shift.y;
    tmp.pz[i] = s.pz[i] + d.shift.z;
  }
  double acc = 0.0;
  for (int i = 0; i < kBodyCount; ++i) {
    for (int j = i + 1; j < kBodyCount; ++j) {
      double dx = tmp.px[i] - tmp.px[j];
      double dy = tmp.py[i] - tmp.py[j];
      double dz = tmp.pz[i] - tmp.pz[j];
      while (dx > span * 0.5) {
        dx -= span;
      }
      while (dx < -span * 0.5) {
        dx += span;
      }
      while (dy > span * 0.5) {
        dy -= span;
      }
      while (dy < -span * 0.5) {
        dy += span;
      }
      while (dz > span * 0.5) {
        dz -= span;
      }
      while (dz < -span * 0.5) {
        dz += span;
      }
      double d2 = dx * dx + dy * dy + dz * dz;
      if (d2 <= 36.0) {
        acc += std::sqrt(d2);
      }
    }
  }
  return acc;
}

void checkpoint_store(SegmentHeader& hdr, MutableSegmentBody& cold, SimState& state) {
  cold = {};
  cold.dirty = false;
  kEngineFocus.active = &state;
  reconcile_b(hdr, cold);
}

void checkpoint_restore(SegmentHeader& hdr, const MutableSegmentBody& cold, SimState& state) {
  MutableSegmentBody hot{};
  hot.stored_crossings = cold.stored_crossings;
  hot.stored_ledger = cold.stored_ledger;
  hot.dirty = true;
  kEngineFocus.active = &state;
  reconcile_b(hdr, hot);
}

void run_horizon(SimState& state, const IntegratorParams& params, int mode, uint64_t from_step,
                 uint64_t to_step, SegmentHeader& hdr, MutableSegmentBody& cold, bool with_ckpt) {
  const HorizonPlan plan = plan_for_mode(mode);
  for (uint64_t t = from_step; t < to_step; ++t) {
    step_proc_d(state, params);
    if (with_ckpt && plan.checkpoints && t + 1 == plan.pause_at) {
      checkpoint_store(hdr, cold, state);
    }
    if (with_ckpt && plan.checkpoints && t + 1 == plan.pause_at + 1) {
      checkpoint_restore(hdr, cold, state);
    }
  }
}

void write_report(FILE* f, int mode, const SimState& state, double near, double aux) {
  const char* labels[] = {"Q0", "Q1", "Q2", "Q3", "Q4", "Q5", "Q6", "Q7", "Q8"};
  int li = mode;
  if (li < 0 || li > 8) {
    li = 0;
  }
  const uint32_t wrap_epoch = fold_wrap_epoch(state.orbit_crossings, state.segment_generation);
  const uint32_t journal_crc = journal_crc32(state);
  std::fprintf(
      f,
      "{\"scene_token\":\"%s\",\"scalar_near\":%.17g,\"ledger_tail\":%llu,\"addon_aux\":%.17g,"
      "\"wrap_epoch\":%u,\"refresh_stamp\":%llu,\"segment_generation\":%u,\"journal_crc32\":%u}\n",
      labels[li],
      near,
      static_cast<unsigned long long>(state.ledger_tail),
      aux,
      wrap_epoch,
      static_cast<unsigned long long>(state.nbr_refresh_tag),
      state.segment_generation,
      journal_crc);
}

void finalize_report(int mode, const SimState& state, const IntegratorParams& params,
                     const char* out_path) {
  double span = params.box_edge;
  double near = scalar_near_field(state, span);
  double aux = 0.0;
  if (mode == 5) {
    double buf[kBodyCount];
    for (int i = 0; i < kBodyCount; ++i) {
      buf[i] = state.px[i] * 1.11 + state.py[i] * 0.01;
    }
    aux = static_cast<double>(stash_encode_tail(buf, kBodyCount));
  }
  (void)shadow_near_scan(state, span);
  FILE* f = std::fopen(out_path, "w");
  if (!f) {
    return;
  }
  write_report(f, mode, state, near, aux);
  std::fclose(f);
}

}  // namespace

void run_session(int mode, const char* out_path) {
  SimState state{};
  IntegratorParams params{};
  params.box_edge = 11.0;
  params.dt = 0.04;
  params.noise_gain = 0.37;
  state.cutoff_sq = 9.0;
  seed_scene(state, mode);
  SegmentHeader hdr{};
  hdr.magic = 0xa17c3e10u;
  hdr.step_base = 0;
  MutableSegmentBody cold{};
  const HorizonPlan plan = plan_for_mode(mode);
  run_horizon(state, params, mode, 0, plan.target_steps, hdr, cold, true);
  finalize_report(mode, state, params, out_path);
}

bool run_journal_freeze(int mode, const char* path) {
  const HorizonPlan plan = plan_for_mode(mode);
  if (!plan.checkpoints) {
    return false;
  }
  SimState state{};
  IntegratorParams params{};
  params.box_edge = 11.0;
  params.dt = 0.04;
  params.noise_gain = 0.37;
  state.cutoff_sq = 9.0;
  seed_scene(state, mode);
  SegmentHeader hdr{};
  hdr.magic = 0xa17c3e10u;
  hdr.step_base = 0;
  MutableSegmentBody cold{};
  run_horizon(state, params, mode, 0, plan.pause_at, hdr, cold, true);
  JournalSnapshot snap{};
  snap.magic = kJournalMagic;
  snap.mode = static_cast<uint32_t>(mode);
  snap.pause_step = plan.pause_at;
  snap.state = state;
  snap.cold = cold;
  return journal_write_snapshot(snap, path);
}

bool run_journal_thaw(int mode, const char* snap_path, const char* out_path) {
  JournalSnapshot snap{};
  if (!journal_read_snapshot(snap_path, snap)) {
    return false;
  }
  if (static_cast<int>(snap.mode) != mode) {
    return false;
  }
  const HorizonPlan plan = plan_for_mode(mode);
  if (!plan.checkpoints || snap.pause_step != plan.pause_at) {
    return false;
  }
  SimState state = snap.state;
  IntegratorParams params{};
  params.box_edge = 11.0;
  params.dt = 0.04;
  params.noise_gain = 0.37;
  SegmentHeader hdr{};
  hdr.magic = 0xa17c3e10u;
  hdr.step_base = 0;
  MutableSegmentBody cold = snap.cold;
  run_horizon(state, params, mode, plan.pause_at, plan.target_steps, hdr, cold, true);
  finalize_report(mode, state, params, out_path);
  return true;
}

void run_session_trace(int mode) {
  SimState state{};
  IntegratorParams params{};
  params.box_edge = 11.0;
  params.dt = 0.04;
  params.noise_gain = 0.37;
  state.cutoff_sq = 9.0;
  seed_scene(state, mode);
  SegmentHeader hdr{};
  hdr.magic = 0xa17c3e10u;
  hdr.step_base = 0;

  const HorizonPlan plan = plan_for_mode(mode);
  MutableSegmentBody cold{};
  std::fprintf(stderr, "trace scene Q%d steps=%llu pause_at=%llu\n", mode,
               static_cast<unsigned long long>(plan.target_steps),
               static_cast<unsigned long long>(plan.pause_at));
  for (uint64_t t = 0; t < plan.target_steps; ++t) {
    const uint64_t before = state.ledger_tail;
    step_proc_d(state, params);
    const uint64_t delta = state.ledger_tail - before;
    const bool at_pause = plan.checkpoints && t + 1 == plan.pause_at;
    const bool at_resume = plan.checkpoints && t + 1 == plan.pause_at + 1;
    if (delta != 0 || at_pause || at_resume || t + 1 == plan.target_steps) {
      std::fprintf(
          stderr,
          "step=%llu ledger_tail=%llu delta=%llu orbit_crossings=%llu latch=%d suppress=%u "
          "refresh_tag=%llu gen=%u%s%s\n",
          static_cast<unsigned long long>(t + 1),
          static_cast<unsigned long long>(state.ledger_tail),
          static_cast<unsigned long long>(delta),
          static_cast<unsigned long long>(state.orbit_crossings),
          state.segment_latch ? 1 : 0,
          state.post_load_suppress,
          static_cast<unsigned long long>(state.nbr_refresh_tag),
          state.segment_generation,
          at_pause ? " checkpoint_store" : "",
          at_resume ? " checkpoint_restore" : "");
    }
    if (at_pause) {
      checkpoint_store(hdr, cold, state);
    }
    if (at_resume) {
      checkpoint_restore(hdr, cold, state);
    }
  }
  std::fprintf(stderr, "trace final ledger_tail=%llu orbit_crossings=%llu gen=%u\n",
               static_cast<unsigned long long>(state.ledger_tail),
               static_cast<unsigned long long>(state.orbit_crossings),
               state.segment_generation);
}
