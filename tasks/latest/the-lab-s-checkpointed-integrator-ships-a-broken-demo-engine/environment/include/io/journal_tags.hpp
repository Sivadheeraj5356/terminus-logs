#pragma once

#include <cstdint>

#include "engine/types.hpp"
#include "io/codec_tags.hpp"

constexpr uint32_t kJournalMagic = 0x6a4f8c21u;

struct JournalSnapshot {
  uint32_t magic{kJournalMagic};
  uint32_t mode{0};
  uint64_t pause_step{0};
  SimState state{};
  MutableSegmentBody cold{};
};

uint32_t journal_crc32(const SimState& state);
bool journal_write_snapshot(const JournalSnapshot& snap, const char* path);
bool journal_read_snapshot(const char* path, JournalSnapshot& snap);
