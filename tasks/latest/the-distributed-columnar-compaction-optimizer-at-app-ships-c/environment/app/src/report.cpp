#include "report.h"
#include <sstream>

static std::string json_escape(const std::string& value) {
    std::string out;
    out.reserve(value.size() + 8);
    for (unsigned char c : value) {
        switch (c) {
            case '\\': out += "\\\\"; break;
            case '"': out += "\\\""; break;
            case '\n': out += "\\n"; break;
            case '\r': out += "\\r"; break;
            case '\t': out += "\\t"; break;
            default:
                if (c < 0x20) {
                    static const char hex[] = "0123456789abcdef";
                    out += "\\u00";
                    out.push_back(hex[(c >> 4) & 0xF]);
                    out.push_back(hex[c & 0xF]);
                } else {
                    out.push_back(static_cast<char>(c));
                }
                break;
        }
    }
    return out;
}

std::string plan_to_json(const CompactionPlan& plan) {
    std::ostringstream os;
    os << "{\n";
    os << "  \"fragment_ids\": [";
    for (size_t i = 0; i < plan.fragment_ids.size(); ++i) {
        if (i) os << ", ";
        os << plan.fragment_ids[i];
    }
    os << "],\n";
    os << "  \"row_overlap_lengths\": [";
    for (size_t i = 0; i < plan.row_overlap_lengths.size(); ++i) {
        if (i) os << ", ";
        os << plan.row_overlap_lengths[i];
    }
    os << "],\n";
    os << "  \"total_rows\": " << plan.total_rows << ",\n";
    os << "  \"scan_cost_units\": " << plan.scan_cost_units << ",\n";
    os << "  \"fragmentation_index\": " << plan.fragmentation_index << ",\n";
    os << "  \"replica_consistent\": " << (plan.replica_consistent ? "true" : "false") << ",\n";
    os << "  \"fingerprint\": \"" << json_escape(plan.fingerprint) << "\"\n";
    os << "}\n";
    return os.str();
}

std::string validation_to_json(const ValidationResult& vr) {
    std::ostringstream os;
    os << "{\n  \"ok\": " << (vr.ok ? "true" : "false") << ",\n";
    os << "  \"primary_error\": \"" << vr.primary_error << "\",\n";
    os << "  \"errors\": [";
    for (size_t i = 0; i < vr.errors.size(); ++i) {
        if (i) os << ", ";
        os << "\"" << vr.errors[i] << "\"";
    }
    os << "],\n  \"fingerprint\": \"" << vr.fingerprint << "\"\n}\n";
    return os.str();
}

std::string repair_to_json(const RepairResult& rr) {
    std::ostringstream os;
    os << "{\n  \"ok\": " << (rr.ok ? "true" : "false") << ",\n";
    os << "  \"primary_error\": \"" << rr.primary_error << "\",\n";
    os << "  \"swaps\": " << rr.swaps << ",\n";
    os << "  \"fingerprint\": \"" << rr.fingerprint << "\"\n}\n";
    return os.str();
}
