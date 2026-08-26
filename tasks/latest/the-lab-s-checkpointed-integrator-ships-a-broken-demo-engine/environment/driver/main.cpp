#include <cstdlib>
#include <iostream>
#include <string>

extern void run_session(int mode, const char* out_path);
extern void run_session_trace(int mode);
extern bool run_journal_freeze(int mode, const char* path);
extern bool run_journal_thaw(int mode, const char* snap_path, const char* out_path);

namespace {

int parse_mode(const std::string& tok) {
  if (tok.size() >= 2 && tok[0] == 'Q') {
    const char c = tok[1];
    if (c >= '0' && c <= '8') {
      return c - '0';
    }
  }
  return 0;
}

void usage() {
  std::cerr << "usage:\n"
            << "  demo_engine emit <QTOKEN> /path/report.json\n"
            << "  demo_engine trace <QTOKEN>\n"
            << "  demo_engine journal freeze <QTOKEN> /path/snapshot.bin\n"
            << "  demo_engine journal thaw <QTOKEN> /path/snapshot.bin /path/report.json\n";
}

}  // namespace

int main(int argc, char** argv) {
  if (argc < 3) {
    usage();
    return 2;
  }
  const std::string cmd = argv[1];
  if (cmd == "emit") {
    if (argc < 4) {
      usage();
      return 2;
    }
    run_session(parse_mode(argv[2]), argv[3]);
    return 0;
  }
  if (cmd == "trace") {
    run_session_trace(parse_mode(argv[2]));
    return 0;
  }
  if (cmd == "journal") {
    if (argc < 5) {
      usage();
      return 2;
    }
    const std::string sub = argv[2];
    const int mode = parse_mode(argv[3]);
    if (sub == "freeze") {
      if (!run_journal_freeze(mode, argv[4])) {
        return 1;
      }
      return 0;
    }
    if (sub == "thaw" && argc >= 6) {
      if (!run_journal_thaw(mode, argv[4], argv[5])) {
        return 1;
      }
      return 0;
    }
  }
  usage();
  return 2;
}
