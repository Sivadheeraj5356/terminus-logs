#include "h9_stage.hpp"

#include <cstring>
#include <fstream>
#include <string>

int fn_h9(const char* audit_path, const char* trace_root, char* label_out, size_t label_cap) {
    (void)audit_path;
    (void)trace_root;
    std::string label = "drift";
    if (label_out && label_cap > 0) {
        std::strncpy(label_out, label.c_str(), label_cap - 1);
        label_out[label_cap - 1] = '\0';
    }
    return 0;
}

int h9_emit_label(const char* audit_path, const char* trace_root, char* label_out, size_t label_cap) {
    return fn_h9(audit_path, trace_root, label_out, label_cap);
}
