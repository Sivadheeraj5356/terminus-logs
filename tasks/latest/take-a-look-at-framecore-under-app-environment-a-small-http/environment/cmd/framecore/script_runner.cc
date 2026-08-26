#include "script_runner.h"

#include <cstdint>
#include <cstdio>
#include <exception>
#include <fstream>
#include <map>
#include <memory>
#include <sstream>
#include <string>
#include <vector>

#include "framecore/codec/header_field.h"
#include "framecore/status.h"
#include "framecore/transport/session.h"
#include "framecore/transport/stream.h"
#include "framecore/transport/stream_category.h"

namespace framecore {
namespace cli {

namespace {

std::string Unescape(const std::string& token) {
  if (token == "-") {
    return "";
  }
  return token;
}

bool ParseCategory(const std::string& token, HeaderCategory* out) {
  if (token == "headers") {
    *out = HeaderCategory::kHeaders;
    return true;
  }
  if (token == "informational") {
    *out = HeaderCategory::kInformational;
    return true;
  }
  if (token == "trailers") {
    *out = HeaderCategory::kTrailers;
    return true;
  }
  return false;
}

std::string CategoryName(HeaderCategory category) {
  switch (category) {
    case HeaderCategory::kHeaders:
      return "headers";
    case HeaderCategory::kInformational:
      return "informational";
    case HeaderCategory::kTrailers:
      return "trailers";
  }
  return "unknown";
}

std::vector<std::string> Tokenize(const std::string& line) {
  std::istringstream iss(line);
  std::vector<std::string> tokens;
  std::string tok;
  while (iss >> tok) {
    tokens.push_back(tok);
  }
  return tokens;
}

bool ParseU32(const std::string& text, uint32_t* out) {
  try {
    size_t idx = 0;
    unsigned long value = std::stoul(text, &idx);
    if (idx != text.size()) {
      return false;
    }
    *out = static_cast<uint32_t>(value);
    return true;
  } catch (const std::exception&) {
    return false;
  }
}

bool ParseSize(const std::string& text, size_t* out) {
  try {
    size_t idx = 0;
    unsigned long long value = std::stoull(text, &idx);
    if (idx != text.size()) {
      return false;
    }
    *out = static_cast<size_t>(value);
    return true;
  } catch (const std::exception&) {
    return false;
  }
}

}

int RunScript(const std::string& path) {
  std::ifstream in(path);
  if (!in) {
    std::fprintf(stderr, "script_runner: cannot open script %s\n", path.c_str());
    return 2;
  }

  std::unique_ptr<Session> session;
  std::map<uint32_t, Stream*> streams;

  std::string line;
  size_t line_no = 0;
  while (std::getline(in, line)) {
    ++line_no;
    if (line.empty()) {
      continue;
    }
    std::vector<std::string> tok = Tokenize(line);
    if (tok.empty()) {
      continue;
    }
    const std::string& cmd = tok[0];

    if (cmd == "session") {
      size_t max_bytes = 0;
      size_t max_headers = 0;
      if (tok.size() != 3 || !ParseSize(tok[1], &max_bytes) || !ParseSize(tok[2], &max_headers)) {
        std::fprintf(stderr, "script_runner: line %zu: session requires 2 numeric arguments\n",
                     line_no);
        return 2;
      }
      session = std::make_unique<Session>(max_bytes, max_headers);
      streams.clear();
      std::printf("SESSION memory=%zu header_count=%zu max_memory=%zu max_header_count=%zu\n",
                  session->current_session_memory(), session->current_header_count(),
                  session->max_session_memory(), session->max_header_count());
      continue;
    }

    if (!session) {
      std::fprintf(stderr, "script_runner: line %zu: no session has been created yet\n", line_no);
      return 2;
    }

    if (cmd == "stream") {
      uint32_t id = 0;
      if (tok.size() != 2 || !ParseU32(tok[1], &id)) {
        std::fprintf(stderr, "script_runner: line %zu: stream requires 1 numeric argument\n",
                     line_no);
        return 2;
      }
      Stream* s = session->CreateStream(id);
      streams[id] = s;
      std::printf("STREAM id=%u headers_length=%zu header_count=%zu category=%s\n", id,
                  s->current_headers_length(), s->header_count(),
                  CategoryName(s->category()).c_str());
      continue;
    }

    if (cmd == "start_headers") {
      uint32_t id = 0;
      if (tok.size() != 3 || !ParseU32(tok[1], &id)) {
        std::fprintf(stderr, "script_runner: line %zu: start_headers requires 2 arguments\n",
                     line_no);
        return 2;
      }
      auto it = streams.find(id);
      if (it == streams.end()) {
        std::fprintf(stderr, "script_runner: line %zu: unknown stream %u\n", line_no, id);
        return 2;
      }
      HeaderCategory category;
      if (!ParseCategory(tok[2], &category)) {
        std::fprintf(stderr, "script_runner: line %zu: unknown category %s\n", line_no,
                     tok[2].c_str());
        return 2;
      }
      Status st = it->second->StartHeaders(category);
      const char* status_str = st.ok() ? "ok" : (st.ignored() ? "ignored" : "rejected");
      std::printf("START id=%u status=%s category=%s memory=%zu header_count=%zu\n", id,
                  status_str, CategoryName(it->second->category()).c_str(),
                  session->current_session_memory(), session->current_header_count());
      continue;
    }

    if (cmd == "add_header") {
      uint32_t id = 0;
      if (tok.size() != 4 || !ParseU32(tok[1], &id)) {
        std::fprintf(stderr, "script_runner: line %zu: add_header requires 3 arguments\n",
                     line_no);
        return 2;
      }
      auto it = streams.find(id);
      if (it == streams.end()) {
        std::fprintf(stderr, "script_runner: line %zu: unknown stream %u\n", line_no, id);
        return 2;
      }
      std::string name = Unescape(tok[2]);
      std::string value = Unescape(tok[3]);
      size_t before = session->current_session_memory();
      Status st = it->second->AddHeader(name, value);
      size_t after = session->current_session_memory();
      const char* status_str = st.ok() ? "ok" : (st.ignored() ? "ignored" : "rejected");
      std::printf(
          "ADD id=%u status=%s name_len=%zu value_len=%zu charge=%zu memory=%zu "
          "header_count=%zu local_length=%zu\n",
          id, status_str, name.size(), value.size(), after - before, after,
          session->current_header_count(), it->second->current_headers_length());
      continue;
    }

    if (cmd == "flush") {
      uint32_t id = 0;
      if (tok.size() != 2 || !ParseU32(tok[1], &id)) {
        std::fprintf(stderr, "script_runner: line %zu: flush requires 1 argument\n", line_no);
        return 2;
      }
      auto it = streams.find(id);
      if (it == streams.end()) {
        std::fprintf(stderr, "script_runner: line %zu: unknown stream %u\n", line_no, id);
        return 2;
      }
      std::vector<HeaderField> flushed = it->second->FlushHeaders();
      std::printf("FLUSH id=%u count=%zu memory=%zu header_count=%zu local_length=%zu\n", id,
                  flushed.size(), session->current_session_memory(),
                  session->current_header_count(), it->second->current_headers_length());
      continue;
    }

    if (cmd == "destroy") {
      uint32_t id = 0;
      if (tok.size() != 2 || !ParseU32(tok[1], &id)) {
        std::fprintf(stderr, "script_runner: line %zu: destroy requires 1 argument\n", line_no);
        return 2;
      }
      auto it = streams.find(id);
      if (it == streams.end()) {
        std::fprintf(stderr, "script_runner: line %zu: unknown stream %u\n", line_no, id);
        return 2;
      }
      bool destroyed = session->DestroyStream(id);
      streams.erase(it);
      std::printf("DESTROY id=%u destroyed=%s memory=%zu header_count=%zu\n", id,
                  destroyed ? "true" : "false", session->current_session_memory(),
                  session->current_header_count());
      continue;
    }

    std::fprintf(stderr, "script_runner: line %zu: unknown command %s\n", line_no, cmd.c_str());
    return 2;
  }

  if (session) {
    std::printf("FINAL memory=%zu header_count=%zu max_memory=%zu max_header_count=%zu\n",
                session->current_session_memory(), session->current_header_count(),
                session->max_session_memory(), session->max_header_count());
  }
  return 0;
}

}
}
