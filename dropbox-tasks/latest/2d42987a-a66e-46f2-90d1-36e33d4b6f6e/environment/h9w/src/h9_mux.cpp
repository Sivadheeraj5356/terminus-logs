#include "h9_stage.hpp"

#include <cstring>
#include <fstream>
#include <string>

int fn_h9(const char* audit_path, const char* trace_root, char* label_out, size_t label_cap) {
    std::string label = "drift";
    {
        std::ifstream in(audit_path);
        std::string text((std::istreambuf_iterator<char>(in)), std::istreambuf_iterator<char>());
        if (text.find("\"conv_label\": \"settled\"") != std::string::npos) label = "settled";
    }
    (void)trace_root;
    if (label_out && label_cap > 0) {
        std::strncpy(label_out, label.c_str(), label_cap - 1);
        label_out[label_cap - 1] = '\0';
    }
    return label == "settled" ? 1 : 0;
}

int h9_emit_label(const char* audit_path, const char* trace_root, char* label_out, size_t label_cap) {
    return fn_h9(audit_path, trace_root, label_out, label_cap);
}
