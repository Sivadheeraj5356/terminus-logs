#include <iostream>
#include <string>

int run_matrix(const std::string& matrix_dir, const std::string& out_path,
               const std::string& env_root);

int main(int argc, char** argv) {
  std::string matrix_dir;
  std::string out_path;
  std::string env_root = "/app/environment";
  for (int i = 1; i < argc; ++i) {
    const std::string arg = argv[i];
    if (arg == "--matrix" && i + 1 < argc) {
      matrix_dir = argv[++i];
    } else if (arg == "--out" && i + 1 < argc) {
      out_path = argv[++i];
    } else if (arg == "--env" && i + 1 < argc) {
      env_root = argv[++i];
    }
  }
  if (matrix_dir.empty() || out_path.empty()) {
    std::cerr << "usage: spw_run --matrix DIR --out FILE [--env ROOT]\n";
    return 2;
  }
  return run_matrix(matrix_dir, out_path, env_root);
}
