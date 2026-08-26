#!/usr/bin/env bash
set -euo pipefail

log() { printf '[solve] %s\n' "$1"; }

ENV="/app/environment"
OUT=/app/output/failover_report.json

log "repair membership admit (drop staging-only ghosts)"
cat > "${ENV}/p3k/src/tbl_mux.cpp" <<'CPP'
#include "vx_types.hpp"

#include <fstream>
#include <set>
#include <string>
#include <vector>

std::vector<std::string> ReadStaging(const std::string& path) {
    std::vector<std::string> out;
    std::ifstream in(path);
    if (!in) return out;
    std::string body((std::istreambuf_iterator<char>(in)), std::istreambuf_iterator<char>());
    size_t i = 0;
    while (i < body.size()) {
        if (body[i] == '"') {
            size_t j = body.find('"', i + 1);
            if (j == std::string::npos) break;
            out.push_back(body.substr(i + 1, j - i - 1));
            i = j + 1;
        } else {
            ++i;
        }
    }
    return out;
}

std::pair<uint8_t, std::vector<std::string>> FnR4(const std::string& tbl_path,
                                                  const std::vector<std::string>& seed_ids) {
    auto staged = ReadStaging(tbl_path);
    std::set<std::string> present(staged.begin(), staged.end());
    std::vector<std::string> out;
    for (const auto& id : seed_ids) {
        if (present.count(id)) out.push_back(id);
    }
    if (out.empty()) return {0, {}};
    return {1, out};
}
CPP

log "repair generation flush advance"
cat > "${ENV}/q7n/src/gen_mux.cpp" <<'CPP'
#include "vx_types.hpp"

uint64_t FnM7(uint64_t gen, bool flush) {
    return flush ? gen + 1 : gen;
}
CPP

log "repair ordering prefix gate"
cat > "${ENV}/t2w/src/ord_mux.cpp" <<'CPP'
#include "vx_types.hpp"

#include <string>
#include <vector>

static bool starts_with(const std::vector<uint8_t>& v, const std::string& p) {
    if (v.size() < p.size()) return false;
    for (size_t i = 0; i < p.size(); ++i) {
        if (static_cast<char>(v[i]) != p[i]) return false;
    }
    return true;
}

uint8_t FnN2(const std::vector<uint8_t>& a, const std::vector<uint8_t>& b) {
    return (starts_with(a, "M0|") && starts_with(b, "T1|")) ? 1 : 0;
}
CPP

log "repair journal fingerprint + epoch/digest commit/ack"
cat > "${ENV}/u8m/src/jrnl_mux.cpp" <<'CPP'
#include "vx_types.hpp"

#include <fstream>
#include <sstream>
#include <string>

std::string HashMaterial(const std::string& notes, const std::string& triple, int seed) {
    return md5_hex16(notes + "|" + triple + "|" + std::to_string(seed));
}

bool ReadField(const std::string& path, const std::string& key, std::string& out) {
    std::ifstream in(path);
    if (!in) return false;
    std::string line;
    std::string prefix = key + "=";
    while (std::getline(in, line)) {
        if (line.rfind(prefix, 0) == 0) {
            out = line.substr(prefix.size());
            while (!out.empty() && (out.back() == ' ' || out.back() == '\r')) out.pop_back();
            return true;
        }
    }
    return false;
}

int FnS5(const std::string& path, const std::string& fp, const std::string& mode, uint64_t epoch,
         const std::string& digest) {
    if (mode == "commit") {
        std::ofstream out(path);
        out << "epoch=" << epoch << "\ncompile_fp=" << fp << "\nmembership_digest=" << digest
            << "\nreplay_ack=0\n";
        return 0;
    }
    std::string current;
    bool have = ReadField(path, "compile_fp", current);
    if (mode == "ready") {
        return (have && current == fp) ? 0 : 1;
    }
    if (mode == "ack") {
        if (!have || current != fp) return 1;
        std::string epoch_s = "1";
        std::string e;
        if (ReadField(path, "epoch", e)) epoch_s = e;
        std::string dig;
        ReadField(path, "membership_digest", dig);
        std::ofstream out(path);
        out << "epoch=" << epoch_s << "\ncompile_fp=" << current << "\nmembership_digest=" << dig
            << "\nreplay_ack=1\n";
        return 0;
    }
    return 1;
}

uint32_t FnMerge(uint64_t line_epoch, uint64_t state_epoch, const std::string& line_digest,
                 const std::string& state_digest, uint32_t pending_after_decay, uint32_t fixture_max,
                 uint32_t persisted_pending) {
    if (line_epoch == state_epoch && line_digest == state_digest && !line_digest.empty()) {
        return pending_after_decay;
    }
    return fixture_max > persisted_pending ? fixture_max : persisted_pending;
}
CPP

log "repair ARP decay-once + epoch bump"
cat > "${ENV}/n9p/src/arp_mux.cpp" <<'CPP'
#include "vx_types.hpp"

#include <cstdint>

uint32_t FnDecay(uint32_t pending) {
    return pending > 0 ? pending - 1 : 0;
}

uint64_t FnBump(uint64_t epoch) {
    return epoch + 1;
}
CPP

log "repair settle-chain fold (identity carry of previous bind)"
cat > "${ENV}/k7r/src/chain_mux.cpp" <<'CPP'
#include "vx_types.hpp"

#include <cstdint>
#include <string>

std::string FnK7(const std::string& prev) {
    return prev;
}

uint64_t FnArm(uint64_t settle_epoch) {
    return settle_epoch;
}
CPP

log "repair bind live seal cross-check"
cat > "${ENV}/v5r/src/bind_mux.cpp" <<'CPP'
#include "vx_types.hpp"

#include <string>

uint8_t BindOK(const std::string& seal, const std::string& id, const std::string& facet) {
    std::string needle = "\"" + id + "\": \"" + facet + "\"";
    size_t count = 0;
    size_t pos = 0;
    while ((pos = seal.find(needle, pos)) != std::string::npos) {
        ++count;
        pos += needle.size();
    }
    return count == 1 ? 1 : 0;
}
CPP

log "repair status-view predicate (settled AND img_rc=1)"
cat > "${ENV}/w4z/src/view_mux.cpp" <<'CPP'
#include "vx_types.hpp"

#include <cctype>
#include <string>

static bool json_string_eq(const std::string& json, const std::string& key, const std::string& want) {
    const std::string needle = "\"" + key + "\"";
    size_t pos = 0;
    while ((pos = json.find(needle, pos)) != std::string::npos) {
        size_t i = pos + needle.size();
        while (i < json.size() && std::isspace(static_cast<unsigned char>(json[i]))) ++i;
        if (i >= json.size() || json[i] != ':') {
            pos += needle.size();
            continue;
        }
        ++i;
        while (i < json.size() && std::isspace(static_cast<unsigned char>(json[i]))) ++i;
        if (i >= json.size() || json[i] != '"') {
            pos += needle.size();
            continue;
        }
        ++i;
        size_t end = json.find('"', i);
        if (end == std::string::npos) return false;
        if (json.substr(i, end - i) == want) return true;
        pos = end + 1;
    }
    return false;
}

static bool json_int_eq(const std::string& json, const std::string& key, int want) {
    const std::string needle = "\"" + key + "\"";
    size_t pos = 0;
    while ((pos = json.find(needle, pos)) != std::string::npos) {
        size_t i = pos + needle.size();
        while (i < json.size() && std::isspace(static_cast<unsigned char>(json[i]))) ++i;
        if (i >= json.size() || json[i] != ':') {
            pos += needle.size();
            continue;
        }
        ++i;
        while (i < json.size() && std::isspace(static_cast<unsigned char>(json[i]))) ++i;
        if (i >= json.size() || !(std::isdigit(static_cast<unsigned char>(json[i])) || json[i] == '-')) {
            pos += needle.size();
            continue;
        }
        size_t j = i;
        if (json[j] == '-') ++j;
        while (j < json.size() && std::isdigit(static_cast<unsigned char>(json[j]))) ++j;
        try {
            if (std::stoi(json.substr(i, j - i)) == want) return true;
        } catch (...) {
        }
        pos = j;
    }
    return false;
}

std::pair<std::string, bool> emit_lane_view(const std::string& report_json) {
    bool settled = json_string_eq(report_json, "sync_label", "settled");
    bool has_image = json_int_eq(report_json, "img_rc", 1);
    if (settled && has_image) {
        return {"settled", true};
    }
    return {"pending", false};
}
CPP

log "repair seal gate (settled + image + flow digest)"
cat > "${ENV}/g6k/src/gate_mux.cpp" <<'CPP'
#include "vx_types.hpp"

#include <cctype>
#include <string>

static bool json_string_eq(const std::string& json, const std::string& key, const std::string& want) {
    const std::string needle = "\"" + key + "\"";
    size_t pos = 0;
    while ((pos = json.find(needle, pos)) != std::string::npos) {
        size_t i = pos + needle.size();
        while (i < json.size() && std::isspace(static_cast<unsigned char>(json[i]))) ++i;
        if (i >= json.size() || json[i] != ':') {
            pos += needle.size();
            continue;
        }
        ++i;
        while (i < json.size() && std::isspace(static_cast<unsigned char>(json[i]))) ++i;
        if (i >= json.size() || json[i] != '"') {
            pos += needle.size();
            continue;
        }
        ++i;
        size_t end = json.find('"', i);
        if (end == std::string::npos) return false;
        if (json.substr(i, end - i) == want) return true;
        pos = end + 1;
    }
    return false;
}

static bool json_int_eq(const std::string& json, const std::string& key, int want) {
    const std::string needle = "\"" + key + "\"";
    size_t pos = 0;
    while ((pos = json.find(needle, pos)) != std::string::npos) {
        size_t i = pos + needle.size();
        while (i < json.size() && std::isspace(static_cast<unsigned char>(json[i]))) ++i;
        if (i >= json.size() || json[i] != ':') {
            pos += needle.size();
            continue;
        }
        ++i;
        while (i < json.size() && std::isspace(static_cast<unsigned char>(json[i]))) ++i;
        if (i >= json.size() || !(std::isdigit(static_cast<unsigned char>(json[i])) || json[i] == '-')) {
            pos += needle.size();
            continue;
        }
        size_t j = i;
        if (json[j] == '-') ++j;
        while (j < json.size() && std::isdigit(static_cast<unsigned char>(json[j]))) ++j;
        try {
            if (std::stoi(json.substr(i, j - i)) == want) return true;
        } catch (...) {
        }
        pos = j;
    }
    return false;
}

bool FnGate(const std::string& report_json, const std::string& flow_digest) {
    bool settled = json_string_eq(report_json, "sync_label", "settled");
    bool has_image = json_int_eq(report_json, "img_rc", 1);
    bool digest_ok = flow_digest.size() == 16;
    for (char c : flow_digest) {
        if (!((c >= '0' && c <= '9') || (c >= 'a' && c <= 'f'))) digest_ok = false;
    }
    return settled && has_image && digest_ok;
}
CPP

log "repair seal replace-in-place (collapse duplicate permits)"
cat > "${ENV}/x1h/src/seal_mux.cpp" <<'CPP'
#include "vx_types.hpp"

#include <fstream>
#include <sstream>
#include <string>
#include <vector>

static std::string seal_path(const std::string& root) { return root + "/meta/seal.bin"; }

std::string ReadSeal(const std::string& root) {
    std::ifstream in(seal_path(root));
    if (!in) return "";
    std::string body((std::istreambuf_iterator<char>(in)), std::istreambuf_iterator<char>());
    return body;
}

int RefreshSeal(const std::string& root, const std::string& id, const std::string& facet) {
    std::vector<std::string> lines;
    {
        std::ifstream in(seal_path(root));
        std::string line;
        while (std::getline(in, line)) lines.push_back(line);
    }
    std::string key = "\"" + id + "\":";
    std::string replacement = "\"" + id + "\": \"" + facet + "\"";
    std::vector<std::string> kept;
    bool wrote = false;
    for (const auto& line : lines) {
        if (line.rfind(key, 0) == 0) {
            if (!wrote) {
                kept.push_back(replacement);
                wrote = true;
            }
            // drop prior duplicate permits for this id
            continue;
        }
        kept.push_back(line);
    }
    if (!wrote) kept.push_back(replacement);
    std::ofstream out(seal_path(root), std::ios::trunc);
    if (!out) return 1;
    for (const auto& line : kept) out << line << "\n";
    return 0;
}
CPP

log "repair emit (seal refresh then bind)"
cat > "${ENV}/engine/src/ph_emit.cpp" <<'CPP'
#include "ph_iface.hpp"
#include "vx_types.hpp"

#include <cstdint>
#include <string>

extern int RefreshSeal(const std::string& root, const std::string& id, const std::string& facet);
extern std::string ReadSeal(const std::string& root);
extern uint8_t BindOK(const std::string& seal, const std::string& id, const std::string& facet);

Row emit_row_phase(const std::string& env_root, const std::string& lane_id, int loc_rc, int img_rc,
                   int lag_code, const std::string& facet) {
    RefreshSeal(env_root, lane_id, facet);
    std::string seal = ReadSeal(env_root);
    int bind = BindOK(seal, lane_id, facet);
    Row row;
    row.lane_id = lane_id;
    row.loc_rc = loc_rc;
    row.img_rc = img_rc;
    row.bind_rc = bind;
    row.lag_code = lag_code;
    row.facet_hex = facet;
    return row;
}
CPP

log "repair q2m mirror push after seal"
cat > "${ENV}/engine/src/sync_q2m.cpp" <<'CPP'
#include "ph_iface.hpp"

#include <cstdlib>
#include <string>

void sync_q2m_mirrors(const std::string& env_root) {
    static const char* mods[] = {"p3k", "q7n", "t2w", "u8m", "v5r", "x1h", "w4z", "n9p", "g6k",
                                 "k7r", nullptr};
    for (const char** m = mods; *m; ++m) {
        std::string cmd = "mkdir -p \"" + env_root + "/q2m/" + *m + "/src\" && cp -a \"" +
                          env_root + "/" + *m + "/src/.\" \"" + env_root + "/q2m/" + *m + "/src/\"";
        std::system(cmd.c_str());
    }
}
CPP

log "mirror repaired graded muxes into q2m (driver refreshes from q2m)"
for m in p3k q7n t2w u8m v5r x1h w4z n9p g6k k7r; do
  mkdir -p "${ENV}/q2m/${m}/src"
  cp -a "${ENV}/${m}/src/." "${ENV}/q2m/${m}/src/"
done

log "rebuild driver + probe"
cd "${ENV}"
cmake -B build -DCMAKE_BUILD_TYPE=Release
cmake --build build
mkdir -p /app/bin /app/output
cp build/vx_bond /app/bin/vx_run

log "reset seal scaffolding, zero lineage ledger, and run prep -> seal (seed 0)"
printf '"axle": "0000000000000000"\n"rotor": "1111111111111111"\n' > "${ENV}/meta/seal.bin"
cat > "${ENV}/meta/lineage.json" <<'JSON'
{
  "pack_epoch": 0,
  "settle_epoch": 0,
  "seed": -1,
  "chain_prev": "",
  "chain_bind": "",
  "last_matrix": ""
}
JSON
rm -rf /app/output/run_traces
rm -f /app/output/runtime_state.json /app/output/arp_journal.jsonl /app/output/failover_report.json
VX_ENV_ROOT="${ENV}" /app/bin/vx_run --profile prep --variant-seed 0 --out "${OUT}"
VX_ENV_ROOT="${ENV}" /app/bin/vx_run --profile seal --variant-seed 0 --out "${OUT}"

log "sanity-check output contract"
python3 <<'PY'
import hashlib
import json
import subprocess
from pathlib import Path

def md5_16(s: str) -> str:
    return hashlib.md5(s.encode("utf-8")).hexdigest()[:16]

env = Path("/app/environment")
ids = [ln.strip() for ln in (env / "docs" / "member_ids.txt").read_text(encoding="utf-8").splitlines() if ln.strip()]
notes = ",".join(ids)
seed = 0
triple = "x86_64-linux"
cur = -1
for line in (env / "data" / "rank_tbl.toml").read_text(encoding="utf-8").splitlines():
    line = line.strip()
    if line.startswith("seed"):
        cur = int(line.split("=", 1)[1].strip())
    if line.startswith("triple") and cur == seed:
        triple = line.split("=", 1)[1].strip().strip('"')
want_fp = md5_16(f"{notes}|{triple}|{seed}")
want_md = md5_16("bond|" + ",".join(ids))

data = json.loads(Path("/app/output/failover_report.json").read_text(encoding="utf-8"))
assert data["summary"]["sync_label"] == "settled", data["summary"]
assert data["summary"]["span_band"] == 0
assert data["summary"]["rows_total"] == len(data["rows"]) == 6
for row in data["rows"]:
    assert row["lag_code"] == 0
    assert row["loc_rc"] == row["img_rc"] == row["bind_rc"] == 1
    assert len(row["facet_hex"]) == 16
by = {r["lane_id"]: r for r in data["rows"]}
for a, b in [("axle", "axle_echo"), ("rotor", "rotor_echo"), ("stator", "stator_echo")]:
    assert by[a]["facet_hex"] == by[b]["facet_hex"]
assert "ghost0" not in by
journal_path = Path("/app/output/run_traces/session.journal")
journal = journal_path.read_text(encoding="utf-8")
assert "replay_ack=1" in journal
fields = {}
for line in journal.splitlines():
    if "=" in line:
        k, v = line.split("=", 1)
        fields[k.strip()] = v.strip()
assert fields.get("compile_fp") == want_fp, (fields.get("compile_fp"), want_fp)
assert fields.get("membership_digest") == want_md, (fields.get("membership_digest"), want_md)
arp_path = Path("/app/output/arp_journal.jsonl")
assert arp_path.is_file()
for line in arp_path.read_text(encoding="utf-8").splitlines():
    if not line.strip():
        continue
    row = json.loads(line)
    assert row["membership_digest"] == want_md, row
state = json.loads(Path("/app/output/runtime_state.json").read_text(encoding="utf-8"))
assert state["epoch"] >= 1
lineage = json.loads(Path("/app/environment/meta/lineage.json").read_text(encoding="utf-8"))
assert lineage["pack_epoch"] == 1 and lineage["settle_epoch"] == 1, lineage
assert lineage["seed"] == 0
assert lineage["last_matrix"] == data["summary"]["matrix_digest"]
assert lineage["chain_prev"] == ""
want_bind = md5_16("|" + data["summary"]["matrix_digest"] + "|1")
assert lineage["chain_bind"] == want_bind, (lineage["chain_bind"], want_bind)
assert data["summary"]["pack_epoch"] == 1
assert data["summary"]["settle_epoch"] == 1
assert data["summary"]["chain_bind"] == want_bind
seal = Path("/app/environment/meta/seal.bin").read_text(encoding="utf-8")
for lane in by:
    assert seal.count(f'"{lane}":') == 1
probe = "/app/environment/build/bond_probe"
out = subprocess.check_output([probe, "/app/output/failover_report.json"], text=True)
assert "label=settled" in out and "converged=1" in out
syn = Path("/tmp/vx_probe_syn.json")
syn.write_text(
    '{"rows":[{"lane_id":"axle","loc_rc":1,"img_rc":10,"bind_rc":1,"lag_code":0,"facet_hex":"'
    + ("0" * 16)
    + '"}],"summary":{"rows_total":1,"sync_label":"settled","span_band":0,"matrix_digest":"'
    + ("0" * 16)
    + '"}}',
    encoding="utf-8",
)
out = subprocess.check_output([probe, syn.as_posix()], text=True)
assert "label=pending" in out and "converged=0" in out
PY

log "second workflow: verify settle chain extends"
VX_ENV_ROOT="${ENV}" /app/bin/vx_run --profile prep --variant-seed 0 --out "${OUT}"
VX_ENV_ROOT="${ENV}" /app/bin/vx_run --profile seal --variant-seed 0 --out "${OUT}"
python3 <<'PY'
import hashlib
import json
from pathlib import Path

def md5_16(s: str) -> str:
    return hashlib.md5(s.encode("utf-8")).hexdigest()[:16]

data = json.loads(Path("/app/output/failover_report.json").read_text(encoding="utf-8"))
assert data["summary"]["sync_label"] == "settled", data["summary"]
lineage = json.loads(Path("/app/environment/meta/lineage.json").read_text(encoding="utf-8"))
assert lineage["pack_epoch"] == 2 and lineage["settle_epoch"] == 2, lineage
d = data["summary"]["matrix_digest"]
b1 = md5_16("|" + d + "|1")
b2 = md5_16(b1 + "|" + d + "|2")
assert lineage["chain_prev"] == b1, lineage
assert lineage["chain_bind"] == b2, lineage
assert data["summary"]["chain_bind"] == b2
PY

log "done"
