// Continuous vacuum-interrupter restrike and contact-erosion reconstruction.

#include <algorithm>
#include <cmath>
#include <cstdio>
#include <iostream>
#include <optional>
#include <string>
#include <tuple>
#include <utility>
#include <vector>

namespace {

constexpr double TIME_EPS = 1e-9;
constexpr double VALUE_EPS = 1e-10;

using FieldList = std::vector<std::pair<std::string, std::string>>;

struct Settings {
    double window_start{};
    double window_end{};
    double strike_level{};
    double clear_level{};
    double current_weight{};
    double pressure_weight{};
    double gap_weight{};
    double current_slope{};
    double pressure_slope{};
    double gap_slope{};
    double conditioning_relief{};
    double qualify_sec{};
    double erosion_limit{};
    double start_current{};
    double start_pressure{};
    double start_gap{};
};

struct Reading {
    double time{};
    std::string kind;
    double value{};
    bool carries_value{};
    std::size_t line_order{};
};

struct ReadingBatch {
    double time{};
    std::vector<Reading> readings;
};

struct Quadratic {
    double second{};
    double first{};
    double constant{};

    double at(double x) const {
        return (second * x + first) * x + constant;
    }

    double antiderivative(double x) const {
        return (second / 3.0) * x * x * x + 0.5 * first * x * x + constant * x;
    }

    double area(double begin, double end, double baseline = 0.0) const {
        return antiderivative(end) - antiderivative(begin) - baseline * (end - begin);
    }
};

struct Runtime {
    double current{};
    double pressure{};
    double gap{};
    bool conditioning{};
    bool restrike{};
    bool welded{};
    double qualification{};
    double erosion{};
};

FieldList decode_object(const std::string &text) {
    FieldList fields;
    std::size_t cursor = 0;
    while (cursor < text.size()) {
        cursor = text.find('"', cursor);
        if (cursor == std::string::npos) {
            break;
        }
        const std::size_t key_begin = ++cursor;
        const std::size_t key_end = text.find('"', key_begin);
        if (key_end == std::string::npos) {
            break;
        }
        const std::string key = text.substr(key_begin, key_end - key_begin);
        cursor = text.find(':', key_end + 1);
        if (cursor == std::string::npos) {
            break;
        }
        ++cursor;
        while (cursor < text.size() && (text[cursor] == ' ' || text[cursor] == '\t')) {
            ++cursor;
        }
        std::string value;
        if (cursor < text.size() && text[cursor] == '"') {
            const std::size_t value_begin = ++cursor;
            const std::size_t value_end = text.find('"', value_begin);
            if (value_end == std::string::npos) {
                break;
            }
            value = text.substr(value_begin, value_end - value_begin);
            cursor = value_end + 1;
        } else {
            const std::size_t value_begin = cursor;
            while (cursor < text.size() && text[cursor] != ',' && text[cursor] != '}') {
                ++cursor;
            }
            value = text.substr(value_begin, cursor - value_begin);
            const std::size_t first = value.find_first_not_of(" \t\r\n");
            if (first == std::string::npos) {
                value.clear();
            } else {
                value = value.substr(first, value.find_last_not_of(" \t\r\n") - first + 1);
            }
        }
        fields.emplace_back(key, value);
    }
    return fields;
}

std::optional<std::string> field(const FieldList &fields, const std::string &name) {
    for (const auto &[key, value] : fields) {
        if (key == name) {
            return value;
        }
    }
    return std::nullopt;
}

double number(const FieldList &fields, const std::string &name) {
    const auto value = field(fields, name);
    if (!value.has_value()) {
        return 0.0;
    }
    try {
        return std::stod(*value);
    } catch (...) {
        return 0.0;
    }
}

Settings decode_settings(const std::string &line) {
    const FieldList fields = decode_object(line);
    return Settings{
        number(fields, "window_start"), number(fields, "window_end"),
        number(fields, "strike_level"), number(fields, "clear_level"),
        number(fields, "current_weight"), number(fields, "pressure_weight"),
        number(fields, "gap_weight"), number(fields, "current_slope"),
        number(fields, "pressure_slope"), number(fields, "gap_slope"),
        number(fields, "conditioning_relief"), number(fields, "qualify_sec"),
        number(fields, "erosion_limit"), number(fields, "start_current"),
        number(fields, "start_pressure"), number(fields, "start_gap"),
    };
}

Reading decode_reading(const std::string &line, std::size_t order) {
    const FieldList fields = decode_object(line);
    const auto raw_value = field(fields, "value");
    return Reading{
        number(fields, "t"), field(fields, "kind").value_or(""),
        raw_value.has_value() ? number(fields, "value") : 0.0,
        raw_value.has_value(), order,
    };
}

std::vector<ReadingBatch> make_batches(std::vector<Reading> readings) {
    std::stable_sort(readings.begin(), readings.end(), [](const Reading &left, const Reading &right) {
        if (left.time != right.time) {
            return left.time < right.time;
        }
        return left.line_order < right.line_order;
    });
    std::vector<ReadingBatch> batches;
    for (std::size_t index = 0; index < readings.size();) {
        ReadingBatch batch;
        batch.time = readings[index].time;
        while (index < readings.size() && readings[index].time <= batch.time + TIME_EPS) {
            batch.readings.push_back(readings[index++]);
        }
        std::sort(batch.readings.begin(), batch.readings.end(), [](const Reading &left, const Reading &right) {
            return left.line_order < right.line_order;
        });
        batches.push_back(std::move(batch));
    }
    return batches;
}

std::string render_number(double value) {
    if (std::fabs(value) < 5e-12) {
        value = 0.0;
    }
    if (std::fabs(value - std::round(value)) < 1e-9) {
        char buffer[48];
        std::snprintf(buffer, sizeof(buffer), "%.0f", std::round(value));
        return buffer;
    }
    char buffer[96];
    std::snprintf(buffer, sizeof(buffer), "%.9f", value);
    std::string result(buffer);
    while (!result.empty() && result.back() == '0') {
        result.pop_back();
    }
    if (!result.empty() && result.back() == '.') {
        result.pop_back();
    }
    return result.empty() ? "0" : result;
}

void add_level_roots(const Quadratic &curve, double level, double duration,
                     std::vector<double> &points) {
    const double c = curve.constant - level;
    if (std::fabs(curve.second) <= VALUE_EPS) {
        if (std::fabs(curve.first) > VALUE_EPS) {
            points.push_back(-c / curve.first);
        }
        return;
    }
    double discriminant = curve.first * curve.first - 4.0 * curve.second * c;
    if (discriminant < -VALUE_EPS) {
        return;
    }
    discriminant = std::max(0.0, discriminant);
    const double root = std::sqrt(discriminant);
    points.push_back((-curve.first - root) / (2.0 * curve.second));
    points.push_back((-curve.first + root) / (2.0 * curve.second));
    (void)duration;
}

std::vector<double> threshold_partition(const Quadratic &curve, const Settings &settings,
                                        double duration) {
    std::vector<double> points{0.0, duration};
    add_level_roots(curve, settings.strike_level, duration, points);
    add_level_roots(curve, settings.clear_level, duration, points);
    points.erase(std::remove_if(points.begin(), points.end(), [duration](double value) {
        return value < -TIME_EPS || value > duration + TIME_EPS;
    }), points.end());
    for (double &point : points) {
        point = std::clamp(point, 0.0, duration);
    }
    std::sort(points.begin(), points.end());
    std::vector<double> unique;
    for (double point : points) {
        if (unique.empty() || std::fabs(point - unique.back()) > TIME_EPS) {
            unique.push_back(point);
        }
    }
    if (unique.empty() || unique.front() > TIME_EPS) {
        unique.insert(unique.begin(), 0.0);
    }
    if (duration - unique.back() > TIME_EPS) {
        unique.push_back(duration);
    }
    return unique;
}

class Reconstructor {
  public:
    Reconstructor(Settings settings, std::vector<ReadingBatch> batches)
        : settings_(settings), batches_(std::move(batches)), runtime_{
              settings.start_current, settings.start_pressure, settings.start_gap,
              false, false, false, 0.0, 0.0} {}

    std::vector<std::tuple<std::string, double, double>> run() {
        double cursor = settings_.window_start;
        settle(cursor);
        record_state(cursor);

        for (const ReadingBatch &batch : batches_) {
            if (batch.time < settings_.window_start - TIME_EPS) {
                continue;
            }
            if (batch.time > settings_.window_end + TIME_EPS) {
                break;
            }
            const double event_time = std::clamp(batch.time, cursor, settings_.window_end);
            advance(cursor, event_time - cursor);
            cursor = event_time;
            apply(batch);
            settle(cursor);
            record_state(cursor);
        }

        advance(cursor, settings_.window_end - cursor);
        finish(settings_.window_end);
        return spans_;
    }

  private:
    Settings settings_;
    std::vector<ReadingBatch> batches_;
    Runtime runtime_;
    std::vector<std::tuple<std::string, double, double>> spans_;
    std::optional<std::string> visible_;
    double visible_start_{};

    std::string state_name() const {
        if (runtime_.welded) {
            return "welded";
        }
        if (runtime_.conditioning) {
            return "conditioning";
        }
        if (runtime_.restrike) {
            return "restrike";
        }
        return "normal";
    }

    void record_state(double time) {
        const std::string next = state_name();
        if (!visible_.has_value()) {
            visible_ = next;
            visible_start_ = time;
            return;
        }
        if (*visible_ == next) {
            return;
        }
        if (time - visible_start_ > TIME_EPS) {
            spans_.emplace_back(*visible_, visible_start_, time);
        }
        visible_ = next;
        visible_start_ = time;
    }

    void finish(double end) {
        if (!visible_.has_value()) {
            return;
        }
        if (end - visible_start_ > TIME_EPS) {
            spans_.emplace_back(*visible_, visible_start_, end);
        }
    }

    Quadratic stress_curve() const {
        const double current = runtime_.current;
        const double pressure = runtime_.pressure;
        const double gap = runtime_.gap;
        return Quadratic{
            settings_.current_weight * settings_.current_slope * settings_.current_slope
                + settings_.pressure_weight * settings_.pressure_slope * settings_.pressure_slope,
            2.0 * settings_.current_weight * current * settings_.current_slope
                + 2.0 * settings_.pressure_weight * pressure * settings_.pressure_slope
                - settings_.gap_weight * settings_.gap_slope,
            settings_.current_weight * current * current
                + settings_.pressure_weight * pressure * pressure
                - settings_.gap_weight * gap
                - (runtime_.conditioning ? settings_.conditioning_relief : 0.0),
        };
    }

    void settle(double time) {
        settle_stress(time, stress_curve().constant);
    }

    void settle_stress(double time, double stress) {
        if (runtime_.welded) {
            return;
        }
        if (runtime_.restrike && stress <= settings_.clear_level + VALUE_EPS) {
            runtime_.restrike = false;
            runtime_.qualification = 0.0;
            record_state(time);
        }
        if (!runtime_.restrike) {
            if (stress < settings_.strike_level - VALUE_EPS) {
                runtime_.qualification = 0.0;
            } else if (settings_.qualify_sec <= TIME_EPS) {
                runtime_.restrike = true;
                runtime_.qualification = 0.0;
                record_state(time);
            }
        }
    }

    void latch_weld(double interval_start, const Quadratic &curve,
                    double begin, double end) {
        const double remaining = settings_.erosion_limit - runtime_.erosion;
        const double gained = std::max(0.0, curve.area(begin, end, settings_.clear_level));
        if (gained + VALUE_EPS < remaining) {
            runtime_.erosion += gained;
            return;
        }
        double low = begin;
        double high = end;
        for (int iteration = 0; iteration < 100; ++iteration) {
            const double middle = 0.5 * (low + high);
            if (curve.area(begin, middle, settings_.clear_level) >= remaining) {
                high = middle;
            } else {
                low = middle;
            }
        }
        runtime_.erosion = settings_.erosion_limit;
        runtime_.welded = true;
        runtime_.restrike = false;
        runtime_.qualification = 0.0;
        record_state(interval_start + 0.5 * (low + high));
    }

    void consume_restrike(double interval_start, const Quadratic &curve,
                          double begin, double end) {
        if (runtime_.welded || end - begin <= TIME_EPS) {
            return;
        }
        const double middle_stress = curve.at(0.5 * (begin + end));
        if (middle_stress <= settings_.clear_level + VALUE_EPS) {
            runtime_.restrike = false;
            runtime_.qualification = 0.0;
            record_state(interval_start + begin);
            return;
        }
        latch_weld(interval_start, curve, begin, end);
    }

    void advance(double interval_start, double duration) {
        if (duration <= TIME_EPS) {
            return;
        }
        const Quadratic curve = stress_curve();
        const std::vector<double> points = threshold_partition(curve, settings_, duration);

        for (std::size_t index = 0; index + 1 < points.size(); ++index) {
            const double begin = points[index];
            const double end = points[index + 1];
            settle_stress(interval_start + begin, curve.at(begin));
            if (end - begin <= TIME_EPS || runtime_.welded) {
                continue;
            }
            const double middle_stress = curve.at(0.5 * (begin + end));
            if (runtime_.restrike) {
                consume_restrike(interval_start, curve, begin, end);
                continue;
            }
            if (middle_stress >= settings_.strike_level - VALUE_EPS) {
                const double needed = std::max(0.0, settings_.qualify_sec - runtime_.qualification);
                const double available = end - begin;
                if (needed <= available + TIME_EPS) {
                    const double transition = std::clamp(begin + needed, begin, end);
                    runtime_.qualification = 0.0;
                    runtime_.restrike = true;
                    record_state(interval_start + transition);
                    consume_restrike(interval_start, curve, transition, end);
                } else {
                    runtime_.qualification += available;
                }
            } else {
                runtime_.qualification = 0.0;
            }
        }
        settle_stress(interval_start + points.back(), curve.at(points.back()));

        runtime_.current += settings_.current_slope * duration;
        runtime_.pressure += settings_.pressure_slope * duration;
        runtime_.gap += settings_.gap_slope * duration;
        settle(interval_start + duration);
    }

    void apply(const ReadingBatch &batch) {
        for (const Reading &reading : batch.readings) {
            if (reading.kind == "current_sample" && reading.carries_value) {
                runtime_.current = reading.value;
            } else if (reading.kind == "pressure_sample" && reading.carries_value) {
                runtime_.pressure = reading.value;
            } else if (reading.kind == "gap_sample" && reading.carries_value) {
                runtime_.gap = reading.value;
            } else if (reading.kind == "conditioning_on") {
                runtime_.conditioning = true;
            } else if (reading.kind == "conditioning_off") {
                runtime_.conditioning = false;
            }
        }
    }
};

}  // namespace

int main() {
    std::vector<std::string> lines;
    std::string line;
    while (std::getline(std::cin, line)) {
        if (line.find_first_not_of(" \t\r\n") != std::string::npos) {
            lines.push_back(line);
        }
    }
    if (lines.empty()) {
        std::cout << "[]\n";
        return 0;
    }

    const Settings settings = decode_settings(lines.front());
    if (settings.window_end <= settings.window_start) {
        std::cout << "[]\n";
        return 0;
    }
    std::vector<Reading> readings;
    for (std::size_t index = 1; index < lines.size(); ++index) {
        readings.push_back(decode_reading(lines[index], index - 1));
    }

    Reconstructor reconstructor(settings, make_batches(std::move(readings)));
    const auto spans = reconstructor.run();
    std::cout << '[';
    for (std::size_t index = 0; index < spans.size(); ++index) {
        if (index != 0) {
            std::cout << ',';
        }
        const auto &[state, start, end] = spans[index];
        std::cout << "{\"state\":\"" << state << "\",\"start\":"
                  << render_number(start) << ",\"end\":" << render_number(end) << '}';
    }
    std::cout << "]\n";
    return 0;
}
