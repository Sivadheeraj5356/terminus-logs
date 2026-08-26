#pragma once

#include "lockcore/json_io.hpp"
#include "lockcore/types.hpp"

#include <cstdint>
#include <string>
#include <vector>

namespace lockcore {

bool is_valid_event_id(const std::string& id);

ForcingEvent forcing_event_from_json(const JsonValue& obj);
JsonValue forcing_event_to_json(const ForcingEvent& ev);

// Parses raw JSONL bytes into events preserving physical line order. Enforces
// nonempty lines, a trailing newline, and unique event IDs/source sequences.
std::vector<ForcingEvent> parse_forcing_jsonl(const std::string& text);

bool forcing_canonical_less(const ForcingEvent& a, const ForcingEvent& b);
std::vector<ForcingEvent> sort_events_canonical(std::vector<ForcingEvent> events);

}  // namespace lockcore
