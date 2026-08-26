#include "session/epoch_fold.hpp"

#include <cstdint>

namespace {

constexpr uint32_t kFoldPrime = 65521u;
constexpr uint32_t kFoldSalt = 48271u;

}  // namespace

uint32_t fold_wrap_epoch(uint64_t orbit_crossings, uint32_t segment_generation) {
  const uint32_t folded = static_cast<uint32_t>(
      (orbit_crossings * static_cast<uint64_t>(kFoldSalt)) %
      static_cast<uint64_t>(kFoldPrime));
  return folded ^ segment_generation;
}
