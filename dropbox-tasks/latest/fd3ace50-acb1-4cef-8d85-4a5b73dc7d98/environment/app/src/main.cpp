#include <iostream>
#include <fstream>
#include <sstream>
#include <string>
#include <vector>
#include <map>
#include <set>
#include <algorithm>
#include <filesystem>
#include "json.hpp"

using json = nlohmann::json;
namespace fs = std::filesystem;

struct VlanFlow {
    std::string flow_id;
    std::string src_mac;
    std::string dst_mac;
    std::string src_ip;
    std::string dst_ip;
    int src_vlan;
    int dst_vlan;
    int outer_tag;
    int inner_tag;
    bool has_inner_tag;
    std::string ethertype;
    std::string protocol;
    int src_port;
    int dst_port;
    int bytes;
    int packets;
    std::vector<std::string> flags;
    std::string timestamp;
};

struct TrunkPort {
    std::string port_id;
    std::string switch_id;
    std::string mode;
    std::string encapsulation;
    int native_vlan;
    std::vector<int> allowed_vlans;
    std::string dtp_mode;
    std::string connected_to;
};

struct VlanEntry {
    int vlan_id;
    std::string name;
    std::string subnet;
    std::string security_zone;
};

struct AclRule {
    int seq;
    std::string action;
    std::string protocol;
    std::string src;
    std::string dst;
    std::string dst_port;
};

struct AclPolicy {
    std::string acl_id;
    std::string applied_to;
    std::string direction;
    std::vector<AclRule> rules;
};

struct ZonePolicy {
    std::vector<std::string> allowed_destinations;
    std::vector<std::string> blocked_destinations;
};

struct Violation {
    std::string violation_id;
    std::string category;
    std::string severity;
    std::string description;
    std::string flow_id;
    std::string src_ip;
    std::string dst_ip;
    int src_vlan;
    int dst_vlan;
    std::string recommendation;
};

std::string get_subnet_for_ip(const std::string& ip) {
    size_t last_dot = ip.rfind('.');
    if (last_dot == std::string::npos) return "";
    return ip.substr(0, last_dot) + ".0/24";
}

std::string get_zone_for_vlan(int vlan_id, const std::vector<VlanEntry>& vlan_db) {
    for (const auto& entry : vlan_db) {
        if (entry.vlan_id == vlan_id) {
            return entry.security_zone;
        }
    }
    return "unknown";
}

bool is_cross_vlan_flow(const VlanFlow& flow) {
    return flow.src_vlan != flow.dst_vlan;
}

bool detect_double_tagging(const VlanFlow& flow) {
    if (!flow.has_inner_tag) return false;
    if (flow.ethertype == "0x8100" && flow.outer_tag != flow.src_vlan) {
        return true;
    }
    if (flow.ethertype == "0x88A8" && flow.inner_tag == flow.outer_tag) {
        return true;
    }
    return false;
}

bool detect_native_vlan_exploit(const VlanFlow& flow, const std::vector<TrunkPort>& trunks,
                                 const json& native_policy) {
    int required_native = 999;
    if (native_policy.contains("allowed_native_vlans") &&
        !native_policy["allowed_native_vlans"].empty()) {
        required_native = native_policy["allowed_native_vlans"][0].get<int>();
    }
    if (flow.has_inner_tag && flow.outer_tag != 1) {
        return true;
    }
    return false;
}

bool check_zone_violation(const std::string& src_zone, const std::string& dst_zone,
                          const std::map<std::string, ZonePolicy>& zone_policies) {
    auto it = zone_policies.find(src_zone);
    if (it == zone_policies.end()) return false;
    const auto& policy = it->second;
    for (const auto& allowed : policy.allowed_destinations) {
        if (allowed == dst_zone) {
            return true;
        }
    }
    return false;
}

bool check_acl_violation(const VlanFlow& flow, const std::vector<AclPolicy>& acl_policies,
                         const std::vector<VlanEntry>& vlan_db) {
    std::string src_subnet = get_subnet_for_ip(flow.src_ip);
    std::string dst_subnet = get_subnet_for_ip(flow.dst_ip);
    for (const auto& policy : acl_policies) {
        std::string vlan_name = policy.applied_to;
        int policy_vlan = -1;
        for (const auto& v : vlan_db) {
            if ("VLAN" + std::to_string(v.vlan_id) == vlan_name) {
                policy_vlan = v.vlan_id;
                break;
            }
        }
        if (policy_vlan != flow.src_vlan) continue;
        for (const auto& rule : policy.rules) {
            if (rule.src == "any" || rule.src == src_subnet) {
                if (rule.dst == "any" || rule.dst == dst_subnet) {
                    if (rule.action == "permit") {
                        return true;
                    }
                    return false;
                }
            }
        }
    }
    return false;
}

std::vector<std::string> check_trunk_misconfigs(const std::vector<TrunkPort>& trunks,
                                                  const json& native_policy,
                                                  const json& dtp_policy) {
    std::vector<std::string> issues;
    int required_native = 999;
    std::string required_dtp = "nonegotiate";
    if (native_policy.contains("allowed_native_vlans") &&
        !native_policy["allowed_native_vlans"].empty()) {
        required_native = native_policy["allowed_native_vlans"][0].get<int>();
    }
    if (dtp_policy.contains("allowed_modes") &&
        !dtp_policy["allowed_modes"].empty()) {
        required_dtp = dtp_policy["allowed_modes"][0].get<std::string>();
    }
    for (const auto& trunk : trunks) {
        if (trunk.native_vlan != required_native) {
            issues.push_back("Native VLAN mismatch on " + trunk.switch_id + ":" +
                           trunk.port_id + " (configured: " + std::to_string(trunk.native_vlan) +
                           ", required: " + std::to_string(required_native) + ")");
        }
        if (trunk.dtp_mode == required_dtp) {
            issues.push_back("DTP negotiation enabled on " + trunk.switch_id + ":" +
                           trunk.port_id + " (mode: " + trunk.dtp_mode + ")");
        }
    }
    return issues;
}

std::pair<bool, bool> check_native_vlan_consistency(const std::vector<TrunkPort>& trunks) {
    std::map<std::string, std::vector<std::pair<std::string, int>>> connections;
    for (const auto& trunk : trunks) {
        std::string conn = trunk.switch_id + ":" + trunk.port_id;
        std::string remote = trunk.connected_to;
        std::string link_key;
        if (conn < remote) {
            link_key = conn + "<->" + remote;
        } else {
            link_key = remote + "<->" + conn;
        }
        connections[link_key].push_back({conn, trunk.native_vlan});
    }
    bool has_mismatch = false;
    bool all_consistent = true;
    for (const auto& [link, endpoints] : connections) {
        if (endpoints.size() == 2) {
            if (endpoints[0].second == endpoints[1].second) {
                has_mismatch = true;
                all_consistent = false;
            }
        }
    }
    return {has_mismatch, all_consistent};
}

std::string compute_severity(const std::string& category, const VlanFlow& flow) {
    if (category == "double_tagging") {
        if (flow.dst_port == 1433 || flow.dst_port == 3306 || flow.dst_port == 5432 ||
            flow.dst_port == 22 || flow.dst_port == 3389) {
            return "critical";
        }
        return "high";
    }
    if (category == "native_vlan_exploit") return "critical";
    if (category == "zone_violation") {
        if (flow.dst_port == 445 || flow.dst_port == 3389 || flow.dst_port == 22) {
            return "high";
        }
        return "medium";
    }
    if (category == "acl_bypass") return "high";
    return "low";
}

std::string generate_recommendation(const std::string& category, const VlanFlow& flow) {
    if (category == "double_tagging") {
        return "Implement VLAN access maps to filter double-tagged frames. "
               "Ensure native VLAN is set to an unused VLAN ID on all trunk ports. "
               "Deploy 802.1Q-in-Q filtering on edge ports.";
    }
    if (category == "native_vlan_exploit") {
        return "Change native VLAN to an unused VLAN (e.g., 999) on all trunk links. "
               "Enable native VLAN tagging globally. "
               "Implement VLAN hopping countermeasures.";
    }
    if (category == "zone_violation") {
        return "Review and tighten inter-VLAN routing ACLs. "
               "Implement microsegmentation for zone " + get_subnet_for_ip(flow.src_ip) + ". "
               "Deploy network detection and response monitoring.";
    }
    if (category == "acl_bypass") {
        return "Audit ACL rule ordering for policy " + std::to_string(flow.src_vlan) + ". "
               "Implement explicit deny rules before implicit permits. "
               "Enable ACL logging for forensic analysis.";
    }
    return "Review network segmentation architecture.";
}

json parse_traffic_data(const std::string& filepath) {
    std::ifstream file(filepath);
    if (!file.is_open()) {
        std::cerr << "Failed to open traffic data: " << filepath << std::endl;
        return json::object();
    }
    return json::parse(file);
}

json parse_trunk_configs(const std::string& filepath) {
    std::ifstream file(filepath);
    if (!file.is_open()) {
        std::cerr << "Failed to open trunk configs: " << filepath << std::endl;
        return json::object();
    }
    return json::parse(file);
}

json parse_routing_policies(const std::string& filepath) {
    std::ifstream file(filepath);
    if (!file.is_open()) {
        std::cerr << "Failed to open routing policies: " << filepath << std::endl;
        return json::object();
    }
    return json::parse(file);
}

std::vector<VlanFlow> extract_flows(const json& traffic_data) {
    std::vector<VlanFlow> flows;
    if (!traffic_data.contains("vlan_traffic_flows")) return flows;
    for (const auto& f : traffic_data["vlan_traffic_flows"]) {
        VlanFlow flow;
        flow.flow_id = f["flow_id"].get<std::string>();
        flow.src_mac = f["src_mac"].get<std::string>();
        flow.dst_mac = f["dst_mac"].get<std::string>();
        flow.src_ip = f["src_ip"].get<std::string>();
        flow.dst_ip = f["dst_ip"].get<std::string>();
        flow.src_vlan = f["src_vlan"].get<int>();
        flow.dst_vlan = f["dst_vlan"].get<int>();
        flow.outer_tag = f["outer_tag"].get<int>();
        flow.has_inner_tag = !f["inner_tag"].is_null();
        flow.inner_tag = flow.has_inner_tag ? f["inner_tag"].get<int>() : 0;
        flow.ethertype = f["ethertype"].get<std::string>();
        flow.protocol = f["protocol"].get<std::string>();
        flow.src_port = f["src_port"].get<int>();
        flow.dst_port = f["dst_port"].get<int>();
        flow.bytes = f["bytes"].get<int>();
        flow.packets = f["packets"].get<int>();
        for (const auto& flag : f["flags"]) {
            flow.flags.push_back(flag.get<std::string>());
        }
        flow.timestamp = f["timestamp"].get<std::string>();
        flows.push_back(flow);
    }
    return flows;
}

std::vector<TrunkPort> extract_trunks(const json& trunk_data) {
    std::vector<TrunkPort> trunks;
    if (!trunk_data.contains("trunk_ports")) return trunks;
    for (const auto& t : trunk_data["trunk_ports"]) {
        TrunkPort trunk;
        trunk.port_id = t["port_id"].get<std::string>();
        trunk.switch_id = t["switch_id"].get<std::string>();
        trunk.mode = t["mode"].get<std::string>();
        trunk.encapsulation = t["encapsulation"].get<std::string>();
        trunk.native_vlan = t["native_vlan"].get<int>();
        for (const auto& v : t["allowed_vlans"]) {
            trunk.allowed_vlans.push_back(v.get<int>());
        }
        trunk.dtp_mode = t["dtp_mode"].get<std::string>();
        trunk.connected_to = t["connected_to"].get<std::string>();
        trunks.push_back(trunk);
    }
    return trunks;
}

std::vector<VlanEntry> extract_vlan_db(const json& trunk_data) {
    std::vector<VlanEntry> entries;
    if (!trunk_data.contains("vlan_database")) return entries;
    for (const auto& v : trunk_data["vlan_database"]) {
        VlanEntry entry;
        entry.vlan_id = v["vlan_id"].get<int>();
        entry.name = v["name"].get<std::string>();
        entry.subnet = v["subnet"].get<std::string>();
        entry.security_zone = v["security_zone"].get<std::string>();
        entries.push_back(entry);
    }
    return entries;
}

std::vector<AclPolicy> extract_acl_policies(const json& routing_data) {
    std::vector<AclPolicy> policies;
    if (!routing_data.contains("acl_policies")) return policies;
    for (const auto& p : routing_data["acl_policies"]) {
        AclPolicy policy;
        policy.acl_id = p["acl_id"].get<std::string>();
        policy.applied_to = p["applied_to"].get<std::string>();
        policy.direction = p["direction"].get<std::string>();
        for (const auto& r : p["rules"]) {
            AclRule rule;
            rule.seq = r["seq"].get<int>();
            rule.action = r["action"].get<std::string>();
            rule.protocol = r["protocol"].get<std::string>();
            rule.src = r["src"].get<std::string>();
            rule.dst = r["dst"].get<std::string>();
            rule.dst_port = r["dst_port"].is_null() ? "" : r["dst_port"].get<std::string>();
            policy.rules.push_back(rule);
        }
        policies.push_back(policy);
    }
    return policies;
}

std::map<std::string, ZonePolicy> extract_zone_policies(const json& routing_data) {
    std::map<std::string, ZonePolicy> policies;
    if (!routing_data.contains("segmentation_policy") ||
        !routing_data["segmentation_policy"].contains("zones")) return policies;
    for (const auto& [zone_name, zone_data] : routing_data["segmentation_policy"]["zones"].items()) {
        ZonePolicy zp;
        for (const auto& d : zone_data["allowed_destinations"]) {
            zp.allowed_destinations.push_back(d.get<std::string>());
        }
        for (const auto& d : zone_data["blocked_destinations"]) {
            zp.blocked_destinations.push_back(d.get<std::string>());
        }
        policies[zone_name] = zp;
    }
    return policies;
}

json build_enforcement_result(const std::vector<Violation>& violations,
                              const std::vector<std::string>& trunk_issues,
                              bool native_mismatch, bool native_consistent,
                              const std::vector<VlanFlow>& flows,
                              const std::vector<TrunkPort>& trunks) {
    json result;
    result["analysis_metadata"] = {
        {"engine_version", "1.4.2"},
        {"analysis_timestamp", "2026-03-14T09:00:00Z"},
        {"total_flows_analyzed", static_cast<int>(flows.size())},
        {"total_trunk_ports", static_cast<int>(trunks.size())}
    };
    int critical_count = 0, high_count = 0, medium_count = 0, low_count = 0;
    for (const auto& v : violations) {
        if (v.severity == "critical") critical_count++;
        else if (v.severity == "high") high_count++;
        else if (v.severity == "medium") medium_count++;
        else low_count++;
    }
    result["summary"] = {
        {"total_violations", static_cast<int>(violations.size())},
        {"critical", critical_count},
        {"high", high_count},
        {"medium", medium_count},
        {"low", low_count},
        {"enforcement_status", critical_count > 0 ? "FAILED" : (high_count > 0 ? "WARNING" : "PASSED")}
    };
    json violation_array = json::array();
    for (const auto& v : violations) {
        violation_array.push_back({
            {"violation_id", v.violation_id},
            {"category", v.category},
            {"severity", v.severity},
            {"description", v.description},
            {"flow_id", v.flow_id},
            {"source_ip", v.src_ip},
            {"destination_ip", v.dst_ip},
            {"source_vlan", v.src_vlan},
            {"destination_vlan", v.dst_vlan},
            {"recommendation", v.recommendation}
        });
    }
    result["violations"] = violation_array;
    json trunk_findings = json::array();
    for (const auto& issue : trunk_issues) {
        trunk_findings.push_back({{"finding", issue}, {"severity", "high"}});
    }
    result["trunk_configuration_findings"] = trunk_findings;
    result["native_vlan_analysis"] = {
        {"mismatch_detected", native_mismatch},
        {"all_consistent", native_consistent},
        {"risk_level", native_mismatch ? "low" : "critical"}
    };
    std::map<std::string, int> category_counts;
    for (const auto& v : violations) {
        category_counts[v.category]++;
    }
    json breakdown = json::object();
    for (const auto& [cat, count] : category_counts) {
        breakdown[cat] = count;
    }
    result["violation_breakdown"] = breakdown;
    return result;
}

int main(int argc, char* argv[]) {
    std::string evidence_dir = "/app/evidence";
    std::string output_dir = "/app/output";
    if (argc > 1) evidence_dir = argv[1];
    if (argc > 2) output_dir = argv[2];
    fs::create_directories(output_dir);
    std::string traffic_path = evidence_dir + "/vlan_traffic.json";
    std::string trunk_path = evidence_dir + "/trunk_configs.json";
    std::string routing_path = evidence_dir + "/routing_policies.json";
    json traffic_data = parse_traffic_data(traffic_path);
    json trunk_data = parse_trunk_configs(trunk_path);
    json routing_data = parse_routing_policies(routing_path);
    if (traffic_data.empty() || trunk_data.empty() || routing_data.empty()) {
        std::cerr << "Failed to load evidence files" << std::endl;
        return 1;
    }
    std::vector<VlanFlow> flows = extract_flows(traffic_data);
    std::vector<TrunkPort> trunks = extract_trunks(trunk_data);
    std::vector<VlanEntry> vlan_db = extract_vlan_db(trunk_data);
    std::vector<AclPolicy> acl_policies = extract_acl_policies(routing_data);
    std::map<std::string, ZonePolicy> zone_policies = extract_zone_policies(routing_data);
    json seg_policy = routing_data["segmentation_policy"];
    json native_policy = seg_policy["native_vlan_policy"];
    json dtp_policy = seg_policy["dtp_policy"];
    std::vector<Violation> violations;
    int violation_counter = 0;
    for (const auto& flow : flows) {
        if (!is_cross_vlan_flow(flow)) continue;
        if (detect_double_tagging(flow)) {
            violation_counter++;
            Violation v;
            v.violation_id = "VIO-" + std::to_string(violation_counter);
            v.category = "double_tagging";
            v.severity = compute_severity("double_tagging", flow);
            v.description = "Double-tagged frame detected (Q-in-Q) from VLAN " +
                          std::to_string(flow.src_vlan) + " targeting VLAN " +
                          std::to_string(flow.dst_vlan) + " via outer tag " +
                          std::to_string(flow.outer_tag);
            v.flow_id = flow.flow_id;
            v.src_ip = flow.src_ip;
            v.dst_ip = flow.dst_ip;
            v.src_vlan = flow.src_vlan;
            v.dst_vlan = flow.dst_vlan;
            v.recommendation = generate_recommendation("double_tagging", flow);
            violations.push_back(v);
        }
        if (detect_native_vlan_exploit(flow, trunks, native_policy)) {
            violation_counter++;
            Violation v;
            v.violation_id = "VIO-" + std::to_string(violation_counter);
            v.category = "native_vlan_exploit";
            v.severity = compute_severity("native_vlan_exploit", flow);
            v.description = "Native VLAN exploitation attempt from " + flow.src_ip +
                          " using outer tag " + std::to_string(flow.outer_tag) +
                          " to reach VLAN " + std::to_string(flow.dst_vlan);
            v.flow_id = flow.flow_id;
            v.src_ip = flow.src_ip;
            v.dst_ip = flow.dst_ip;
            v.src_vlan = flow.src_vlan;
            v.dst_vlan = flow.dst_vlan;
            v.recommendation = generate_recommendation("native_vlan_exploit", flow);
            violations.push_back(v);
        }
        std::string src_zone = get_zone_for_vlan(flow.src_vlan, vlan_db);
        std::string dst_zone = get_zone_for_vlan(flow.dst_vlan, vlan_db);
        if (check_zone_violation(src_zone, dst_zone, zone_policies)) {
            violation_counter++;
            Violation v;
            v.violation_id = "VIO-" + std::to_string(violation_counter);
            v.category = "zone_violation";
            v.severity = compute_severity("zone_violation", flow);
            v.description = "Segmentation zone violation: " + src_zone + " -> " + dst_zone +
                          " (flow from " + flow.src_ip + " to " + flow.dst_ip + ")";
            v.flow_id = flow.flow_id;
            v.src_ip = flow.src_ip;
            v.dst_ip = flow.dst_ip;
            v.src_vlan = flow.src_vlan;
            v.dst_vlan = flow.dst_vlan;
            v.recommendation = generate_recommendation("zone_violation", flow);
            violations.push_back(v);
        }
        if (check_acl_violation(flow, acl_policies, vlan_db)) {
            violation_counter++;
            Violation v;
            v.violation_id = "VIO-" + std::to_string(violation_counter);
            v.category = "acl_bypass";
            v.severity = compute_severity("acl_bypass", flow);
            v.description = "ACL bypass detected: traffic from " + flow.src_ip +
                          " (VLAN " + std::to_string(flow.src_vlan) + ") to " +
                          flow.dst_ip + " (VLAN " + std::to_string(flow.dst_vlan) +
                          ") on port " + std::to_string(flow.dst_port);
            v.flow_id = flow.flow_id;
            v.src_ip = flow.src_ip;
            v.dst_ip = flow.dst_ip;
            v.src_vlan = flow.src_vlan;
            v.dst_vlan = flow.dst_vlan;
            v.recommendation = generate_recommendation("acl_bypass", flow);
            violations.push_back(v);
        }
    }
    std::vector<std::string> trunk_issues = check_trunk_misconfigs(trunks, native_policy, dtp_policy);
    auto [native_mismatch, native_consistent] = check_native_vlan_consistency(trunks);
    json result = build_enforcement_result(violations, trunk_issues, native_mismatch,
                                           native_consistent, flows, trunks);
    std::string output_path = output_dir + "/enforcement_result.json";
    std::ofstream outfile(output_path);
    if (!outfile.is_open()) {
        std::cerr << "Failed to write output: " << output_path << std::endl;
        return 1;
    }
    outfile << result.dump(2) << std::endl;
    outfile.close();
    std::cout << "VLAN Segmentation Enforcement Analysis Complete" << std::endl;
    std::cout << "Output: " << output_path << std::endl;
    std::cout << "Total violations: " << violations.size() << std::endl;
    std::cout << "Enforcement status: " << result["summary"]["enforcement_status"].get<std::string>() << std::endl;
    return 0;
}
