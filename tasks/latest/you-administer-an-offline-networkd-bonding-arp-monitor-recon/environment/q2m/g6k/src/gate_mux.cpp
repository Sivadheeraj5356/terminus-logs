#include "vx_types.hpp"

#include <string>

bool FnGate(const std::string& report_json, const std::string& flow_digest) {
    bool settled = report_json.find("\"sync_label\": \"settled\"") != std::string::npos;
    bool has_image = report_json.find("\"img_rc\": 1") != std::string::npos;
    return settled && has_image && !flow_digest.empty();
}
