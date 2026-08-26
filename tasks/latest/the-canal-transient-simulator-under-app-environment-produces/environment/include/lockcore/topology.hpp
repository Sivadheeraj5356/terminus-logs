#pragma once

#include "lockcore/json_io.hpp"
#include "lockcore/types.hpp"

#include <map>
#include <string>
#include <vector>

namespace lockcore {

void validate_topology(const Topology& topo);

const NodeSpec& find_node(const Topology& topo, const std::string& node_id);
const LinkSpec& find_link(const Topology& topo, const std::string& link_id);
bool has_node(const Topology& topo, const std::string& node_id);

std::vector<std::string> storage_node_ids_sorted(const Topology& topo);
std::vector<std::string> boundary_node_ids_sorted(const Topology& topo);
std::vector<std::string> link_ids_sorted(const Topology& topo);

bool is_valid_identifier(const std::string& id);

// Builds a topology JSON object with nodes/links/initial_inflows sorted by
// ID, suitable for hashing into the case digest.
JsonValue normalized_topology_to_json(const Topology& topo);

}  // namespace lockcore
