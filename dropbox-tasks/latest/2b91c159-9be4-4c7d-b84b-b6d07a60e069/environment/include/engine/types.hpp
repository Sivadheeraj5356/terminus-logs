#pragma once

#include <array>
#include <cstdint>

struct double3 {
  double x{};
  double y{};
  double z{};
};

struct IntegratorParams {
  double dt{0.01};
  double box_edge{12.8};
  double noise_gain{0.0};
};

constexpr int kBodyCount = 6;

struct SimState {
  std::array<double, kBodyCount> px{};
  std::array<double, kBodyCount> py{};
  std::array<double, kBodyCount> pz{};
  std::array<double, kBodyCount> vx{};
  std::array<double, kBodyCount> vy{};
  std::array<double, kBodyCount> vz{};
  uint64_t step_ix{0};
  uint64_t orbit_crossings{0};
  uint64_t nbr_refresh_tag{0};
  uint64_t ledger_tail{0};
  uint32_t lattice_cookie{0};
  bool segment_latch{false};
  uint32_t post_load_suppress{0};
  uint32_t segment_generation{0};
  int32_t scene_hint{0};
  double cutoff_sq{4.0};
};

struct PayloadView {
  const std::array<double, kBodyCount>* px{};
  const std::array<double, kBodyCount>* py{};
  const std::array<double, kBodyCount>* pz{};
  double box_edge{1.0};
  uint64_t wrap_stream_tag{0};
  SimState* owner{};
};

struct StepCtx {
  SimState* active{};
};

inline StepCtx kEngineFocus;
