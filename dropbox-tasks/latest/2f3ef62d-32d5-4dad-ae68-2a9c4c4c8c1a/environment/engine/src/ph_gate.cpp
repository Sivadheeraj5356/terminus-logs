#include "ph_iface.hpp"

#include <string>

extern bool FnGate(const std::string& report_json, const std::string& flow_digest);

bool gate_report_ok(const std::string& report_json, const std::string& flow_digest) {
    return FnGate(report_json, flow_digest);
}

std::string membership_digest_for(const std::vector<std::string>& lanes) {
    std::string payload = "bond|";
    for (size_t i = 0; i < lanes.size(); ++i) {
        if (i) payload += ",";
        payload += lanes[i];
    }
    return md5_hex16(payload);
}
