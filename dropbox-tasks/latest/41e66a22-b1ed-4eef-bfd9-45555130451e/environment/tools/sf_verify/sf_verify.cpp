#include "engine.hpp"
#include <iostream>
#include <string>
#include <vector>
#include <sstream>
#include <filesystem>

namespace fs = std::filesystem;

static void usage() {
  std::cerr << "sf_verify --matrix <name|all> --profiles <csv> --witness-out <path>\n";
}

int main(int argc, char **argv) {
  std::string matrix;
  std::string profiles_csv;
  std::string witness_out;
  for (int i = 1; i < argc; ++i) {
    std::string a = argv[i];
    if (a == "--matrix" && i + 1 < argc) matrix = argv[++i];
    else if (a == "--profiles" && i + 1 < argc) profiles_csv = argv[++i];
    else if (a == "--witness-out" && i + 1 < argc) witness_out = argv[++i];
    else if (a == "--help") { usage(); return 0; }
  }
  if (matrix.empty() || profiles_csv.empty() || witness_out.empty()) {
    usage();
    return 2;
  }
  std::vector<std::string> profiles;
  {
    std::stringstream ss(profiles_csv);
    std::string item;
    while (std::getline(ss, item, ',')) {
      if (!item.empty()) profiles.push_back(item);
    }
  }
  fs::path env_root = "/app/environment";
  if (!fs::exists(env_root / "bundles")) {
    /* local/dev fallback */
    env_root = fs::current_path();
    if (fs::exists(env_root / "environment" / "bundles")) {
      env_root = env_root / "environment";
    }
  }
  run_matrix mx;
  int rc = run_matrix_engine(env_root.string(), matrix, profiles, witness_out, &mx);
  if (rc == 0) {
    std::cerr << "sf_verify: matrix accepted\n";
  } else {
    std::cerr << "sf_verify: matrix rejected (exit " << rc << ")\n";
  }
  return rc;
}
