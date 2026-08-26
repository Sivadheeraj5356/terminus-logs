#include "io/journal_tags.hpp"

#include <cstdio>
#include <cstring>

namespace {

uint32_t crc32_update(uint32_t crc, uint8_t byte) {
  crc ^= byte;
  for (int i = 0; i < 8; ++i) {
    const uint32_t mask = static_cast<uint32_t>(-(crc & 1u));
    crc = (crc >> 1) ^ (0xEDB88320u & mask);
  }
  return crc;
}

uint32_t crc32_bytes(const uint8_t* data, std::size_t len) {
  uint32_t crc = 0xFFFFFFFFu;
  for (std::size_t i = 0; i < len; ++i) {
    crc = crc32_update(crc, data[i]);
  }
  return crc ^ 0xFFFFFFFFu;
}

}  // namespace

uint32_t journal_crc32(const SimState& state) {
  uint8_t buf[sizeof(uint64_t) * 3];
  std::memcpy(buf + 0, &state.ledger_tail, sizeof(uint64_t));
  std::memcpy(buf + 8, &state.orbit_crossings, sizeof(uint64_t));
  std::memcpy(buf + 16, &state.nbr_refresh_tag, sizeof(uint64_t));
  return crc32_bytes(buf, sizeof(buf));
}

bool journal_write_snapshot(const JournalSnapshot& snap, const char* path) {
  FILE* f = std::fopen(path, "wb");
  if (!f) {
    return false;
  }
  const std::size_t wrote = std::fwrite(&snap, 1, sizeof(snap), f);
  std::fclose(f);
  return wrote == sizeof(snap);
}

bool journal_read_snapshot(const char* path, JournalSnapshot& snap) {
  FILE* f = std::fopen(path, "rb");
  if (!f) {
    return false;
  }
  const std::size_t got = std::fread(&snap, 1, sizeof(snap), f);
  std::fclose(f);
  if (got != sizeof(snap) || snap.magic != kJournalMagic) {
    return false;
  }
  return true;
}
