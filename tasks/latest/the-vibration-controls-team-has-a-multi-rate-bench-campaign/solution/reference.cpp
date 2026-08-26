#include <algorithm>
#include <cstdint>
#include <filesystem>
#include <fstream>
#include <functional>
#include <iostream>
#include <limits>
#include <map>
#include <optional>
#include <set>
#include <stdexcept>
#include <string>
#include <tuple>
#include <utility>
#include <vector>

#include <boost/multiprecision/cpp_int.hpp>
#include <nlohmann/json.hpp>

using boost::multiprecision::cpp_int;
using json = nlohmann::json;
namespace fs = std::filesystem;

static cpp_int abs_int(cpp_int value) {
    return value < 0 ? -value : value;
}

static cpp_int gcd_int(cpp_int a, cpp_int b) {
    a = abs_int(a);
    b = abs_int(b);
    while (b != 0) {
        cpp_int remainder = a % b;
        a = b;
        b = remainder;
    }
    return a;
}

struct Rat {
    cpp_int n{0};
    cpp_int d{1};

    Rat() = default;
    Rat(long long value) : n(value), d(1) {}
    Rat(cpp_int numerator, cpp_int denominator) : n(std::move(numerator)), d(std::move(denominator)) {
        normalize();
    }

    void normalize() {
        if (d == 0) {
            throw std::runtime_error("zero denominator");
        }
        if (d < 0) {
            n = -n;
            d = -d;
        }
        cpp_int common = gcd_int(n, d);
        if (common != 0) {
            n /= common;
            d /= common;
        }
        if (n == 0) {
            d = 1;
        }
    }

    bool is_zero() const { return n == 0; }
};

static Rat operator+(const Rat& a, const Rat& b) {
    return Rat(a.n * b.d + b.n * a.d, a.d * b.d);
}

static Rat operator-(const Rat& a, const Rat& b) {
    return Rat(a.n * b.d - b.n * a.d, a.d * b.d);
}

static Rat operator-(const Rat& a) {
    return Rat(-a.n, a.d);
}

static Rat operator*(const Rat& a, const Rat& b) {
    return Rat(a.n * b.n, a.d * b.d);
}

static Rat operator/(const Rat& a, const Rat& b) {
    if (b.n == 0) {
        throw std::runtime_error("division by zero");
    }
    return Rat(a.n * b.d, a.d * b.n);
}

struct Cpx {
    Rat real;
    Rat imag;
};

static Cpx operator+(const Cpx& a, const Cpx& b) {
    return {a.real + b.real, a.imag + b.imag};
}

static Cpx operator*(const Cpx& a, const Cpx& b) {
    return {
        a.real * b.real - a.imag * b.imag,
        a.real * b.imag + a.imag * b.real,
    };
}

static Cpx operator/(const Cpx& a, const Cpx& b) {
    Rat scale = b.real * b.real + b.imag * b.imag;
    if (scale.is_zero()) {
        throw std::runtime_error("zero complex denominator");
    }
    return {
        (a.real * b.real + a.imag * b.imag) / scale,
        (a.imag * b.real - a.real * b.imag) / scale,
    };
}

static std::string int_text(const cpp_int& value) {
    return value.convert_to<std::string>();
}

static cpp_int parse_bigint(const std::string& text) {
    if (text.empty()) {
        throw std::runtime_error("empty integer string");
    }
    std::size_t pos = 0;
    bool negative = false;
    if (text[0] == '-') {
        negative = true;
        pos = 1;
    }
    if (pos == text.size()) {
        throw std::runtime_error("invalid integer string");
    }
    if (text[pos] == '0' && pos + 1 != text.size()) {
        throw std::runtime_error("non-canonical integer string");
    }
    cpp_int value = 0;
    for (; pos < text.size(); ++pos) {
        char ch = text[pos];
        if (ch < '0' || ch > '9') {
            throw std::runtime_error("invalid integer string");
        }
        value *= 10;
        value += ch - '0';
    }
    return negative ? -value : value;
}

static void require_exact_keys(const json& value, const std::set<std::string>& keys) {
    if (!value.is_object() || value.size() != keys.size()) {
        throw std::runtime_error("wrong object shape");
    }
    for (const auto& key : keys) {
        if (!value.contains(key)) {
            throw std::runtime_error("missing object field");
        }
    }
}

static Rat parse_rat(const json& value) {
    require_exact_keys(value, {"d", "n"});
    if (!value.at("n").is_string() || !value.at("d").is_string()) {
        throw std::runtime_error("fraction fields must be strings");
    }
    const std::string numerator_text = value.at("n").get<std::string>();
    const std::string denominator_text = value.at("d").get<std::string>();
    Rat result(parse_bigint(numerator_text), parse_bigint(denominator_text));
    if (result.d <= 0 || int_text(result.n) != numerator_text || int_text(result.d) != denominator_text) {
        throw std::runtime_error("fraction is not canonical");
    }
    return result;
}

static json rat_json(const Rat& value) {
    return json{{"n", int_text(value.n)}, {"d", int_text(value.d)}};
}

static long long json_integer(const json& value) {
    if (!value.is_number_integer()) {
        throw std::runtime_error("expected JSON integer");
    }
    return value.get<long long>();
}

static json read_json(const fs::path& path) {
    std::ifstream stream(path);
    if (!stream) {
        throw std::runtime_error("cannot open " + path.string());
    }
    json value;
    stream >> value;
    stream >> std::ws;
    if (!stream.eof()) {
        throw std::runtime_error("trailing content in JSON file");
    }
    return value;
}

static std::vector<fs::path> json_files(const fs::path& directory) {
    if (!fs::is_directory(directory)) {
        throw std::runtime_error("missing directory");
    }
    std::vector<fs::path> files;
    for (const auto& entry : fs::directory_iterator(directory)) {
        if (!entry.is_regular_file() || entry.path().extension() != ".json") {
            throw std::runtime_error("unexpected campaign entry");
        }
        files.push_back(entry.path());
    }
    std::sort(files.begin(), files.end());
    return files;
}

struct Tone {
    std::string id;
    int omega;
};

struct PathModel {
    std::string source;
    std::string probe;
    std::vector<Rat> numerator;
    std::vector<Rat> denominator;
};

struct Bin {
    int id;
    Rat expected_cos;
    Rat expected_sin;
    Rat measured_cos;
    Rat measured_sin;
};

struct ProbeCapture {
    std::string id;
    std::vector<Bin> bins;
};

struct Capture {
    std::string id;
    int sample_rate;
    long long trigger_quarters;
    std::vector<ProbeCapture> probes;
};

struct Campaign {
    std::vector<std::string> sources;
    std::vector<std::string> probes;
    int max_active;
    std::vector<Tone> tones;
    std::map<std::pair<std::string, std::string>, PathModel> paths;
    std::vector<Capture> captures;
};

static std::vector<std::string> parse_string_array(const json& value) {
    if (!value.is_array()) {
        throw std::runtime_error("expected string array");
    }
    std::vector<std::string> result;
    std::set<std::string> seen;
    for (const auto& item : value) {
        if (!item.is_string()) {
            throw std::runtime_error("array member is not a string");
        }
        std::string text = item.get<std::string>();
        auto valid_identifier = [](const std::string& candidate) {
            if (candidate.empty()) {
                return false;
            }
            auto ascii_alnum = [](unsigned char ch) {
                return (ch >= 'A' && ch <= 'Z') || (ch >= 'a' && ch <= 'z') ||
                       (ch >= '0' && ch <= '9');
            };
            if (!ascii_alnum(static_cast<unsigned char>(candidate.front()))) {
                return false;
            }
            for (unsigned char ch : candidate) {
                if (!ascii_alnum(ch) && ch != '.' && ch != '_' && ch != '-') {
                    return false;
                }
            }
            return true;
        };
        if (!valid_identifier(text) || !seen.insert(text).second) {
            throw std::runtime_error("empty or duplicate identifier");
        }
        result.push_back(text);
    }
    std::sort(result.begin(), result.end());
    return result;
}

static std::vector<Rat> parse_polynomial(const json& value) {
    if (!value.is_array() || value.empty()) {
        throw std::runtime_error("invalid polynomial");
    }
    std::vector<Rat> result;
    for (const auto& coefficient : value) {
        result.push_back(parse_rat(coefficient));
    }
    return result;
}

static Campaign load_campaign(const fs::path& root) {
    Campaign campaign;
    json policy = read_json(root / "campaign.json");
    require_exact_keys(policy, {"format", "max_active_sources", "probes", "sources"});
    if (!policy.at("format").is_string() ||
        policy.at("format").get<std::string>() != "harmonic-source-bench/v1") {
        throw std::runtime_error("unknown campaign format");
    }
    campaign.sources = parse_string_array(policy.at("sources"));
    campaign.probes = parse_string_array(policy.at("probes"));
    if (campaign.sources.empty() || campaign.probes.empty()) {
        throw std::runtime_error("source and probe lists must be nonempty");
    }
    long long max_active = json_integer(policy.at("max_active_sources"));
    if (max_active < 0 || max_active > std::numeric_limits<int>::max()) {
        throw std::runtime_error("invalid active-source limit");
    }
    campaign.max_active = static_cast<int>(max_active);

    json source_catalog = read_json(root / "sources.json");
    require_exact_keys(source_catalog, {"sources"});
    if (!source_catalog.at("sources").is_array()) {
        throw std::runtime_error("invalid source catalog");
    }
    std::set<std::string> described_sources;
    for (const auto& row : source_catalog.at("sources")) {
        require_exact_keys(row, {"description", "source_id"});
        if (!row.at("source_id").is_string() || !row.at("description").is_string()) {
            throw std::runtime_error("invalid source catalog row");
        }
        if (!described_sources.insert(row.at("source_id").get<std::string>()).second) {
            throw std::runtime_error("duplicate source description");
        }
    }
    if (described_sources != std::set<std::string>(campaign.sources.begin(), campaign.sources.end())) {
        throw std::runtime_error("source catalog mismatch");
    }

    std::set<std::string> tone_ids;
    for (const auto& file : json_files(root / "tones")) {
        json row = read_json(file);
        require_exact_keys(row, {"omega", "tone_id"});
        if (!row.at("tone_id").is_string()) {
            throw std::runtime_error("invalid tone id");
        }
        std::string tone_id = row.at("tone_id").get<std::string>();
        long long omega = json_integer(row.at("omega"));
        if (parse_string_array(json::array({tone_id})).size() != 1 ||
            omega <= 0 || omega > 1000000 || !tone_ids.insert(tone_id).second) {
            throw std::runtime_error("invalid tone");
        }
        campaign.tones.push_back({tone_id, static_cast<int>(omega)});
    }
    if (campaign.tones.empty()) {
        throw std::runtime_error("empty tone catalog");
    }
    std::sort(campaign.tones.begin(), campaign.tones.end(), [](const Tone& a, const Tone& b) {
        return a.id < b.id;
    });
    if (campaign.max_active >
        static_cast<int>(campaign.tones.size() * campaign.sources.size())) {
        throw std::runtime_error("active-source limit exceeds candidate count");
    }

    std::set<std::string> source_set(campaign.sources.begin(), campaign.sources.end());
    std::set<std::string> probe_set(campaign.probes.begin(), campaign.probes.end());
    for (const auto& file : json_files(root / "paths")) {
        json row = read_json(file);
        require_exact_keys(row, {"denominator", "numerator", "probe_id", "source_id"});
        if (!row.at("source_id").is_string() || !row.at("probe_id").is_string()) {
            throw std::runtime_error("invalid path identity");
        }
        PathModel model{
            row.at("source_id").get<std::string>(),
            row.at("probe_id").get<std::string>(),
            parse_polynomial(row.at("numerator")),
            parse_polynomial(row.at("denominator")),
        };
        if (!source_set.count(model.source) || !probe_set.count(model.probe)) {
            throw std::runtime_error("unknown path endpoint");
        }
        auto key = std::make_pair(model.source, model.probe);
        if (!campaign.paths.emplace(key, std::move(model)).second) {
            throw std::runtime_error("duplicate path");
        }
    }
    if (campaign.paths.size() != campaign.sources.size() * campaign.probes.size()) {
        throw std::runtime_error("incomplete path set");
    }

    std::set<std::string> capture_ids;
    for (const auto& file : json_files(root / "captures")) {
        json row = read_json(file);
        require_exact_keys(row, {"capture_id", "probes", "sample_rate", "trigger_quarters"});
        if (!row.at("capture_id").is_string() || !row.at("probes").is_array()) {
            throw std::runtime_error("invalid capture");
        }
        std::string capture_id = row.at("capture_id").get<std::string>();
        long long sample_rate = json_integer(row.at("sample_rate"));
        long long trigger_quarters = json_integer(row.at("trigger_quarters"));
        if (parse_string_array(json::array({capture_id})).size() != 1 ||
            sample_rate <= 0 || sample_rate > 1000000 ||
            !capture_ids.insert(capture_id).second) {
            throw std::runtime_error("invalid capture identity");
        }
        Capture capture{capture_id, static_cast<int>(sample_rate), trigger_quarters, {}};
        std::set<std::string> capture_probes;
        for (const auto& probe_row : row.at("probes")) {
            require_exact_keys(probe_row, {"bins", "probe_id"});
            if (!probe_row.at("probe_id").is_string() || !probe_row.at("bins").is_array()) {
                throw std::runtime_error("invalid capture probe");
            }
            std::string probe_id = probe_row.at("probe_id").get<std::string>();
            if (!probe_set.count(probe_id) || !capture_probes.insert(probe_id).second) {
                throw std::runtime_error("unknown or duplicate capture probe");
            }
            ProbeCapture probe{probe_id, {}};
            std::set<int> seen_bins;
            for (const auto& bin_row : probe_row.at("bins")) {
                require_exact_keys(bin_row, {"bin", "expected", "measured"});
                int bin_id = static_cast<int>(json_integer(bin_row.at("bin")));
                if (bin_id < 0 || bin_id > capture.sample_rate / 2 || !seen_bins.insert(bin_id).second) {
                    throw std::runtime_error("invalid bin");
                }
                require_exact_keys(bin_row.at("expected"), {"cos", "sin"});
                require_exact_keys(bin_row.at("measured"), {"cos", "sin"});
                probe.bins.push_back(
                    {
                        bin_id,
                        parse_rat(bin_row.at("expected").at("cos")),
                        parse_rat(bin_row.at("expected").at("sin")),
                        parse_rat(bin_row.at("measured").at("cos")),
                        parse_rat(bin_row.at("measured").at("sin")),
                    }
                );
            }
            if (seen_bins.size() != static_cast<std::size_t>(capture.sample_rate / 2 + 1)) {
                throw std::runtime_error("incomplete bin grid");
            }
            std::sort(probe.bins.begin(), probe.bins.end(), [](const Bin& a, const Bin& b) {
                return a.id < b.id;
            });
            capture.probes.push_back(std::move(probe));
        }
        if (capture_probes != probe_set) {
            throw std::runtime_error("incomplete capture probe set");
        }
        std::sort(capture.probes.begin(), capture.probes.end(), [](const ProbeCapture& a, const ProbeCapture& b) {
            return a.id < b.id;
        });
        campaign.captures.push_back(std::move(capture));
    }
    if (campaign.captures.empty()) {
        throw std::runtime_error("empty capture set");
    }
    std::sort(campaign.captures.begin(), campaign.captures.end(), [](const Capture& a, const Capture& b) {
        return a.id < b.id;
    });

    return campaign;
}

static Cpx evaluate_polynomial(const std::vector<Rat>& coefficients, int omega) {
    Cpx result{Rat(0), Rat(0)};
    Cpx jw{Rat(0), Rat(omega)};
    for (auto it = coefficients.rbegin(); it != coefficients.rend(); ++it) {
        result = result * jw + Cpx{*it, Rat(0)};
    }
    return result;
}

static Cpx path_response(const PathModel& model, int omega) {
    return evaluate_polynomial(model.numerator, omega) /
           evaluate_polynomial(model.denominator, omega);
}

static int positive_mod(long long value, int modulus) {
    long long result = value % modulus;
    if (result < 0) {
        result += modulus;
    }
    return static_cast<int>(result);
}

static int trigger_phase(int omega, long long trigger_quarters) {
    return (positive_mod(omega, 4) * positive_mod(trigger_quarters, 4)) % 4;
}

static std::pair<Rat, Rat> rotate_coordinates(const Rat& cosine, const Rat& sine, int quarters) {
    switch (positive_mod(quarters, 4)) {
        case 0: return {cosine, sine};
        case 1: return {sine, -cosine};
        case 2: return {-cosine, -sine};
        default: return {-sine, cosine};
    }
}

struct Fold {
    int bin;
    int sine_sign;
};

static Fold fold_tone(int omega, int sample_rate) {
    int residue = omega % sample_rate;
    int bin = residue;
    int sine_sign = 1;
    if (residue > sample_rate / 2) {
        bin = sample_rate - residue;
        sine_sign = -1;
    }
    if (bin == 0 || (sample_rate % 2 == 0 && bin == sample_rate / 2)) {
        sine_sign = 0;
    }
    return {bin, sine_sign};
}

struct Item {
    Tone tone;
    std::string source;
};

struct Contribution {
    int phase_quarters;
    int bin;
    int sine_sign;
    Rat cosine;
    Rat sine;
};

static Contribution contribution(
    const Campaign& campaign,
    const Item& item,
    const Capture& capture,
    const std::string& probe,
    const Rat& source_cos,
    const Rat& source_sin
) {
    int phase = trigger_phase(item.tone.omega, capture.trigger_quarters);
    auto rotated = rotate_coordinates(source_cos, source_sin, phase);
    const PathModel& model = campaign.paths.at({item.source, probe});
    Cpx h = path_response(model, item.tone.omega);
    Rat output_cos = h.real * rotated.first + h.imag * rotated.second;
    Rat output_sin = h.real * rotated.second - h.imag * rotated.first;
    Fold folded = fold_tone(item.tone.omega, capture.sample_rate);
    return {
        phase,
        folded.bin,
        folded.sine_sign,
        output_cos,
        output_sin * Rat(folded.sine_sign),
    };
}

struct RowKey {
    std::string capture;
    std::string probe;
    int bin;
    int component;
};

static std::vector<RowKey> build_rows(const Campaign& campaign, std::vector<Rat>& rhs) {
    std::vector<RowKey> rows;
    for (const auto& capture : campaign.captures) {
        for (const auto& probe : capture.probes) {
            for (const auto& bin : probe.bins) {
                rows.push_back({capture.id, probe.id, bin.id, 0});
                rhs.push_back(bin.measured_cos - bin.expected_cos);
                rows.push_back({capture.id, probe.id, bin.id, 1});
                rhs.push_back(bin.measured_sin - bin.expected_sin);
            }
        }
    }
    return rows;
}

static std::vector<Item> build_items(const Campaign& campaign) {
    std::vector<Item> items;
    for (const auto& tone : campaign.tones) {
        for (const auto& source : campaign.sources) {
            items.push_back({tone, source});
        }
    }
    std::sort(items.begin(), items.end(), [](const Item& a, const Item& b) {
        return std::tie(a.tone.id, a.source) < std::tie(b.tone.id, b.source);
    });
    return items;
}

static std::vector<Rat> item_column(
    const Campaign& campaign,
    const Item& item,
    bool sine_basis
) {
    std::vector<Rat> values;
    Rat source_cos = sine_basis ? Rat(0) : Rat(1);
    Rat source_sin = sine_basis ? Rat(1) : Rat(0);
    for (const auto& capture : campaign.captures) {
        for (const auto& probe : capture.probes) {
            Contribution value = contribution(
                campaign, item, capture, probe.id, source_cos, source_sin
            );
            for (const auto& bin : probe.bins) {
                if (bin.id == value.bin) {
                    values.push_back(value.cosine);
                    values.push_back(value.sine);
                } else {
                    values.push_back(Rat(0));
                    values.push_back(Rat(0));
                }
            }
        }
    }
    return values;
}

static constexpr long long MODULUS = 1000000007LL;

static long long mod_pow(long long base, long long exponent) {
    long long result = 1;
    while (exponent > 0) {
        if (exponent & 1LL) {
            result = static_cast<long long>(
                (static_cast<unsigned long long>(result) * static_cast<unsigned long long>(base)) %
                static_cast<unsigned long long>(MODULUS)
            );
        }
        base = static_cast<long long>(
            (static_cast<unsigned long long>(base) * static_cast<unsigned long long>(base)) %
            static_cast<unsigned long long>(MODULUS)
        );
        exponent >>= 1LL;
    }
    return result;
}

static long long cpp_mod(const cpp_int& value) {
    cpp_int result = value % MODULUS;
    if (result < 0) {
        result += MODULUS;
    }
    return result.convert_to<long long>();
}

static std::optional<long long> rat_mod(const Rat& value) {
    long long denominator = cpp_mod(value.d);
    if (denominator == 0) {
        return std::nullopt;
    }
    return static_cast<long long>(
        (
            static_cast<unsigned long long>(cpp_mod(value.n)) *
            static_cast<unsigned long long>(mod_pow(denominator, MODULUS - 2))
        ) % static_cast<unsigned long long>(MODULUS)
    );
}

static bool modular_maybe_consistent(
    const std::vector<int>& support,
    const std::vector<std::vector<Rat>>& cosine_columns,
    const std::vector<std::vector<Rat>>& sine_columns,
    const std::vector<Rat>& rhs
) {
    int column_count = static_cast<int>(support.size()) * 2;
    std::vector<std::vector<long long>> matrix(
        rhs.size(), std::vector<long long>(column_count + 1, 0)
    );
    for (std::size_t row = 0; row < rhs.size(); ++row) {
        for (std::size_t item_pos = 0; item_pos < support.size(); ++item_pos) {
            auto cos_value = rat_mod(cosine_columns[support[item_pos]][row]);
            auto sin_value = rat_mod(sine_columns[support[item_pos]][row]);
            auto rhs_value = rat_mod(rhs[row]);
            if (!cos_value || !sin_value || !rhs_value) {
                return true;
            }
            matrix[row][item_pos * 2] = *cos_value;
            matrix[row][item_pos * 2 + 1] = *sin_value;
            matrix[row][column_count] = *rhs_value;
        }
        if (support.empty()) {
            auto rhs_value = rat_mod(rhs[row]);
            if (!rhs_value) {
                return true;
            }
            matrix[row][0] = *rhs_value;
        }
    }

    std::size_t pivot_row = 0;
    for (int column = 0; column < column_count && pivot_row < matrix.size(); ++column) {
        std::size_t pivot = pivot_row;
        while (pivot < matrix.size() && matrix[pivot][column] == 0) {
            ++pivot;
        }
        if (pivot == matrix.size()) {
            continue;
        }
        std::swap(matrix[pivot], matrix[pivot_row]);
        long long inverse = mod_pow(matrix[pivot_row][column], MODULUS - 2);
        for (int j = column; j <= column_count; ++j) {
            matrix[pivot_row][j] = static_cast<long long>(
                (
                    static_cast<unsigned long long>(matrix[pivot_row][j]) *
                    static_cast<unsigned long long>(inverse)
                ) % static_cast<unsigned long long>(MODULUS)
            );
        }
        for (std::size_t row = pivot_row + 1; row < matrix.size(); ++row) {
            long long factor = matrix[row][column];
            if (factor == 0) {
                continue;
            }
            for (int j = column; j <= column_count; ++j) {
                long long delta = static_cast<long long>(
                    (
                        static_cast<unsigned long long>(factor) *
                        static_cast<unsigned long long>(matrix[pivot_row][j])
                    ) % static_cast<unsigned long long>(MODULUS)
                );
                matrix[row][j] -= delta;
                if (matrix[row][j] < 0) {
                    matrix[row][j] += MODULUS;
                }
            }
        }
        ++pivot_row;
    }
    for (const auto& row : matrix) {
        bool all_zero = true;
        for (int column = 0; column < column_count; ++column) {
            if (row[column] != 0) {
                all_zero = false;
                break;
            }
        }
        if (all_zero && row[column_count] != 0) {
            return false;
        }
    }
    return true;
}

static std::optional<std::vector<Rat>> exact_unique_solution(
    const std::vector<int>& support,
    const std::vector<std::vector<Rat>>& cosine_columns,
    const std::vector<std::vector<Rat>>& sine_columns,
    const std::vector<Rat>& rhs
) {
    const int column_count = static_cast<int>(support.size()) * 2;
    if (column_count == 0) {
        for (const Rat& value : rhs) {
            if (!value.is_zero()) {
                return std::nullopt;
            }
        }
        return std::vector<Rat>{};
    }
    std::vector<std::vector<Rat>> matrix(
        rhs.size(), std::vector<Rat>(column_count + 1, Rat(0))
    );
    for (std::size_t row = 0; row < rhs.size(); ++row) {
        for (std::size_t item_pos = 0; item_pos < support.size(); ++item_pos) {
            matrix[row][item_pos * 2] = cosine_columns[support[item_pos]][row];
            matrix[row][item_pos * 2 + 1] = sine_columns[support[item_pos]][row];
        }
        matrix[row][column_count] = rhs[row];
    }

    std::size_t pivot_row = 0;
    std::vector<int> pivot_for_column(column_count, -1);
    for (int column = 0; column < column_count && pivot_row < matrix.size(); ++column) {
        std::size_t pivot = pivot_row;
        while (pivot < matrix.size() && matrix[pivot][column].is_zero()) {
            ++pivot;
        }
        if (pivot == matrix.size()) {
            continue;
        }
        std::swap(matrix[pivot], matrix[pivot_row]);
        Rat pivot_value = matrix[pivot_row][column];
        for (int j = column; j <= column_count; ++j) {
            matrix[pivot_row][j] = matrix[pivot_row][j] / pivot_value;
        }
        for (std::size_t row = 0; row < matrix.size(); ++row) {
            if (row == pivot_row || matrix[row][column].is_zero()) {
                continue;
            }
            Rat factor = matrix[row][column];
            for (int j = column; j <= column_count; ++j) {
                matrix[row][j] = matrix[row][j] - factor * matrix[pivot_row][j];
            }
        }
        pivot_for_column[column] = static_cast<int>(pivot_row);
        ++pivot_row;
    }

    for (const auto& row : matrix) {
        bool all_zero = true;
        for (int column = 0; column < column_count; ++column) {
            if (!row[column].is_zero()) {
                all_zero = false;
                break;
            }
        }
        if (all_zero && !row[column_count].is_zero()) {
            return std::nullopt;
        }
    }
    if (pivot_row != static_cast<std::size_t>(column_count)) {
        return std::nullopt;
    }

    std::vector<Rat> solution(column_count, Rat(0));
    for (int column = 0; column < column_count; ++column) {
        if (pivot_for_column[column] < 0) {
            return std::nullopt;
        }
        solution[column] = matrix[pivot_for_column[column]][column_count];
    }
    for (std::size_t item_pos = 0; item_pos < support.size(); ++item_pos) {
        if (solution[item_pos * 2].is_zero() && solution[item_pos * 2 + 1].is_zero()) {
            return std::nullopt;
        }
    }
    return solution;
}

struct Recovery {
    std::vector<int> support;
    std::vector<Rat> coordinates;
};

static Recovery recover(const Campaign& campaign, const std::vector<Rat>& rhs) {
    std::vector<Item> items = build_items(campaign);
    if (campaign.max_active > static_cast<int>(items.size())) {
        throw std::runtime_error("active-source limit exceeds candidate count");
    }
    std::vector<std::vector<Rat>> cosine_columns;
    std::vector<std::vector<Rat>> sine_columns;
    for (const auto& item : items) {
        cosine_columns.push_back(item_column(campaign, item, false));
        sine_columns.push_back(item_column(campaign, item, true));
    }

    for (int target_size = 0; target_size <= campaign.max_active; ++target_size) {
        std::vector<int> selected;
        std::optional<Recovery> found;
        std::function<void(int, int)> visit = [&](int start, int remaining) {
            if (found) {
                return;
            }
            if (remaining == 0) {
                if (!modular_maybe_consistent(selected, cosine_columns, sine_columns, rhs)) {
                    return;
                }
                auto solution = exact_unique_solution(selected, cosine_columns, sine_columns, rhs);
                if (solution) {
                    found = Recovery{selected, *solution};
                }
                return;
            }
            if (static_cast<int>(items.size()) - start < remaining) {
                return;
            }
            for (int index = start; index <= static_cast<int>(items.size()) - remaining; ++index) {
                selected.push_back(index);
                visit(index + 1, remaining - 1);
                selected.pop_back();
                if (found) {
                    return;
                }
            }
        };
        visit(0, target_size);
        if (found) {
            return *found;
        }
    }
    throw std::runtime_error("campaign has no admissible recovery");
}

static json build_product(const Campaign& campaign, const Recovery& recovery, const std::vector<Rat>& rhs) {
    const std::vector<Item> items = build_items(campaign);
    json selected_sources = json::array();
    json folded_tracks = json::array();
    json sensitivity_values = json::array();
    json source_contributions = json::array();
    std::vector<Rat> predicted(rhs.size(), Rat(0));
    std::vector<std::string> support_key;

    std::size_t coordinate_offset = 0;
    for (int item_index : recovery.support) {
        const Item& item = items[item_index];
        const Rat& source_cos = recovery.coordinates[coordinate_offset++];
        const Rat& source_sin = recovery.coordinates[coordinate_offset++];
        support_key.push_back(item.tone.id + "@" + item.source);
        selected_sources.push_back(
            {
                {"tone_id", item.tone.id},
                {"source_id", item.source},
                {"omega", item.tone.omega},
                {"cos", rat_json(source_cos)},
                {"sin", rat_json(source_sin)},
                {"energy", rat_json(source_cos * source_cos + source_sin * source_sin)},
            }
        );

        for (const auto& capture : campaign.captures) {
            Fold folded = fold_tone(item.tone.omega, capture.sample_rate);
            int phase = trigger_phase(item.tone.omega, capture.trigger_quarters);
            folded_tracks.push_back(
                {
                    {"tone_id", item.tone.id},
                    {"source_id", item.source},
                    {"capture_id", capture.id},
                    {"sample_rate", capture.sample_rate},
                    {"trigger_quarters", capture.trigger_quarters},
                    {"phase_quarters", phase},
                    {"folded_bin", folded.bin},
                    {"sine_sign", folded.sine_sign},
                }
            );
        }

        for (const auto& probe : campaign.probes) {
            Cpx h = path_response(campaign.paths.at({item.source, probe}), item.tone.omega);
            sensitivity_values.push_back(
                {
                    {"tone_id", item.tone.id},
                    {"source_id", item.source},
                    {"probe_id", probe},
                    {"real", rat_json(h.real)},
                    {"imag", rat_json(h.imag)},
                }
            );
        }

        std::size_t row_offset = 0;
        for (const auto& capture : campaign.captures) {
            for (const auto& probe : capture.probes) {
                Contribution value = contribution(
                    campaign, item, capture, probe.id, source_cos, source_sin
                );
                source_contributions.push_back(
                    {
                        {"tone_id", item.tone.id},
                        {"source_id", item.source},
                        {"capture_id", capture.id},
                        {"probe_id", probe.id},
                        {"bin", value.bin},
                        {"cos", rat_json(value.cosine)},
                        {"sin", rat_json(value.sine)},
                    }
                );
                for (const auto& bin : probe.bins) {
                    if (bin.id == value.bin) {
                        predicted[row_offset] = predicted[row_offset] + value.cosine;
                        predicted[row_offset + 1] = predicted[row_offset + 1] + value.sine;
                    }
                    row_offset += 2;
                }
            }
        }
    }

    json reconstructed_bins = json::array();
    json residual_balance = json::array();
    std::size_t row_offset = 0;
    for (const auto& capture : campaign.captures) {
        for (const auto& probe : capture.probes) {
            for (const auto& bin : probe.bins) {
                const Rat& predicted_cos = predicted[row_offset];
                const Rat& predicted_sin = predicted[row_offset + 1];
                const Rat& observed_cos = rhs[row_offset];
                const Rat& observed_sin = rhs[row_offset + 1];
                reconstructed_bins.push_back(
                    {
                        {"capture_id", capture.id},
                        {"probe_id", probe.id},
                        {"bin", bin.id},
                        {"cos", rat_json(predicted_cos)},
                        {"sin", rat_json(predicted_sin)},
                    }
                );
                residual_balance.push_back(
                    {
                        {"capture_id", capture.id},
                        {"probe_id", probe.id},
                        {"bin", bin.id},
                        {"observed", {{"cos", rat_json(observed_cos)}, {"sin", rat_json(observed_sin)}}},
                        {"predicted", {{"cos", rat_json(predicted_cos)}, {"sin", rat_json(predicted_sin)}}},
                        {"error", {
                            {"cos", rat_json(observed_cos - predicted_cos)},
                            {"sin", rat_json(observed_sin - predicted_sin)},
                        }},
                    }
                );
                row_offset += 2;
            }
        }
    }

    json certificate{
        {"support_size", static_cast<int>(recovery.support.size())},
        {"scalar_unknowns", static_cast<int>(recovery.support.size()) * 2},
        {"scalar_equations", static_cast<int>(rhs.size())},
        {"matrix_rank", static_cast<int>(recovery.support.size()) * 2},
        {"exact_fit", true},
        {"support_key", support_key},
    };

    return json{
        {"selected_sources", selected_sources},
        {"folded_tracks", folded_tracks},
        {"sensitivity_values", sensitivity_values},
        {"source_contributions", source_contributions},
        {"reconstructed_bins", reconstructed_bins},
        {"residual_balance", residual_balance},
        {"recovery_certificate", certificate},
    };
}

static bool path_is_within(const fs::path& candidate, const fs::path& root) {
    fs::path relative = candidate.lexically_relative(root);
    if (relative.empty()) {
        return true;
    }
    if (relative.is_absolute()) {
        return false;
    }
    auto first = relative.begin();
    return first != relative.end() && *first != "..";
}

int main(int argc, char** argv) {
    if (argc != 3) {
        std::cerr << "expected campaign directory and destination\n";
        return 2;
    }
    fs::path destination = argv[2];
    fs::path temporary = destination;
    temporary += ".tmp";
    try {
        fs::path campaign_root = fs::weakly_canonical(fs::path(argv[1]));
        fs::path raw_parent = destination.has_parent_path() ? destination.parent_path() : fs::current_path();
        fs::path destination_parent = fs::weakly_canonical(raw_parent);
        fs::path normalized_destination = (destination_parent / destination.filename()).lexically_normal();
        if (path_is_within(normalized_destination, campaign_root)) {
            throw std::runtime_error("destination must be outside the campaign directory");
        }
        Campaign campaign = load_campaign(argv[1]);
        for (const auto& tone : campaign.tones) {
            for (const auto& [key, model] : campaign.paths) {
                (void)key;
                (void)path_response(model, tone.omega);
            }
        }
        std::vector<Rat> rhs;
        std::vector<RowKey> rows = build_rows(campaign, rhs);
        (void)rows;
        Recovery recovery = recover(campaign, rhs);
        json product = build_product(campaign, recovery, rhs);

        std::ofstream stream(temporary, std::ios::binary | std::ios::trunc);
        if (!stream) {
            throw std::runtime_error("cannot open temporary destination");
        }
        stream << product.dump(2) << '\n';
        stream.close();
        if (!stream) {
            throw std::runtime_error("cannot finish destination");
        }
        fs::rename(temporary, destination);
        return 0;
    } catch (const std::exception& error) {
        std::error_code ignored;
        fs::remove(temporary, ignored);
        std::cerr << error.what() << '\n';
        return 2;
    }
}
