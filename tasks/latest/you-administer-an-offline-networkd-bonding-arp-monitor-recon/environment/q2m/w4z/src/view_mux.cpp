#include "vx_types.hpp"

#include <string>

std::pair<std::string, bool> emit_lane_view(const std::string& report_json) {
    bool settled = report_json.find("\"sync_label\": \"settled\"") != std::string::npos;
    bool has_image = report_json.find("\"img_rc\": 1") != std::string::npos;
    if (settled && has_image) {
        return {"settled", true};
    }
    return {"pending", false};
}
