#include <filesystem>
#include <fstream>
#include <iostream>

namespace fs = std::filesystem;

int legacy_scan_main(int argc, char** argv) {
  if (argc < 2) {
    return 2;
  }
  int count = 0;
  for (const auto& entry : fs::directory_iterator(argv[1])) {
    if (entry.path().extension() == ".json") {
      ++count;
    }
  }
  std::cout << count << "\n";
  return 0;
}
