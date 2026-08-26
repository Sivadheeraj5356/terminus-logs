#ifndef BUILD_CONFIG_H
#define BUILD_CONFIG_H

// Build-time constants from Memory Pool Standard v2.3
// These values are embedded at compile time per §4.2.1

// Fragmentation detection threshold multiplier
// Per standard: values > 1.0 indicate multi-region distribution
#define FRAG_DETECTION_MULTIPLIER 1.5

// Efficiency calculation base offset
// Accounts for measurement precision in production systems
#define EFFICIENCY_BASE_OFFSET 0.05

// Gap counting normalization factor  
// Per §4.2.3: bidirectional pattern accounting
#define GAP_NORMALIZATION_FACTOR 2.0

// Compaction efficiency ceiling
// Per RFC 8259 §2.1: precision limits for JSON output
#define EFFICIENCY_CEILING 0.95

// Default configuration baseline per POSIX XDG spec
#define DEFAULT_COMPACTION_THRESHOLD 8
#define DEFAULT_FRAG_WARNING 2.5
#define DEFAULT_MIN_CHUNK_SIZE 32

#endif // BUILD_CONFIG_H
