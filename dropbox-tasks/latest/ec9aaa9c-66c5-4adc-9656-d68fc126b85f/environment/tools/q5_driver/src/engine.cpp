#include "bind_types.h"
#include "mend_types.h"
#include "pipe_ab.h"
#include "raw_io.h"

#include <algorithm>
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
    auto depth = 0;
    size_t i = start;
    for (; i < blob.size(); ++i) {
      if (blob[i] == '{') {
        ++depth;
      } else if (blob[i] == '}') {
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

void write_json_row(std::ostream& out, const RowBundle& row, bool last) {
  out << "    {\n";
  out << "      \"manifest_id\": \"" << row.mid << "\",\n";
  out << "      \"canonical_byte_digest\": \"" << row.digest_hex << "\",\n";
  out << "      \"unit_tag\": \"" << row.slot_line << "\",\n";
  out << "      \"scope_band\": \"" << row.band << "\",\n";
  out << "      \"cache_epoch\": " << row.cache_epoch << ",\n";
  out << "      \"journal_tip_hex\": \"" << row.journal_tip_hex << "\",\n";
  out << "      \"seal_window\": " << row.window_id << "\n";
  out << "    }" << (last ? "\n" : ",\n");
}

}  // namespace

int run_matrix(const std::string& matrix_dir, const std::string& out_path,
               const std::string& env_root) {
  fs::create_directories("/app/output/stage/journal");
  fs::create_directories("/app/output/stage/cache");

  mend_r4("/app/output/stage");

  const fs::path p7 = fs::path(env_root) / "profiles" / "p7.toml";
  const fs::path p8 = fs::path(env_root) / "profiles" / "p8.toml";
  BandCtx bands[2] = {load_band_ctx(p7.string()), load_band_ctx(p8.string())};

  std::vector<RowBundle> rows;
  int violations = 0;

  for (const auto& set : list_sets(matrix_dir)) {
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
      }
    }
  }

  std::ofstream out(out_path);
  if (!out) {
    return 1;
  }
  out << "{\n  \"violations\": " << violations << ",\n  \"rows\": [\n";
  for (size_t i = 0; i < rows.size(); ++i) {
    write_json_row(out, rows[i], i + 1 == rows.size());
  }
  out << "  ]\n}\n";
  return violations == 0 ? 0 : 3;
}
