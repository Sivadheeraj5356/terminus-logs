#pragma once

#include "lockcore/types.hpp"

#include <cmath>
#include <stdexcept>
#include <string>

namespace lockcore {

inline void normalize_neg_zero(double& x) {
    if (x == 0.0) {
        x = 0.0;
    }
}

inline double clamp01(double x) {
    if (x < 0.0) {
        return 0.0;
    }
    if (x > 1.0) {
        return 1.0;
    }
    return x;
}

inline double round_half_even(double value, int places) {
    if (!std::isfinite(value)) {
        throw std::runtime_error("non-finite value in rounding");
    }
    if (value == 0.0) {
        return 0.0;
    }
    const bool neg = value < 0.0;
    double absv = std::fabs(value);
    const double scale = std::pow(10.0, places);
    double scaled = absv * scale;
    double whole = std::floor(scaled);
    double frac = scaled - whole;
    double rounded = whole;
    if (frac > 0.5) {
        rounded = whole + 1.0;
    } else if (frac < 0.5) {
        rounded = whole;
    } else {
        // exactly 0.5: round to even
        if (std::fmod(whole, 2.0) != 0.0) {
            rounded = whole + 1.0;
        }
    }
    double out = rounded / scale;
    if (neg) {
        out = -out;
    }
    normalize_neg_zero(out);
    return out;
}

inline int event_type_rank(EventType t) {
    return static_cast<int>(t);
}

inline std::string event_type_name(EventType t) {
    switch (t) {
        case EventType::StorageCurveRevision:
            return "storage_curve_revision";
        case EventType::BoundaryStage:
            return "boundary_stage";
        case EventType::LinkControl:
            return "link_control";
        case EventType::ExternalInflow:
            return "external_inflow";
        case EventType::VolumeImpulse:
            return "volume_impulse";
    }
    return "unknown";
}

inline EventType parse_event_type(const std::string& s) {
    if (s == "storage_curve_revision") {
        return EventType::StorageCurveRevision;
    }
    if (s == "boundary_stage") {
        return EventType::BoundaryStage;
    }
    if (s == "link_control") {
        return EventType::LinkControl;
    }
    if (s == "external_inflow") {
        return EventType::ExternalInflow;
    }
    if (s == "volume_impulse") {
        return EventType::VolumeImpulse;
    }
    throw std::runtime_error("unknown event_type: " + s);
}

}  // namespace lockcore
