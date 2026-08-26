#include <fstream>
#include <iostream>
#include <string>

int collect_payload_meta(const std::string &path, std::string *out_meta) {
  if (!out_meta) {
    return -1;
  }
  std::ifstream in(path, std::ios::binary);
  if (!in) {
    *out_meta = "missing";
    return -2;
  }
  in.seekg(0, std::ios::end);
  auto sz = in.tellg();
  *out_meta = "bytes=" + std::to_string(static_cast<long long>(sz));
  return 0;
}

int main(int argc, char **argv) {
  std::string meta;
  std::string path = argc > 1 ? argv[1] : "";
  int rc = collect_payload_meta(path, &meta);
  std::cout << meta << "\n";
  return rc == 0 ? 0 : 1;
}
