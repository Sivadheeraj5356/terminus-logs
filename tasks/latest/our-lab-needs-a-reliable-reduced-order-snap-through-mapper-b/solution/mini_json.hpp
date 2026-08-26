#pragma once

#include <cctype>
#include <cmath>
#include <cstddef>
#include <iomanip>
#include <map>
#include <sstream>
#include <stdexcept>
#include <string>
#include <variant>
#include <vector>

namespace mj {

struct Value {
    using Array = std::vector<Value>;
    using Object = std::map<std::string, Value>;
    std::variant<std::nullptr_t, bool, double, std::string, Array, Object> data;

    Value() : data(nullptr) {}
    Value(std::nullptr_t) : data(nullptr) {}
    Value(bool v) : data(v) {}
    Value(double v) : data(v) {}
    Value(int v) : data(static_cast<double>(v)) {}
    Value(std::string v) : data(std::move(v)) {}
    Value(const char* v) : data(std::string(v)) {}
    Value(Array v) : data(std::move(v)) {}
    Value(Object v) : data(std::move(v)) {}

    bool is_null() const { return std::holds_alternative<std::nullptr_t>(data); }
    bool is_bool() const { return std::holds_alternative<bool>(data); }
    bool is_number() const { return std::holds_alternative<double>(data); }
    bool is_string() const { return std::holds_alternative<std::string>(data); }
    bool is_array() const { return std::holds_alternative<Array>(data); }
    bool is_object() const { return std::holds_alternative<Object>(data); }

    bool as_bool() const { return std::get<bool>(data); }
    double as_number() const { return std::get<double>(data); }
    const std::string& as_string() const { return std::get<std::string>(data); }
    const Array& as_array() const { return std::get<Array>(data); }
    Array& as_array() { return std::get<Array>(data); }
    const Object& as_object() const { return std::get<Object>(data); }
    Object& as_object() { return std::get<Object>(data); }
};

class Parser {
  public:
    explicit Parser(const std::string& text) : text_(text) {}

    Value parse() {
        skip_ws();
        Value v = parse_value();
        skip_ws();
        if (pos_ != text_.size()) {
            fail("trailing content");
        }
        return v;
    }

  private:
    const std::string& text_;
    std::size_t pos_ = 0;

    [[noreturn]] void fail(const std::string& what) const {
        throw std::runtime_error("JSON parse error at byte " + std::to_string(pos_) + ": " + what);
    }

    void skip_ws() {
        while (pos_ < text_.size() && std::isspace(static_cast<unsigned char>(text_[pos_]))) {
            ++pos_;
        }
    }

    bool take(char c) {
        if (pos_ < text_.size() && text_[pos_] == c) {
            ++pos_;
            return true;
        }
        return false;
    }

    Value parse_value() {
        if (pos_ >= text_.size()) {
            fail("expected value");
        }
        const char c = text_[pos_];
        if (c == '{') return parse_object();
        if (c == '[') return parse_array();
        if (c == '"') return Value(parse_string());
        if (c == '-' || std::isdigit(static_cast<unsigned char>(c))) return Value(parse_number());
        if (text_.compare(pos_, 4, "true") == 0) {
            pos_ += 4;
            return Value(true);
        }
        if (text_.compare(pos_, 5, "false") == 0) {
            pos_ += 5;
            return Value(false);
        }
        if (text_.compare(pos_, 4, "null") == 0) {
            pos_ += 4;
            return Value(nullptr);
        }
        fail("unexpected token");
    }

    Value parse_object() {
        take('{');
        skip_ws();
        Value::Object obj;
        if (take('}')) return Value(std::move(obj));
        while (true) {
            skip_ws();
            if (pos_ >= text_.size() || text_[pos_] != '"') fail("expected object key");
            std::string key = parse_string();
            skip_ws();
            if (!take(':')) fail("expected ':'");
            skip_ws();
            if (obj.find(key) != obj.end()) fail("duplicate object key");
            obj.emplace(std::move(key), parse_value());
            skip_ws();
            if (take('}')) break;
            if (!take(',')) fail("expected ',' or '}'");
        }
        return Value(std::move(obj));
    }

    Value parse_array() {
        take('[');
        skip_ws();
        Value::Array arr;
        if (take(']')) return Value(std::move(arr));
        while (true) {
            skip_ws();
            arr.push_back(parse_value());
            skip_ws();
            if (take(']')) break;
            if (!take(',')) fail("expected ',' or ']'");
        }
        return Value(std::move(arr));
    }

    static void append_utf8(std::string& out, unsigned cp) {
        if (cp <= 0x7F) {
            out.push_back(static_cast<char>(cp));
        } else if (cp <= 0x7FF) {
            out.push_back(static_cast<char>(0xC0 | (cp >> 6)));
            out.push_back(static_cast<char>(0x80 | (cp & 0x3F)));
        } else if (cp <= 0xFFFF) {
            out.push_back(static_cast<char>(0xE0 | (cp >> 12)));
            out.push_back(static_cast<char>(0x80 | ((cp >> 6) & 0x3F)));
            out.push_back(static_cast<char>(0x80 | (cp & 0x3F)));
        } else {
            out.push_back(static_cast<char>(0xF0 | (cp >> 18)));
            out.push_back(static_cast<char>(0x80 | ((cp >> 12) & 0x3F)));
            out.push_back(static_cast<char>(0x80 | ((cp >> 6) & 0x3F)));
            out.push_back(static_cast<char>(0x80 | (cp & 0x3F)));
        }
    }

    unsigned parse_hex4() {
        unsigned cp = 0;
        for (int i = 0; i < 4; ++i) {
            if (pos_ >= text_.size()) fail("truncated unicode escape");
            char c = text_[pos_++];
            cp <<= 4;
            if (c >= '0' && c <= '9') cp |= static_cast<unsigned>(c - '0');
            else if (c >= 'a' && c <= 'f') cp |= static_cast<unsigned>(10 + c - 'a');
            else if (c >= 'A' && c <= 'F') cp |= static_cast<unsigned>(10 + c - 'A');
            else fail("invalid unicode escape");
        }
        return cp;
    }

    std::string parse_string() {
        if (!take('"')) fail("expected string");
        std::string out;
        while (pos_ < text_.size()) {
            char c = text_[pos_++];
            if (c == '"') return out;
            if (static_cast<unsigned char>(c) < 0x20) fail("control character in string");
            if (c != '\\') {
                out.push_back(c);
                continue;
            }
            if (pos_ >= text_.size()) fail("truncated escape");
            char e = text_[pos_++];
            switch (e) {
                case '"': out.push_back('"'); break;
                case '\\': out.push_back('\\'); break;
                case '/': out.push_back('/'); break;
                case 'b': out.push_back('\b'); break;
                case 'f': out.push_back('\f'); break;
                case 'n': out.push_back('\n'); break;
                case 'r': out.push_back('\r'); break;
                case 't': out.push_back('\t'); break;
                case 'u': {
                    unsigned cp = parse_hex4();
                    if (cp >= 0xD800 && cp <= 0xDBFF) {
                        if (pos_ + 2 > text_.size() || text_[pos_] != '\\' || text_[pos_ + 1] != 'u') {
                            fail("unpaired high surrogate");
                        }
                        pos_ += 2;
                        unsigned low = parse_hex4();
                        if (low < 0xDC00 || low > 0xDFFF) fail("invalid low surrogate");
                        cp = 0x10000 + ((cp - 0xD800) << 10) + (low - 0xDC00);
                    } else if (cp >= 0xDC00 && cp <= 0xDFFF) {
                        fail("unpaired low surrogate");
                    }
                    append_utf8(out, cp);
                    break;
                }
                default: fail("invalid escape");
            }
        }
        fail("unterminated string");
    }

    double parse_number() {
        const std::size_t start = pos_;
        take('-');
        if (pos_ >= text_.size()) fail("truncated number");
        if (text_[pos_] == '0') {
            ++pos_;
        } else {
            if (!std::isdigit(static_cast<unsigned char>(text_[pos_]))) fail("invalid number");
            while (pos_ < text_.size() && std::isdigit(static_cast<unsigned char>(text_[pos_]))) ++pos_;
        }
        if (take('.')) {
            if (pos_ >= text_.size() || !std::isdigit(static_cast<unsigned char>(text_[pos_]))) fail("invalid fraction");
            while (pos_ < text_.size() && std::isdigit(static_cast<unsigned char>(text_[pos_]))) ++pos_;
        }
        if (pos_ < text_.size() && (text_[pos_] == 'e' || text_[pos_] == 'E')) {
            ++pos_;
            if (pos_ < text_.size() && (text_[pos_] == '+' || text_[pos_] == '-')) ++pos_;
            if (pos_ >= text_.size() || !std::isdigit(static_cast<unsigned char>(text_[pos_]))) fail("invalid exponent");
            while (pos_ < text_.size() && std::isdigit(static_cast<unsigned char>(text_[pos_]))) ++pos_;
        }
        double v;
        try {
            v = std::stod(text_.substr(start, pos_ - start));
        } catch (...) {
            fail("number out of range");
        }
        if (!std::isfinite(v)) fail("non-finite number");
        return v;
    }
};

inline std::string escape(const std::string& text) {
    std::ostringstream out;
    out << '"';
    for (unsigned char c : text) {
        switch (c) {
            case '"': out << "\\\""; break;
            case '\\': out << "\\\\"; break;
            case '\b': out << "\\b"; break;
            case '\f': out << "\\f"; break;
            case '\n': out << "\\n"; break;
            case '\r': out << "\\r"; break;
            case '\t': out << "\\t"; break;
            default:
                if (c < 0x20) {
                    out << "\\u" << std::hex << std::setw(4) << std::setfill('0') << static_cast<int>(c)
                        << std::dec << std::setfill(' ');
                } else {
                    out << static_cast<char>(c);
                }
        }
    }
    out << '"';
    return out.str();
}

inline void dump_into(const Value& v, std::ostringstream& out) {
    if (v.is_null()) {
        out << "null";
    } else if (v.is_bool()) {
        out << (v.as_bool() ? "true" : "false");
    } else if (v.is_number()) {
        double x = v.as_number();
        if (!std::isfinite(x)) throw std::runtime_error("cannot serialize non-finite number");
        out << std::setprecision(17) << x;
    } else if (v.is_string()) {
        out << escape(v.as_string());
    } else if (v.is_array()) {
        out << '[';
        bool first = true;
        for (const auto& item : v.as_array()) {
            if (!first) out << ',';
            first = false;
            dump_into(item, out);
        }
        out << ']';
    } else {
        out << '{';
        bool first = true;
        for (const auto& [key, item] : v.as_object()) {
            if (!first) out << ',';
            first = false;
            out << escape(key) << ':';
            dump_into(item, out);
        }
        out << '}';
    }
}

inline Value parse(const std::string& text) { return Parser(text).parse(); }

inline std::string dump(const Value& value) {
    std::ostringstream out;
    dump_into(value, out);
    out << '\n';
    return out.str();
}

}  // namespace mj
