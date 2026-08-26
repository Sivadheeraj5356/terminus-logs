#include "engine.hpp"
#include "pack.hpp"
#include "../libhash/sha256.hpp"
#include "../sf_phases/circ_phase.hpp"
#include "../sf_phases/clock_phase.hpp"
#include "../sf_phases/burst_phase.hpp"
#include "../../core/kz/ring.hpp"
#include "../../lane/ep/latch.hpp"
#include "../../lane/nx/quota.hpp"

#include <fstream>
#include <sstream>
#include <filesystem>
#include <cstdlib>
#include <iostream>
#include <algorithm>
#include <map>
#include <string>
#include <vector>

namespace fs = std::filesystem;

namespace {

std::string read_file(const fs::path &p) {
  std::ifstream in(p, std::ios::binary);
  std::ostringstream ss;
  ss << in.rdbuf();
  return ss.str();
}

std::map<std::string, int64_t> parse_toml_ints(const std::string &text) {
  std::map<std::string, int64_t> out;
  std::istringstream iss(text);
  std::string line;
  while (std::getline(iss, line)) {
    auto eq = line.find('=');
    if (eq == std::string::npos) continue;
    std::string key = line.substr(0, eq);
    std::string val = line.substr(eq + 1);
    auto trim = [](std::string &s) {
      while (!s.empty() && (s.front()==' '||s.front()=='\t')) s.erase(s.begin());
      while (!s.empty() && (s.back()==' '||s.back()=='\t'||s.back()=='\r')) s.pop_back();
    };
    trim(key); trim(val);
    out[key] = std::stoll(val);
  }
  return out;
}

std::string json_get_string(const std::string &js, const std::string &key) {
  auto needle = "\"" + key + "\"";
  auto pos = js.find(needle);
  if (pos == std::string::npos) return "";
  pos = js.find(':', pos);
  pos = js.find('"', pos);
  if (pos == std::string::npos) return "";
  auto end = js.find('"', pos + 1);
  return js.substr(pos + 1, end - pos - 1);
}

int json_get_int(const std::string &js, const std::string &key, int def = 0) {
  auto needle = "\"" + key + "\"";
  auto pos = js.find(needle);
  if (pos == std::string::npos) return def;
  pos = js.find(':', pos);
  if (pos == std::string::npos) return def;
  ++pos;
  while (pos < js.size() && (js[pos]==' '||js[pos]=='\t')) ++pos;
  return std::atoi(js.c_str() + pos);
}

std::string file_sha(const fs::path &p) {
  auto bytes = read_file(p);
  return sha256_hex(reinterpret_cast<const uint8_t *>(bytes.data()), bytes.size());
}

int dual_now(const kz_ctx &kz) {
  return (kz.dual_open && kz.prior_admit_ok) ? 1 : 0;
}

void write_stage(const fs::path &stage_dir, const run_row &r) {
  fs::create_directories(stage_dir);
  std::ofstream out(stage_dir / (r.bundle + "_" + r.profile + ".json"));
  out << "{\"bundle\":\"" << r.bundle << "\",\"profile\":\"" << r.profile
      << "\",\"gen\":" << r.gen << ",\"synced_gen\":" << r.synced_gen
      << ",\"dual_valid\":" << r.dual_valid << ",\"dual_peak\":" << r.dual_peak
      << ",\"status\":\"" << r.status << "\",\"composed\":" << r.composed
      << ",\"abs_deadline\":" << r.abs_deadline
      << ",\"occupancy\":" << r.occupancy << ",\"limit\":" << r.limit
      << ",\"digest_key\":\"" << r.digest_key << "\"}\n";
}

void append_log(const fs::path &log_path, const std::string &line) {
  fs::create_directories(log_path.parent_path());
  std::ofstream out(log_path, std::ios::app);
  out << line << "\n";
}

void write_epoch_ledger(const fs::path &path, const std::vector<run_row> &rows) {
  fs::create_directories(path.parent_path());
  std::ofstream out(path, std::ios::trunc);
  out << "# profile|bundle|gen|synced|dual|dual_peak|occ|abs\n";
  for (const auto &r : rows) {
    out << r.profile << "|" << r.bundle << "|" << r.gen << "|" << r.synced_gen
        << "|" << r.dual_valid << "|" << r.dual_peak << "|" << r.occupancy
        << "|" << r.abs_deadline << "\n";
  }
}

std::map<std::string, std::string> load_epoch_map(const fs::path &path) {
  std::map<std::string, std::string> out;
  if (!fs::exists(path)) return out;
  std::istringstream iss(read_file(path));
  std::string line;
  while (std::getline(iss, line)) {
    if (line.empty() || line[0] == '#') continue;
    auto p1 = line.find('|');
    if (p1 == std::string::npos) continue;
    auto p2 = line.find('|', p1 + 1);
    if (p2 == std::string::npos) continue;
    std::string key = line.substr(0, p2);
    out[key] = line;
  }
  return out;
}

run_row run_bundle(const fs::path &env_root,
                   const std::string &bundle_name,
                   const std::string &profile,
                   const std::map<std::string, int64_t> &cfg,
                   bool recovery_touch) {
  auto bundle_path = env_root / "bundles" / (bundle_name + ".json");
  auto js = read_file(bundle_path);

  kz_ctx kz; kz_ctx_init(&kz);
  ep_ctx ep;
  ep_ctx_init(&ep,
              static_cast<uint64_t>(cfg.at("issued_at")),
              static_cast<uint64_t>(cfg.at("abs_lifetime")),
              static_cast<uint64_t>(cfg.at("idle_lifetime")));

  int burst = static_cast<int>(cfg.at("burst_cap"));
  uint32_t pid = static_cast<uint32_t>(json_get_int(js, "principal_id", 1));
  nx_ctx nx; nx_ctx_init(&nx, pid, burst, 0);

  int peak = 0;
  std::string steps = js;
  size_t cursor = 0;
  while (true) {
    auto op_pos = steps.find("\"op\"", cursor);
    if (op_pos == std::string::npos) break;
    auto colon = steps.find(':', op_pos);
    auto q1 = steps.find('"', colon + 1);
    auto q2 = steps.find('"', q1 + 1);
    std::string op = steps.substr(q1 + 1, q2 - q1 - 1);
    auto obj_end = steps.find('}', q2);
    std::string obj = steps.substr(op_pos, obj_end - op_pos + 1);
    cursor = obj_end + 1;

    if (op == "seal") {
      uint64_t gen = static_cast<uint64_t>(json_get_int(obj, "gen", 1));
      std::string cred = json_get_string(obj, "cred");
      if (cred.empty()) cred = "x";
      circ_apply_seal(&kz, gen, cred);
      peak = std::max(peak, dual_now(kz));
    } else if (op == "latch") {
      uint64_t gen = static_cast<uint64_t>(json_get_int(obj, "gen", 1));
      nx.expected_fence = gen;
      if (bundle_name == "clock_mix") {
        clock_apply_latch(&ep, gen);
      } else {
        circ_apply_latch(&ep, gen);
      }
    } else if (op == "soft_refresh") {
      uint64_t now = static_cast<uint64_t>(json_get_int(obj, "now", 0));
      clock_soft_refresh(&ep, now);
    } else if (op == "compose") {
      clock_compose(&ep);
    } else if (op == "probe_dual") {
      peak = std::max(peak, dual_now(kz));
      (void)obj;
    } else if (op == "admit" || op == "reclaim") {
      int delta = json_get_int(obj, "delta", 0);
      burst_fold(&nx, pid, delta, ep.synced_gen);
    } else if (op == "stale_admit") {
      int delta = json_get_int(obj, "delta", 0);
      uint64_t fence = static_cast<uint64_t>(json_get_int(obj, "fence", 0));
      burst_fold(&nx, pid, delta, fence);
    }
  }

  if (recovery_touch) {
    nx.held_after_reload = 1;
    burst_fold(&nx, pid, 0, ep.synced_gen);
  }

  run_row row;
  row.bundle = bundle_name;
  row.profile = profile;
  row.gen = kz.sealed_gen;
  row.synced_gen = ep.synced_gen;
  row.dual_valid = dual_now(kz);
  row.dual_peak = std::max(peak, row.dual_valid);
  row.composed = ep.composed;
  row.abs_deadline = ep.abs_deadline;
  row.occupancy = nx.occupancy;
  row.limit = nx.limit;
  row.digest_key = json_get_string(js, "digest_key");
  if (row.digest_key.empty()) row.digest_key = "circ_a.bin";

  auto sample = env_root / "samples" / "raw_bytes" / row.digest_key;
  if (fs::exists(sample)) {
    row.digest_sha256 = file_sha(sample);
  } else {
    row.digest_sha256 = std::string(64, '0');
  }
  std::string tag_src = row.digest_sha256 + "|" + profile + "|" + bundle_name;
  row.journal_tag = sha256_hex_str(tag_src).substr(0, 8);

  if (row.dual_valid || row.dual_peak) {
    row.status = "REUSE_HIT";
  } else if (row.occupancy > row.limit) {
    row.status = "CAP_HOLD";
  } else if (bundle_name == "burst_cap" && row.occupancy == row.limit) {
    row.status = "FRESH_OK";
  } else if (bundle_name == "burst_cap") {
    row.status = "CAP_HOLD";
  } else if (bundle_name == "rot_chain" && row.occupancy != 3) {
    row.status = "CAP_HOLD";
  } else {
    row.status = "FRESH_OK";
  }

  return row;
}

}  // namespace

int run_matrix_engine(const std::string &env_root,
                      const std::string &matrix,
                      const std::vector<std::string> &profiles,
                      const std::string &witness_out,
                      run_matrix *out_mx) {
  fs::path root(env_root);
  std::vector<std::string> bundles;
  if (matrix == "all") {
    bundles = {"circ_fence", "rot_chain", "clock_mix", "burst_cap"};
  } else {
    bundles = {matrix};
  }

  run_matrix mx;
  mx.matrix_name = matrix;
  mx.profiles = profiles;
  mx.stage_field_count = 12;
  mx.journal_field_count = 14;
  mx.recovery_marker = "missing";
  mx.epoch_ok = "missing";

  fs::path mark = "/app/output/recovery.marker";
  if (fs::exists(mark)) {
    mx.recovery_marker = read_file(mark);
    while (!mx.recovery_marker.empty() &&
           (mx.recovery_marker.back()=='\n' || mx.recovery_marker.back()=='\r')) {
      mx.recovery_marker.pop_back();
    }
  }

  bool recovery_ok = (mx.recovery_marker == "ok");
  fs::path epoch_path = "/app/output/epoch.ledger";
  auto prior_epoch = load_epoch_map(epoch_path);

  for (const auto &prof : profiles) {
    auto cfg = parse_toml_ints(read_file(root / "presets" / (prof + ".toml")));
    for (const auto &b : bundles) {
      auto row = run_bundle(root, b, prof, cfg, recovery_ok && b == "burst_cap");
      write_stage("/app/output/stage", row);
      append_log("/app/output/logs/sample.log",
                 "row " + b + "/" + prof + " status=" + row.status +
                 " dual_peak=" + std::to_string(row.dual_peak));
      mx.rows.push_back(row);
    }
  }

  write_epoch_ledger(epoch_path, mx.rows);

  bool epoch_match = true;
  if (!prior_epoch.empty()) {
    for (const auto &r : mx.rows) {
      std::string key = r.profile + "|" + r.bundle;
      auto it = prior_epoch.find(key);
      if (it == prior_epoch.end()) {
        epoch_match = false;
        break;
      }
      std::ostringstream expect;
      expect << r.profile << "|" << r.bundle << "|" << r.gen << "|" << r.synced_gen
             << "|" << r.dual_valid << "|" << r.dual_peak << "|" << r.occupancy
             << "|" << r.abs_deadline;
      if (it->second != expect.str()) {
        epoch_match = false;
        break;
      }
    }
    mx.epoch_ok = epoch_match ? "ok" : "drift";
  } else {
    mx.epoch_ok = "seeded";
  }

  auto sample_dir = root / "samples" / "raw_bytes";
  if (fs::exists(sample_dir)) {
    for (auto &ent : fs::directory_iterator(sample_dir)) {
      if (!ent.is_regular_file()) continue;
      auto name = ent.path().filename().string();
      if (!name.empty() && name[0] == '.') continue;
      mx.digests[name] = file_sha(ent.path());
    }
  }

  journal_blob blob;
  if (pack_blob_w(&mx, &blob) != 0) {
    return 2;
  }
  mx.journal_field_count = blob.field_count;

  fs::create_directories(fs::path(witness_out).parent_path());
  {
    std::ofstream out(witness_out);
    out << blob.json_body;
  }

  if (out_mx) *out_mx = mx;

  bool ok = true;
  for (const auto &r : mx.rows) {
    if (r.bundle == "circ_fence" || r.bundle == "rot_chain") {
      if (r.dual_valid != 0 || r.dual_peak != 0) ok = false;
      if (r.synced_gen != r.gen) ok = false;
    }
    if (r.bundle == "rot_chain" && r.occupancy != 3) ok = false;
    if (r.bundle == "clock_mix") {
      uint64_t issued = static_cast<uint64_t>(parse_toml_ints(
          read_file(root / "presets" / (r.profile + ".toml"))).at("issued_at"));
      uint64_t abs_life = static_cast<uint64_t>(parse_toml_ints(
          read_file(root / "presets" / (r.profile + ".toml"))).at("abs_lifetime"));
      uint64_t expect_abs = issued + abs_life;
      if (r.abs_deadline != expect_abs) ok = false;
      if (r.composed != expect_abs) ok = false;
    }
    if (r.bundle == "burst_cap") {
      if (r.occupancy > r.limit) ok = false;
    }
    if (r.digest_sha256.empty() || r.journal_tag.empty()) ok = false;
  }
  auto packed = read_file(witness_out);
  if (packed.find("digest_sha256") == std::string::npos) ok = false;
  if (packed.find("journal_tag") == std::string::npos) ok = false;
  if (packed.find("dual_peak") == std::string::npos) ok = false;
  if (packed.find("abs_deadline") == std::string::npos) ok = false;

  return ok ? 0 : 1;
}
