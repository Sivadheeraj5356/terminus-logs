// Render-pipeline plugin resolver (starter).
//
// Reads a JSON array of resolution cases from standard input and writes a JSON
// array of install-set results to standard output, one per case in order. Each
// case is {"registry": {name: [{version, yanked?, deps?}, ...]}, "requirements":
// {name: constraint}} and a result is {"install": [{name, version}, ...],
// "conflicts": [{packages, dependency}, ...]}. See README.md for the resolution
// contract this program must follow.
//
// TODO: this starter only resolves the top-level requirements of a case using a
// naive reading of the `=`, `>=` and `*` operators, always skipping yanked and
// pre-release versions. It does NOT expand transitive dependency constraints, it
// mishandles the caret/tilde and other comparator operators, it does not apply
// the yanked-exact-pin or pre-release inclusion rules, and it never emits a
// conflict record.

#include <algorithm>
#include <cstdlib>
#include <iostream>
#include <iterator>
#include <map>
#include <optional>
#include <set>
#include <stdexcept>
#include <string>
#include <utility>
#include <vector>

// ---- small JSON model + parser (hand-rolled for the fixed schema) ----

struct JsonValue {
    enum Type { Null, Bool, Num, Str, Arr, Obj } type = Null;
    bool b = false;
    double num = 0;
    std::string str;
    std::vector<JsonValue> arr;
    std::vector<std::pair<std::string, JsonValue>> obj;
    const JsonValue *find(const std::string &key) const {
        for (const auto &kv : obj)
            if (kv.first == key)
                return &kv.second;
        return nullptr;
    }
};

struct JsonParser {
    const std::string &s;
    size_t i = 0;
    explicit JsonParser(const std::string &src) : s(src) {}
    [[noreturn]] void fail(const std::string &m) { throw std::runtime_error(m); }
    void ws() {
        while (i < s.size() && (s[i] == ' ' || s[i] == '\t' || s[i] == '\n' || s[i] == '\r'))
            i++;
    }
    JsonValue parse() {
        ws();
        JsonValue v = parseValue();
        ws();
        if (i != s.size())
            fail("trailing data");
        return v;
    }
    void expect(const std::string &lit) {
        if (s.compare(i, lit.size(), lit) != 0)
            fail("invalid literal");
        i += lit.size();
    }
    JsonValue parseValue() {
        ws();
        if (i >= s.size())
            fail("unexpected end of input");
        char c = s[i];
        if (c == '{')
            return parseObj();
        if (c == '[')
            return parseArr();
        if (c == '"') {
            JsonValue v;
            v.type = JsonValue::Str;
            v.str = parseStr();
            return v;
        }
        if (c == 't') {
            expect("true");
            JsonValue v;
            v.type = JsonValue::Bool;
            v.b = true;
            return v;
        }
        if (c == 'f') {
            expect("false");
            JsonValue v;
            v.type = JsonValue::Bool;
            v.b = false;
            return v;
        }
        if (c == 'n') {
            expect("null");
            JsonValue v;
            v.type = JsonValue::Null;
            return v;
        }
        return parseNum();
    }
    std::string parseStr() {
        if (s[i] != '"')
            fail("expected string");
        i++;
        std::string out;
        while (i < s.size()) {
            char c = s[i++];
            if (c == '"')
                return out;
            if (c == '\\') {
                if (i >= s.size())
                    fail("bad escape");
                char e = s[i++];
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
                    if (i + 4 > s.size())
                        fail("bad unicode escape");
                    int cp = 0;
                    for (int k = 0; k < 4; k++) {
                        char h = s[i++];
                        cp <<= 4;
                        if (h >= '0' && h <= '9')
                            cp |= h - '0';
                        else if (h >= 'a' && h <= 'f')
                            cp |= h - 'a' + 10;
                        else if (h >= 'A' && h <= 'F')
                            cp |= h - 'A' + 10;
                        else
                            fail("bad unicode digit");
                    }
                    if (cp < 0x80) {
                        out.push_back((char)cp);
                    } else if (cp < 0x800) {
                        out.push_back((char)(0xC0 | (cp >> 6)));
                        out.push_back((char)(0x80 | (cp & 0x3F)));
                    } else {
                        out.push_back((char)(0xE0 | (cp >> 12)));
                        out.push_back((char)(0x80 | ((cp >> 6) & 0x3F)));
                        out.push_back((char)(0x80 | (cp & 0x3F)));
                    }
                    break;
                }
                default:
                    fail("bad escape char");
                }
            } else {
                out.push_back(c);
            }
        }
        fail("unterminated string");
    }
    JsonValue parseNum() {
        size_t start = i;
        while (i < s.size()) {
            char c = s[i];
            if ((c >= '0' && c <= '9') || c == '-' || c == '+' || c == '.' || c == 'e' || c == 'E')
                i++;
            else
                break;
        }
        if (i == start)
            fail("invalid value");
        JsonValue v;
        v.type = JsonValue::Num;
        v.num = std::strtod(s.substr(start, i - start).c_str(), nullptr);
        return v;
    }
    JsonValue parseArr() {
        JsonValue v;
        v.type = JsonValue::Arr;
        i++; // [
        ws();
        if (i < s.size() && s[i] == ']') {
            i++;
            return v;
        }
        while (true) {
            v.arr.push_back(parseValue());
            ws();
            if (i >= s.size())
                fail("unterminated array");
            if (s[i] == ',') {
                i++;
                continue;
            }
            if (s[i] == ']') {
                i++;
                break;
            }
            fail("expected , or ] in array");
        }
        return v;
    }
    JsonValue parseObj() {
        JsonValue v;
        v.type = JsonValue::Obj;
        i++; // {
        ws();
        if (i < s.size() && s[i] == '}') {
            i++;
            return v;
        }
        while (true) {
            ws();
            std::string key = parseStr();
            ws();
            if (i >= s.size() || s[i] != ':')
                fail("expected : in object");
            i++;
            JsonValue val = parseValue();
            v.obj.emplace_back(std::move(key), std::move(val));
            ws();
            if (i >= s.size())
                fail("unterminated object");
            if (s[i] == ',') {
                i++;
                continue;
            }
            if (s[i] == '}') {
                i++;
                break;
            }
            fail("expected , or } in object");
        }
        return v;
    }
};

// ---- shared string helpers ----

static std::vector<std::string> splitStr(const std::string &s, char delim) {
    std::vector<std::string> out;
    std::string cur;
    for (char c : s) {
        if (c == delim) {
            out.push_back(cur);
            cur.clear();
        } else {
            cur.push_back(c);
        }
    }
    out.push_back(cur);
    return out;
}

static std::string trim(const std::string &s) {
    size_t a = 0, b = s.size();
    while (a < b && (s[a] == ' ' || s[a] == '\t' || s[a] == '\n' || s[a] == '\r'))
        a++;
    while (b > a && (s[b - 1] == ' ' || s[b - 1] == '\t' || s[b - 1] == '\n' || s[b - 1] == '\r'))
        b--;
    return s.substr(a, b - a);
}

static bool isNum(const std::string &s) {
    if (s.empty())
        return false;
    for (char c : s)
        if (c < '0' || c > '9')
            return false;
    return true;
}

static int toInt(const std::string &s) {
    if (s.empty())
        return 0;
    size_t k = 0;
    if (s[0] == '+' || s[0] == '-')
        k = 1;
    if (k == s.size())
        return 0;
    for (size_t j = k; j < s.size(); j++)
        if (s[j] < '0' || s[j] > '9')
            return 0;
    return std::atoi(s.c_str());
}

// ---- case + result data ----

struct Entry {
    std::string version;
    bool yanked = false;
    std::map<std::string, std::string> deps;
};

struct ResCase {
    std::map<std::string, std::vector<Entry>> registry;
    std::map<std::string, std::string> requirements;
};

struct InstallItem {
    std::string name;
    std::string version;
};

struct ConflictItem {
    std::vector<std::string> packages;
    std::string dependency;
};

struct Result {
    std::vector<InstallItem> install;
    std::vector<ConflictItem> conflicts;
};

static Entry parseEntry(const JsonValue &e) {
    Entry en;
    if (const JsonValue *v = e.find("version"); v && v->type == JsonValue::Str)
        en.version = v->str;
    if (const JsonValue *y = e.find("yanked"); y && y->type == JsonValue::Bool)
        en.yanked = y->b;
    if (const JsonValue *d = e.find("deps"); d && d->type == JsonValue::Obj)
        for (const auto &kv : d->obj)
            if (kv.second.type == JsonValue::Str)
                en.deps[kv.first] = kv.second.str;
    return en;
}

static ResCase parseCase(const JsonValue &c) {
    ResCase rc;
    if (const JsonValue *reg = c.find("registry"); reg && reg->type == JsonValue::Obj) {
        for (const auto &kv : reg->obj) {
            std::vector<Entry> es;
            if (kv.second.type == JsonValue::Arr)
                for (const auto &ev : kv.second.arr)
                    es.push_back(parseEntry(ev));
            rc.registry[kv.first] = std::move(es);
        }
    }
    if (const JsonValue *req = c.find("requirements"); req && req->type == JsonValue::Obj) {
        for (const auto &kv : req->obj)
            if (kv.second.type == JsonValue::Str)
                rc.requirements[kv.first] = kv.second.str;
    }
    return rc;
}

static void escInto(std::string &out, const std::string &s) {
    out.push_back('"');
    for (unsigned char c : s) {
        switch (c) {
        case '"': out += "\\\""; break;
        case '\\': out += "\\\\"; break;
        case '\b': out += "\\b"; break;
        case '\f': out += "\\f"; break;
        case '\n': out += "\\n"; break;
        case '\r': out += "\\r"; break;
        case '\t': out += "\\t"; break;
        default:
            if (c < 0x20) {
                static const char *hex = "0123456789abcdef";
                out += "\\u00";
                out.push_back(hex[(c >> 4) & 0xF]);
                out.push_back(hex[c & 0xF]);
            } else {
                out.push_back((char)c);
            }
        }
    }
    out.push_back('"');
}

static std::string serialize(const std::vector<Result> &rs) {
    std::string out = "[";
    for (size_t ri = 0; ri < rs.size(); ri++) {
        if (ri)
            out.push_back(',');
        const Result &r = rs[ri];
        out += "{\"install\":[";
        for (size_t k = 0; k < r.install.size(); k++) {
            if (k)
                out.push_back(',');
            out += "{\"name\":";
            escInto(out, r.install[k].name);
            out += ",\"version\":";
            escInto(out, r.install[k].version);
            out.push_back('}');
        }
        out += "],\"conflicts\":[";
        for (size_t k = 0; k < r.conflicts.size(); k++) {
            if (k)
                out.push_back(',');
            out += "{\"packages\":[";
            for (size_t p = 0; p < r.conflicts[k].packages.size(); p++) {
                if (p)
                    out.push_back(',');
                escInto(out, r.conflicts[k].packages[p]);
            }
            out += "],\"dependency\":";
            escInto(out, r.conflicts[k].dependency);
            out.push_back('}');
        }
        out += "]}";
    }
    out.push_back(']');
    return out;
}

// ==== resolver (starter, naive) ==============================================

// naiveVer parses "maj.min.patch" ignoring any pre-release tag; the return value
// is false when the string carries a pre-release tag or is otherwise malformed.
static bool naiveVer(const std::string &s, int out[3]) {
    out[0] = out[1] = out[2] = 0;
    if (s.find('-') != std::string::npos)
        return false;
    std::vector<std::string> parts = splitStr(s, '.');
    if (parts.size() != 3)
        return false;
    for (int i = 0; i < 3; i++) {
        if (!isNum(parts[i]))
            return false;
        out[i] = std::atoi(parts[i].c_str());
    }
    return true;
}

static int cmp3(const int a[3], const int b[3]) {
    for (int i = 0; i < 3; i++)
        if (a[i] != b[i])
            return a[i] < b[i] ? -1 : 1;
    return 0;
}

// naiveSat only understands "*", "=x.y.z" and ">=x.y.z".
static bool naiveSat(const int v[3], const std::string &constraint) {
    std::string c = trim(constraint);
    if (c.empty() || c == "*")
        return true;
    if (c.rfind(">=", 0) == 0) {
        int b[3];
        if (naiveVer(trim(c.substr(2)), b))
            return cmp3(v, b) >= 0;
        return true;
    }
    if (c.rfind("=", 0) == 0) {
        int b[3];
        if (naiveVer(trim(c.substr(1)), b))
            return cmp3(v, b) == 0;
        return true;
    }
    return true;
}

static Result resolve(const ResCase &c) {
    Result r;
    for (const auto &kv : c.requirements) {
        const std::string &name = kv.first;
        const std::string &constraint = kv.second;
        int best[3] = {0, 0, 0};
        bool have = false;
        std::string bestVer;
        auto it = c.registry.find(name);
        if (it != c.registry.end()) {
            for (const auto &e : it->second) {
                if (e.yanked)
                    continue;
                int v[3];
                if (!naiveVer(e.version, v))
                    continue;
                if (!naiveSat(v, constraint))
                    continue;
                if (!have || cmp3(v, best) > 0) {
                    for (int i = 0; i < 3; i++)
                        best[i] = v[i];
                    bestVer = e.version;
                    have = true;
                }
            }
        }
        if (have)
            r.install.push_back({name, bestVer});
    }
    return r;
}

// ============================================================================

int main() {
    std::string data((std::istreambuf_iterator<char>(std::cin)), std::istreambuf_iterator<char>());
    JsonValue root;
    try {
        JsonParser p(data);
        root = p.parse();
    } catch (const std::exception &ex) {
        std::cerr << "invalid json input: " << ex.what() << "\n";
        return 1;
    }
    if (root.type != JsonValue::Arr) {
        std::cerr << "invalid json input: expected an array of cases\n";
        return 1;
    }
    std::vector<Result> results;
    results.reserve(root.arr.size());
    for (const auto &cv : root.arr)
        results.push_back(resolve(parseCase(cv)));
    std::cout << serialize(results) << "\n";
    return 0;
}
