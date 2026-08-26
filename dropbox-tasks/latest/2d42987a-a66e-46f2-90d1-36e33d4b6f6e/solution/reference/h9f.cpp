#include "h9_stage.hpp"

#include <cstdlib>
#include <cstring>
#include <fstream>
#include <string>
#include <vector>

static std::string env_root() {
    const char* v = std::getenv("WG_ENV_ROOT");
    return v ? std::string(v) : "/app/environment";
}

static bool witness_covers_traces(const char* trace_root) {
    std::ifstream traces(std::string(trace_root) + "/phase.jsonl");
    if (!traces) return false;
    std::string text((std::istreambuf_iterator<char>(traces)), std::istreambuf_iterator<char>());
    return text.find("\"phase\": \"epoch\"") != std::string::npos &&
           text.find("\"phase\": \"mux\"") != std::string::npos &&
           text.find("\"phase\": \"mark\"") != std::string::npos;
}

static bool witness_covers_bind_material(const std::string& audit_text) {
    std::ifstream wit(env_root() + "/w8g/staged/w8_chain.bin");
    if (!wit) return false;
    std::string witness((std::istreambuf_iterator<char>(wit)), std::istreambuf_iterator<char>());
    if (witness.empty()) return false;
    const std::string key = "\"bind_hex\": \"";
    size_t pos = 0;
    bool saw = false;
    while ((pos = audit_text.find(key, pos)) != std::string::npos) {
        pos += key.size();
        if (pos + 16 > audit_text.size()) return false;
        std::string hex = audit_text.substr(pos, 16);
        saw = true;
        if (witness.find(hex) == std::string::npos) return false;
    }
    return saw;
}

int fn_h9(const char* audit_path, const char* trace_root, char* label_out, size_t label_cap) {
    std::string label = "drift";
    bool json_settled = false;
    std::string audit_text;
    {
        std::ifstream in(audit_path);
        audit_text.assign((std::istreambuf_iterator<char>(in)), std::istreambuf_iterator<char>());
        json_settled = audit_text.find("\"conv_label\": \"settled\"") != std::string::npos;
    }
    if (json_settled && witness_covers_traces(trace_root) &&
        witness_covers_bind_material(audit_text)) {
        label = "settled";
    }
    if (label_out && label_cap > 0) {
        std::strncpy(label_out, label.c_str(), label_cap - 1);
        label_out[label_cap - 1] = '\0';
    }
    return label == "settled" ? 1 : 0;
}
