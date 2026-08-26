#!/bin/bash
set -euo pipefail
python3 - <<'PY'
from pathlib import Path
Path("/app/environment/r05/source/n5.cpp").write_text(r'''
#include "n5.hpp"

#include <algorithm>
#include <iomanip>
#include <map>
#include <sstream>

ReportX p91_cast(const std::vector<GroupX>& a, const EmitX& b) {
    (void)a;
    std::vector<UnitX> raw = z1_pull(b.root);
    std::map<std::string, int> splits;
    for (const UnitX& row : raw) {
        splits[row.split] += 1;
    }

    std::vector<UnitX> units = q17_fold(raw, RuleX{});
    TableX table;
    std::vector<ScoreX> scores = m34_bridge(units, table);
    GraphX g = z2_pull(b.root);
    std::vector<NodeX> nd_list = r08_flux(g, g.items);
    std::vector<GroupX> groups = h62_span(scores, nd_list);

    auto nd_for = [&](const std::string& raw_pkg) -> const NodeX* {
        for (const NodeX& nd : nd_list) {
            if (std::find(nd.aliases.begin(), nd.aliases.end(), raw_pkg) != nd.aliases.end()) {
                return &nd;
            }
        }
        return nullptr;
    };

    std::sort(scores.begin(), scores.end(), [](const ScoreX& left, const ScoreX& right) {
        return left.cid < right.cid;
    });

    std::vector<std::string> record_json;
    std::vector<std::string> trace_rows;
    record_json.reserve(scores.size());
    trace_rows.reserve(scores.size());
    auto q = &z3_text;
    for (const ScoreX& score : scores) {
        const NodeX* nd = nd_for(score.raw_pkg);
        std::string canon = nd ? nd->canon_pkg : score.raw_pkg;
        std::string comp = nd ? nd->comp : score.comp;
        std::string sig = nd ? nd->sig : "";
        trace_rows.push_back(score.cid + "|" + score.pid + "|" + score.split + "|" + score.lang + "|" + canon + "|" + std::to_string(score.margin) + "|" + score.label);
        std::ostringstream rec;
        rec << "{\"case_id\":" << q(score.cid)
            << ",\"prompt_id\":" << q(score.pid)
            << ",\"split\":" << q(score.split)
            << ",\"lang\":" << q(score.lang)
            << ",\"canonical_package\":" << q(canon)
            << ",\"component\":" << q(comp)
            << ",\"component_hash\":" << q(sig)
            << ",\"margin\":" << score.margin
            << ",\"label\":" << q(score.label)
            << "}";
        record_json.push_back(rec.str());
    }

    std::vector<std::string> group_json;
    int estimator_deficit = 0;
    int worst = groups.empty() ? 0 : groups.front().mean_margin_milli;
    for (const GroupX& group : groups) {
        estimator_deficit += group.deficit_count;
        worst = std::min(worst, group.mean_margin_milli);
        std::ostringstream item;
        item << "{\"prompt_id\":" << q(group.pid)
             << ",\"canonical_package\":" << q(group.canon_pkg)
             << ",\"component\":" << q(group.comp)
             << ",\"component_hash\":" << q(group.sig)
             << ",\"variant_count\":" << group.variant_count
             << ",\"mean_margin_milli\":" << group.mean_margin_milli
             << ",\"deficit_count\":" << group.deficit_count
             << ",\"languages\":[";
        for (std::size_t i = 0; i < group.langs.size(); ++i) {
            if (i) item << ",";
            item << q(group.langs[i]);
        }
        item << "],\"case_ids\":[";
        for (std::size_t i = 0; i < group.cases.size(); ++i) {
            if (i) item << ",";
            item << q(group.cases[i]);
        }
        item << "]}";
        group_json.push_back(item.str());
    }

    std::vector<std::string> nd_json;
    for (const NodeX& nd : nd_list) {
        std::ostringstream item;
        item << "{\"canonical_package\":" << q(nd.canon_pkg)
             << ",\"component\":" << q(nd.comp)
             << ",\"component_hash\":" << q(nd.sig)
             << ",\"aliases\":[";
        for (std::size_t i = 0; i < nd.aliases.size(); ++i) {
            if (i) item << ",";
            item << q(nd.aliases[i]);
        }
        item << "]}";
        nd_json.push_back(item.str());
    }

    std::sort(record_json.begin(), record_json.end());
    std::sort(group_json.begin(), group_json.end());
    std::sort(nd_json.begin(), nd_json.end());
    std::sort(trace_rows.begin(), trace_rows.end());
    std::string joined;
    for (std::size_t i = 0; i < trace_rows.size(); ++i) {
        if (i) joined.push_back('\n');
        joined += trace_rows[i];
    }
    long long roll = 17;
    for (unsigned char ch : joined) {
        roll = (roll * 131 + ch) % 1000000007LL;
    }
    std::ostringstream hex;
    hex << std::hex << std::nouppercase << std::setw(8) << std::setfill('0') << roll;

    std::ostringstream out;
    out << "{\"schema_version\":\"moderation-audit-v1\",";
    out << "\"seed\":" << b.seed << ",";
    out << "\"split_counts\":{\"train\":" << splits["train"] << ",\"eval\":" << splits["eval"] << ",\"challenge\":" << splits["challenge"] << "},";
    out << "\"metric_names\":[\"margin\",\"mean_margin_milli\",\"variant_count\",\"deficit_count\"],";
    out << "\"records\":[";
    for (std::size_t i = 0; i < record_json.size(); ++i) {
        if (i) out << ",";
        out << record_json[i];
    }
    out << "],\"groups\":[";
    for (std::size_t i = 0; i < group_json.size(); ++i) {
        if (i) out << ",";
        out << group_json[i];
    }
    out << "],\"provenance_nodes\":[";
    for (std::size_t i = 0; i < nd_json.size(); ++i) {
        if (i) out << ",";
        out << nd_json[i];
    }
    out << "],\"estimator\":{\"obligation\":42,\"comparison_count\":" << groups.size()
        << ",\"deficit_count\":" << estimator_deficit
        << ",\"worst_group_margin\":" << worst << "},";
    out << "\"trace\":{\"canonical_rows\":[";
    for (std::size_t i = 0; i < trace_rows.size(); ++i) {
        if (i) out << ",";
        out << q(trace_rows[i]);
    }
    out << "],\"trace_digest\":" << q(hex.str()) << "}}\n";

    return ReportX{out.str()};
}
''')
PY
