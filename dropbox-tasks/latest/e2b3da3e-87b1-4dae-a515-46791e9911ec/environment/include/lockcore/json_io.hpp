#pragma once

#include "lockcore/types.hpp"

#include <cstdint>
#include <memory>
#include <stdexcept>
#include <string>
#include <utility>
#include <vector>

namespace lockcore {

class JsonError : public std::runtime_error {
public:
    explicit JsonError(const std::string& msg) : std::runtime_error(msg) {}
};

enum class JsonType { Null, Bool, Number, String, Array, Object };

// Minimal JSON value with insertion-order-preserving objects. Numbers keep
// track of whether the original literal looked like an integer so that
// re-serialization can round-trip schema fields such as `schema_version`
// without turning them into `4.0`.
class JsonValue {
public:
    JsonType type = JsonType::Null;

    bool bool_value = false;
    double num_value = 0.0;
    bool is_integer = false;
    int64_t int_value = 0;
    std::string str_value;
    std::vector<JsonValue> arr_value;
    std::vector<std::pair<std::string, JsonValue>> obj_value;

    static JsonValue make_null();
    static JsonValue make_bool(bool b);
    static JsonValue make_number(double d);
    static JsonValue make_int(int64_t i);
    static JsonValue make_string(std::string s);
    static JsonValue make_array();
    static JsonValue make_object();

    bool is_object() const { return type == JsonType::Object; }
    bool is_array() const { return type == JsonType::Array; }
    bool is_string() const { return type == JsonType::String; }
    bool is_number() const { return type == JsonType::Number; }
    bool is_bool() const { return type == JsonType::Bool; }
    bool is_null() const { return type == JsonType::Null; }

    bool contains(const std::string& key) const;
    const JsonValue& at(const std::string& key) const;
    void set(const std::string& key, JsonValue value);
    void push_back(JsonValue value);

    std::vector<std::string> keys() const;

    double as_double() const;
    int64_t as_int() const;
    bool as_bool() const;
    const std::string& as_string() const;
};

JsonValue parse_json(const std::string& text);

// Compact serialization preserving object insertion order (used for reports
// and snapshots whose key order is contract-defined).
std::string dump_compact(const JsonValue& value);

// Compact serialization with object keys recursively sorted (used for
// digest/hash canonicalization).
std::string dump_canonical(const JsonValue& value);

std::string round_trip_double(double v);

std::string sha256_hex(const std::string& data);

std::string read_file_bytes(const std::string& path);
bool file_exists(const std::string& path);
uint64_t file_size_bytes(const std::string& path);
void ensure_parent_directory(const std::string& path);

// Writes `content` atomically to `path` via a unique sibling temp file and
// rename.
void write_atomic(const std::string& path, const std::string& content);

// Writes two files as a single logical commit: both temps are prepared and
// fsynced before either target is replaced; if the second replace fails the
// first target is restored from its original bytes.
void write_atomic_pair(const std::string& path_a, const std::string& content_a,
                       const std::string& path_b, const std::string& content_b);

std::string normalize_absolute_path(const std::string& path);

CaseSpec load_case(const std::string& path);
Topology load_topology(const std::string& path);
std::vector<ForcingEvent> load_forcing(const std::string& path);

JsonValue case_to_json(const CaseSpec& c);
JsonValue topology_to_json(const Topology& t);
JsonValue storage_curve_to_json(const StorageCurve& c);
StorageCurve storage_curve_from_json(const JsonValue& v);

}  // namespace lockcore
