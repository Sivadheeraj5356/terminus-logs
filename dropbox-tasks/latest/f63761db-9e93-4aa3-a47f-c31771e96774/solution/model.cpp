#include "model.hpp"

#include <algorithm>
#include <cmath>
#include <set>
#include <stdexcept>

namespace {

const mj::Value& field(const mj::Value::Object& obj, const char* key) {
    auto it = obj.find(key);
    if (it == obj.end()) throw std::runtime_error(std::string("missing field: ") + key);
    return it->second;
}

long double number(const mj::Value::Object& obj, const char* key) {
    const auto& v = field(obj, key);
    if (!v.is_number() || !std::isfinite(v.as_number())) throw std::runtime_error(std::string("invalid number: ") + key);
    return static_cast<long double>(v.as_number());
}

std::string string_value(const mj::Value::Object& obj, const char* key) {
    const auto& v = field(obj, key);
    if (!v.is_string()) throw std::runtime_error(std::string("invalid string: ") + key);
    return v.as_string();
}

const mj::Value::Array& array_value(const mj::Value::Object& obj, const char* key) {
    const auto& v = field(obj, key);
    if (!v.is_array()) throw std::runtime_error(std::string("invalid array: ") + key);
    return v.as_array();
}

bool active(const Stop& stop, long double theta, int side) {
    constexpr long double tol = 1e-14L;
    if (stop.sense == "upper") {
        return theta > stop.angle + tol || (std::fabs(theta - stop.angle) <= tol && side > 0);
    }
    return theta < stop.angle - tol || (std::fabs(theta - stop.angle) <= tol && side < 0);
}

}  // namespace

Campaign parse_campaign(const mj::Value& root) {
    if (!root.is_object()) throw std::runtime_error("campaign root must be an object");
    const auto& obj = root.as_object();
    if (string_value(obj, "schema") != "kirigami-campaign-v1") throw std::runtime_error("unsupported schema");

    Campaign c;
    c.campaign = string_value(obj, "campaign");
    if (c.campaign.empty()) throw std::runtime_error("campaign is empty");

    const auto& mv = field(obj, "model");
    if (!mv.is_object()) throw std::runtime_error("model must be an object");
    const auto& mo = mv.as_object();
    c.model.a1 = number(mo, "a1");
    c.model.a3 = number(mo, "a3");
    c.model.a5 = number(mo, "a5");
    c.model.b1 = number(mo, "b1");
    c.model.b3 = number(mo, "b3");
    c.model.theta_min = number(mo, "theta_min");
    c.model.theta_max = number(mo, "theta_max");

    if (std::fabs(c.model.a1) > 50 || std::fabs(c.model.a3) > 50 || c.model.a5 < 1e-4L || c.model.a5 > 50 ||
        c.model.b1 < 1e-4L || c.model.b1 > 50 || c.model.b3 < 0 || c.model.b3 > 20) {
        throw std::runtime_error("model coefficient outside allowed range");
    }
    const long double width = c.model.theta_max - c.model.theta_min;
    if (!(width >= 0.25L && width <= 8.0L)) throw std::runtime_error("invalid theta domain");

    const auto& stops = array_value(mo, "stops");
    if (stops.size() > 8) throw std::runtime_error("too many stops");
    std::set<std::pair<std::string, long double>> seen;
    for (const auto& sv : stops) {
        if (!sv.is_object()) throw std::runtime_error("stop must be an object");
        const auto& so = sv.as_object();
        Stop s;
        s.sense = string_value(so, "sense");
        s.angle = number(so, "angle");
        s.stiffness = number(so, "stiffness");
        if (s.sense != "upper" && s.sense != "lower") throw std::runtime_error("invalid stop sense");
        if (!(s.angle > c.model.theta_min && s.angle < c.model.theta_max)) throw std::runtime_error("stop outside domain");
        if (s.stiffness < 1e-4L || s.stiffness > 100) throw std::runtime_error("invalid stop stiffness");
        if (!seen.emplace(s.sense, s.angle).second) throw std::runtime_error("duplicate stop");
        c.model.stops.push_back(std::move(s));
    }

    const auto& loads = array_value(obj, "equilibrium_loads");
    if (loads.empty() || loads.size() > 64) throw std::runtime_error("invalid equilibrium_loads length");
    for (const auto& v : loads) {
        if (!v.is_number() || !std::isfinite(v.as_number())) throw std::runtime_error("invalid equilibrium load");
        c.equilibrium_loads.push_back(static_cast<long double>(v.as_number()));
    }

    const auto& sweeps = array_value(obj, "sweeps");
    if (sweeps.size() > 8) throw std::runtime_error("too many sweeps");
    std::set<std::string> ids;
    for (const auto& swv : sweeps) {
        if (!swv.is_object()) throw std::runtime_error("sweep must be an object");
        const auto& swo = swv.as_object();
        Sweep sw;
        sw.id = string_value(swo, "id");
        if (sw.id.empty() || !ids.insert(sw.id).second) throw std::runtime_error("invalid sweep id");
        sw.initial_theta = number(swo, "initial_theta");
        const auto& seq = array_value(swo, "loads");
        if (seq.size() < 2 || seq.size() > 256) throw std::runtime_error("invalid sweep length");
        for (const auto& v : seq) {
            if (!v.is_number() || !std::isfinite(v.as_number())) throw std::runtime_error("invalid sweep load");
            sw.loads.push_back(static_cast<long double>(v.as_number()));
        }
        const bool increasing = sw.loads[1] > sw.loads[0];
        if (sw.loads[1] == sw.loads[0]) throw std::runtime_error("sweep loads are not strict");
        for (std::size_t i = 1; i < sw.loads.size(); ++i) {
            if (increasing ? !(sw.loads[i] > sw.loads[i - 1]) : !(sw.loads[i] < sw.loads[i - 1])) {
                throw std::runtime_error("sweep loads are not monotone");
            }
        }
        c.sweeps.push_back(std::move(sw));
    }
    return c;
}

std::vector<int> active_stop_indices(const Model& model, long double theta, int side) {
    std::vector<int> out;
    for (std::size_t i = 0; i < model.stops.size(); ++i) {
        if (active(model.stops[i], theta, side)) out.push_back(static_cast<int>(i));
    }
    return out;
}

long double force(const Model& model, long double theta, int side) {
    long double f = model.a1 * theta + model.a3 * theta * theta * theta + model.a5 * theta * theta * theta * theta * theta;
    for (const auto& s : model.stops) {
        if (active(s, theta, side)) f += s.stiffness * (theta - s.angle);
    }
    return f;
}

long double drive(const Model& model, long double theta) { return model.b1 + model.b3 * theta * theta; }

long double load_curve(const Model& model, long double theta, int side) { return force(model, theta, side) / drive(model, theta); }

long double tangent(const Model& model, long double theta, long double load, int side) {
    const long double t2 = theta * theta;
    long double k = model.a1 + 3 * model.a3 * t2 + 5 * model.a5 * t2 * t2 - 2 * load * model.b3 * theta;
    for (const auto& s : model.stops) {
        if (active(s, theta, side)) k += s.stiffness;
    }
    return k;
}

long double energy(const Model& model, long double theta, long double load) {
    const long double t2 = theta * theta;
    long double e = model.a1 * t2 / 2 + model.a3 * t2 * t2 / 4 + model.a5 * t2 * t2 * t2 / 6;
    e -= load * (model.b1 * theta + model.b3 * theta * t2 / 3);
    for (const auto& s : model.stops) {
        const long double z = theta - s.angle;
        if ((s.sense == "upper" && z > 0) || (s.sense == "lower" && z < 0)) e += s.stiffness * z * z / 2;
    }
    return e;
}

std::string stability_of(const Model& model, long double theta, long double load) {
    const long double left = tangent(model, theta, load, -1);
    const long double right = tangent(model, theta, load, 1);
    if (left > 1e-7L && right > 1e-7L) return "stable";
    if (left < -1e-7L && right < -1e-7L) return "unstable";
    return "neutral";
}
