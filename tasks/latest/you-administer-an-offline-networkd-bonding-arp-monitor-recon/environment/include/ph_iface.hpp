#pragma once

#include "vx_types.hpp"

#include <cstdint>
#include <string>
#include <utility>
#include <vector>

std::pair<uint8_t, std::vector<std::string>> expand_lanes(const std::string& staging_path,
                                                         const std::vector<std::string>& seed_ids);

uint8_t order_gate(const std::vector<uint8_t>& miimon, const std::vector<uint8_t>& targets);

std::string reloc_note_after_flush(uint64_t start_gen);

std::string compile_fingerprint(const std::string& notes, const std::string& triple, int seed);

bool journal_commit(const std::string& path, const std::string& fp, uint64_t epoch,
                    const std::string& digest);
bool journal_ready(const std::string& path, const std::string& fp);
bool journal_ack(const std::string& path, const std::string& fp);
bool journal_acked(const std::string& path);

uint32_t decay_arp_once(uint32_t pending);
uint64_t bump_epoch(uint64_t epoch);
uint32_t merge_arp_pending(uint64_t line_epoch, uint64_t state_epoch,
                           const std::string& line_digest, const std::string& state_digest,
                           uint32_t pending_after_decay, uint32_t fixture_max,
                           uint32_t persisted_pending);

bool gate_report_ok(const std::string& report_json, const std::string& flow_digest);

std::string chain_fold(const std::string& prev);
uint64_t chain_arm(uint64_t settle_epoch);

Row emit_row_phase(const std::string& env_root, const std::string& lane_id, int loc_rc, int img_rc,
                   int lag_code, const std::string& facet);

void sync_q2m_mirrors(const std::string& env_root);

std::string membership_digest_for(const std::vector<std::string>& lanes);
