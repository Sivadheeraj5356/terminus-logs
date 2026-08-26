#include "bind_types.h"
#include "mend_types.h"
#include "pipe_ab.h"
#include "raw_io.h"

#include <algorithm>
#include <cstdint>
#include <cstdlib>
#include <filesystem>
#include <fstream>
#include <sstream>
#include <stdexcept>
#include <string>
#include <vector>

namespace fs = std::filesystem;

namespace {

struct SetFile {
  std::string path;
  std::string stem;
};

std::vector<SetFile> list_sets(const fs::path& matrix_dir) {
  std::vector<SetFile> out;
  for (const auto& entry : fs::directory_iterator(matrix_dir)) {
    if (entry.path().extension() == ".json") {
      out.push_back({entry.path().string(), entry.path().stem().string()});
    }
  }
  std::sort(out.begin(), out.end(),
            [](const SetFile& a, const SetFile& b) { return a.path < b.path; });
  return out;
}

std::string read_all(const fs::path& path) {
  std::ifstream in(path, std::ios::binary);
  if (!in) {
    throw std::runtime_error("snapshot input open fail");
  }
  std::ostringstream ss;
  ss << in.rdbuf();
  return ss.str();
}

uint32_t fnv1a32(const std::string& text) {
  uint32_t h = 2166136261u;
  for (unsigned char c : text) {
    h ^= c;
    h *= 16777619u;
  }
  return h;
}

std::string hex32(uint32_t value) {
  static const char* digits = "0123456789abcdef";
  std::string out(8, '0');
  for (int i = 7; i >= 0; --i) {
    out[static_cast<size_t>(i)] = digits[value & 0xf];
    value >>= 4;
  }
  return out;
}

void add_snapshot_part(std::string* wire, const std::string& name,
                       const std::string& bytes) {
  *wire += std::to_string(name.size()) + ":" + name;
  *wire += std::to_string(bytes.size()) + ":" + bytes;
}

std::string snapshot_id(const fs::path& env_root, const std::vector<SetFile>& sets) {
  std::string wire;
  for (const auto& set : sets) {
    add_snapshot_part(&wire, fs::path(set.path).filename().string(), read_all(set.path));
  }
  for (const auto& relative :
       {fs::path("profiles/p7.toml"), fs::path("profiles/p8.toml"),
        fs::path("fixtures/slices/q46.txt")}) {
    add_snapshot_part(&wire, relative.string(), read_all(env_root / relative));
  }
  return hex32(fnv1a32(wire));
}

bool restore_unchanged_snapshot(const fs::path& stage, const std::string& id,
                                const fs::path& out_path) {
  const fs::path marker = stage / ".snapshot_id";
  const fs::path saved = stage / ".snapshot_certificate.json";
  if (!fs::exists(marker) || !fs::exists(saved)) {
    return false;
  }
  std::string recorded = read_all(marker);
  if (!recorded.empty() && recorded.back() == '\n') {
    recorded.pop_back();
  }
  if (recorded != id) {
    return false;
  }
  if (!out_path.parent_path().empty()) {
    fs::create_directories(out_path.parent_path());
  }
  fs::copy_file(saved, out_path, fs::copy_options::overwrite_existing);
  return true;
}

void commit_snapshot(const fs::path& stage, const std::string& id,
                     const fs::path& out_path) {
  const fs::path saved = stage / ".snapshot_certificate.json";
  const fs::path saved_tmp = stage / ".snapshot_certificate.json.tmp";
  const fs::path marker = stage / ".snapshot_id";
  const fs::path marker_tmp = stage / ".snapshot_id.tmp";

  fs::copy_file(out_path, saved_tmp, fs::copy_options::overwrite_existing);
  fs::rename(saved_tmp, saved);
  {
    std::ofstream out(marker_tmp, std::ios::trunc);
    if (!out) {
      throw std::runtime_error("snapshot marker open fail");
    }
    out << id << "\n";
  }
  fs::rename(marker_tmp, marker);
}

void copy_tree(const fs::path& source, const fs::path& target) {
  fs::create_directories(target);
  if (!fs::exists(source)) {
    return;
  }
  for (const auto& entry : fs::recursive_directory_iterator(source)) {
    const fs::path relative = fs::relative(entry.path(), source);
    const fs::path destination = target / relative;
    if (entry.is_directory()) {
      fs::create_directories(destination);
    } else if (entry.is_regular_file()) {
      fs::create_directories(destination.parent_path());
      fs::copy_file(entry.path(), destination, fs::copy_options::overwrite_existing);
    }
  }
}

void copy_optional(const fs::path& source, const fs::path& target) {
  if (fs::exists(source)) {
    fs::copy_file(source, target, fs::copy_options::overwrite_existing);
  }
}

void recover_transaction(const fs::path& stage) {
  const fs::path txn = stage / ".txn";
  if (!fs::exists(txn)) {
    return;
  }

  fs::remove_all(stage / "journal");
  fs::remove_all(stage / "cache");
  copy_tree(txn / "journal", stage / "journal");
  copy_tree(txn / "cache", stage / "cache");

  for (const auto& name :
       {".snapshot_id", ".snapshot_certificate.json", ".snapshot_id.tmp",
        ".snapshot_certificate.json.tmp"}) {
    fs::remove(stage / name);
  }
  copy_optional(txn / ".snapshot_id", stage / ".snapshot_id");
  copy_optional(txn / ".snapshot_certificate.json",
                stage / ".snapshot_certificate.json");
  fs::remove_all(txn);
}

void begin_transaction(const fs::path& stage) {
  const fs::path txn = stage / ".txn";
  fs::remove_all(txn);
  fs::create_directories(txn);
  copy_tree(stage / "journal", txn / "journal");
  copy_tree(stage / "cache", txn / "cache");
  copy_optional(stage / ".snapshot_id", txn / ".snapshot_id");
  copy_optional(stage / ".snapshot_certificate.json",
                txn / ".snapshot_certificate.json");
}

int injected_failure_row() {
  const char* raw = std::getenv("SPW_FAIL_AFTER_ROWS");
  if (raw == nullptr || *raw == '\0') {
    return 0;
  }
  try {
    const int value = std::stoi(raw);
    return value > 0 ? value : 0;
  } catch (...) {
    return 0;
  }
}

std::vector<RawItem> load_set(const std::string& set_path) {
  std::ifstream in(set_path);
  if (!in) {
    throw std::runtime_error("set open fail");
  }
  std::ostringstream ss;
  ss << in.rdbuf();
  const std::string blob = ss.str();
  std::vector<RawItem> items;
  size_t pos = 0;
  while (true) {
    auto start = blob.find('{', pos);
    if (start == std::string::npos) {
      break;
    }
    int depth = 0;
    bool in_string = false;
    bool escaped = false;
    size_t i = start;
    for (; i < blob.size(); ++i) {
      const char c = blob[i];
      if (in_string) {
        if (escaped) {
          escaped = false;
        } else if (c == '\\') {
          escaped = true;
        } else if (c == '"') {
          in_string = false;
        }
      } else if (c == '"') {
        in_string = true;
      } else if (c == '{') {
        ++depth;
      } else if (c == '}') {
        --depth;
        if (depth == 0) {
          break;
        }
      }
    }
    const std::string obj = blob.substr(start, i - start + 1);
    if (obj.find("\"manifest_id\"") != std::string::npos) {
      const std::string tmp = "/tmp/_one.json";
      std::ofstream tmp_out(tmp);
      tmp_out << obj;
      tmp_out.close();
      items.push_back(load_item_json(tmp));
    }
    pos = i + 1;
  }
  return items;
}

std::string json_string(const std::string& value) {
  static const char* hex = "0123456789abcdef";
  std::string out;
  out.push_back('"');
  for (unsigned char c : value) {
    switch (c) {
      case '"':
        out += "\\\"";
        break;
      case '\\':
        out += "\\\\";
        break;
      case '\b':
        out += "\\b";
        break;
      case '\f':
        out += "\\f";
        break;
      case '\n':
        out += "\\n";
        break;
      case '\r':
        out += "\\r";
        break;
      case '\t':
        out += "\\t";
        break;
      default:
        if (c < 0x20) {
          out += "\\u00";
          out.push_back(hex[c >> 4]);
          out.push_back(hex[c & 0x0f]);
        } else {
          out.push_back(static_cast<char>(c));
        }
    }
  }
  out.push_back('"');
  return out;
}

void write_json_row(std::ostream& out, const RowBundle& row, bool last) {
  out << "    {\n";
  out << "      \"manifest_id\": " << json_string(row.mid) << ",\n";
  out << "      \"canonical_byte_digest\": " << json_string(row.digest_hex) << ",\n";
  out << "      \"unit_tag\": " << json_string(row.slot_line) << ",\n";
  out << "      \"scope_band\": " << json_string(row.band) << ",\n";
  out << "      \"cache_epoch\": " << row.cache_epoch << ",\n";
  out << "      \"journal_tip_hex\": " << json_string(row.journal_tip_hex) << ",\n";
  out << "      \"seal_window\": " << row.window_id << "\n";
  out << "    }" << (last ? "\n" : ",\n");
}

}  // namespace

int run_matrix(const std::string& matrix_dir, const std::string& out_path,
               const std::string& env_root) {
  const fs::path stage = "/app/output/stage";
  recover_transaction(stage);
  fs::create_directories(stage / "journal");
  fs::create_directories(stage / "cache");

  const auto sets = list_sets(matrix_dir);
  const std::string id = snapshot_id(env_root, sets);
  if (restore_unchanged_snapshot(stage, id, out_path)) {
    return 0;
  }

  begin_transaction(stage);
  mend_r4(stage.string());

  const fs::path p7 = fs::path(env_root) / "profiles" / "p7.toml";
  const fs::path p8 = fs::path(env_root) / "profiles" / "p8.toml";
  BandCtx bands[2] = {load_band_ctx(p7.string()), load_band_ctx(p8.string())};

  std::vector<RowBundle> rows;
  int violations = 0;
  const int fail_after = injected_failure_row();

  for (const auto& set : sets) {
    const auto items = load_set(set.path);
    for (auto& ctx : bands) {
      ctx.set_stem = set.stem;
    }
    for (const auto& item : items) {
      for (const auto& ctx : bands) {
        AbBundle ab = run_ab(item, ctx);
        RowBundle row = latch_r3(ab.dig, ctx, item.mid, ab.plan);
        if (row.digest_hex.empty() || row.mid.empty()) {
          ++violations;
        }
        if (row.digest_hex.find('|') != std::string::npos) {
          ++violations;
        }
        if (row.cache_epoch <= 0 || row.journal_tip_hex.size() != 8) {
          ++violations;
        }
        if (row.slot_line.find("rev=") == std::string::npos) {
          ++violations;
        }
        rows.push_back(row);
        if (fail_after > 0 && static_cast<int>(rows.size()) == fail_after) {
          return 86;
        }
      }
    }
  }

  const fs::path final_out = out_path;
  const fs::path temp_out = final_out.string() + ".tmp";
  if (!final_out.parent_path().empty()) {
    fs::create_directories(final_out.parent_path());
  }
  std::ofstream out(temp_out, std::ios::trunc);
  if (!out) {
    return 1;
  }
  out << "{\n  \"violations\": " << violations << ",\n  \"rows\": [\n";
  for (size_t i = 0; i < rows.size(); ++i) {
    write_json_row(out, rows[i], i + 1 == rows.size());
  }
  out << "  ]\n}\n";
  out.close();
  fs::rename(temp_out, final_out);

  if (violations == 0) {
    commit_snapshot(stage, id, final_out);
    fs::remove_all(stage / ".txn");
  }
  return violations == 0 ? 0 : 3;
}
