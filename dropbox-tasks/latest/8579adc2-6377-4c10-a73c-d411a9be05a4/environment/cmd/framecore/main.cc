#include <cstdint>
#include <cstdio>
#include <string>

#include "framecore/config/config.h"
#include "framecore/config/config_loader.h"
#include "framecore/transport/frame_dispatcher.h"
#include "framecore/transport/logging_header_listener.h"
#include "framecore/transport/session_manager.h"
#include "replay.h"
#include "script_runner.h"

namespace {

void PrintUsage() {
  std::fprintf(stderr, "usage: framecore <command> [args]\n");
  std::fprintf(stderr, "commands:\n");
  std::fprintf(stderr, "  serve                  start the transport server (placeholder)\n");
  std::fprintf(stderr, "  script <path>          run a scripted session/stream operation file\n");
  std::fprintf(stderr, "  replay <path>          parse a raw wire capture and print a frame summary\n");
  std::fprintf(stderr, "  config-check           print the effective resource limits\n");
}

int RunServe() {
  framecore::Config config;
  framecore::SessionManager manager;
  framecore::Connection* connection =
      manager.OpenConnection("127.0.0.1:0", config.max_session_memory, config.max_header_count,
                              static_cast<int64_t>(config.initial_window_size));
  framecore::LoggingHeaderListener listener;
  framecore::FrameDispatcher dispatcher(connection, &listener);
  (void)dispatcher;
  std::printf("framecore: ready\n");
  return 0;
}

int RunConfigCheck() {
  framecore::Config config = framecore::LoadConfig("");
  std::printf("config.max_session_memory=%zu\n", config.max_session_memory);
  std::printf("config.max_header_count=%zu\n", config.max_header_count);
  std::printf("config.max_concurrent_streams=%zu\n", config.max_concurrent_streams);
  std::printf("config.initial_window_size=%zu\n", config.initial_window_size);
  std::printf("config.max_frame_size=%zu\n", config.max_frame_size);
  return framecore::IsValidConfig(config) ? 0 : 1;
}

}

int main(int argc, char** argv) {
  if (argc < 2) {
    PrintUsage();
    return 2;
  }

  std::string command = argv[1];
  if (command == "serve") {
    return RunServe();
  }
  if (command == "script") {
    if (argc != 3) {
      std::fprintf(stderr, "usage: framecore script <path>\n");
      return 2;
    }
    return framecore::cli::RunScript(argv[2]);
  }
  if (command == "replay") {
    if (argc != 3) {
      std::fprintf(stderr, "usage: framecore replay <path>\n");
      return 2;
    }
    return framecore::cli::RunReplay(argv[2]);
  }
  if (command == "config-check") {
    return RunConfigCheck();
  }

  std::fprintf(stderr, "framecore: unknown command: %s\n", command.c_str());
  return 2;
}
