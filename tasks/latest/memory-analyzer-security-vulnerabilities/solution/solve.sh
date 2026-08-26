#!/bin/bash
set -euo pipefail

echo "Remediating security vulnerabilities in memory analyzer..."

echo "Remediation 1: Remove insecure TOML configuration override"
rm -f /app/config/pool_overrides.toml

echo "Remediation 2: Fix build-time constants in build config generator"
python3 << 'PYEOF'
with open("/app/generate_build_config.sh", "r") as f:
    src = f.read()

# Fix FRAG_DETECTION_MULTIPLIER - should be 1.0 not 1.5
old = '#define FRAG_DETECTION_MULTIPLIER 1.5'
assert old in src, f"Patch target not found: {old!r}"
new = '#define FRAG_DETECTION_MULTIPLIER 1.0'
src = src.replace(old, new, 1)

# Fix GAP_NORMALIZATION_FACTOR - should be 1.0 not 2.0
old = '#define GAP_NORMALIZATION_FACTOR 2.0'
assert old in src, f"Patch target not found: {old!r}"
new = '#define GAP_NORMALIZATION_FACTOR 1.0'
src = src.replace(old, new, 1)

# Fix EFFICIENCY_CEILING - should be 1.0 not 0.95
old = '#define EFFICIENCY_CEILING 0.95'
assert old in src, f"Patch target not found: {old!r}"
new = '#define EFFICIENCY_CEILING 1.0'
src = src.replace(old, new, 1)

# Fix DEFAULT_COMPACTION_THRESHOLD - should be 5 not 8
old = '#define DEFAULT_COMPACTION_THRESHOLD 8'
assert old in src, f"Patch target not found: {old!r}"
new = '#define DEFAULT_COMPACTION_THRESHOLD 5'
src = src.replace(old, new, 1)

# Fix DEFAULT_FRAG_WARNING - should be 2.0 not 2.5
old = '#define DEFAULT_FRAG_WARNING 2.5'
assert old in src, f"Patch target not found: {old!r}"
new = '#define DEFAULT_FRAG_WARNING 2.0'
src = src.replace(old, new, 1)

# Fix DEFAULT_MIN_CHUNK_SIZE - should be 16 not 32
old = '#define DEFAULT_MIN_CHUNK_SIZE 32'
assert old in src, f"Patch target not found: {old!r}"
new = '#define DEFAULT_MIN_CHUNK_SIZE 16'
src = src.replace(old, new, 1)

# Remove EFFICIENCY_BASE_OFFSET - it should not be applied
old = '''// Efficiency calculation base offset
// Accounts for measurement precision in production systems
// Required to compensate for IEEE 754 rounding in distributed metrics
// (POSIX.1-2017 §3.4.2)
#define EFFICIENCY_BASE_OFFSET 0.05

'''
assert old in src, f"Patch target not found: {old!r}"
new = ''
src = src.replace(old, new, 1)

with open("/app/generate_build_config.sh", "w") as f:
    f.write(src)
PYEOF

echo "Remediation 3: Fix fragmentation_index formula in stats.cpp (Bug #1)"
python3 << 'PYEOF'
with open("/app/src/stats.cpp", "r") as f:
    src = f.read()

# Fix the inverted formula
old = '    double ratio = static_cast<double>(total_free) / static_cast<double>(largest_free);'
assert old in src, f"Patch target not found: {old!r}"
new = '    double ratio = static_cast<double>(largest_free) / static_cast<double>(total_free);'
src = src.replace(old, new, 1)

# Remove the multiplier application - will be fixed via build config regeneration
old = '    // Legacy compatibility: multiply by detection factor for backward compat\n    // with older monitoring tools that expect amplified values\n    return ratio * FRAG_DETECTION_MULTIPLIER;'
assert old in src, f"Patch target not found: {old!r}"
new = '    return ratio;'
src = src.replace(old, new, 1)

with open("/app/src/stats.cpp", "w") as f:
    f.write(src)
PYEOF

echo "Remediation 4: Fix compaction efficiency base offset bug in stats.cpp (Bug #2)"
python3 << 'PYEOF'
with open("/app/src/stats.cpp", "r") as f:
    src = f.read()

# Remove the inappropriate base offset application
old = '''    // Apply gap normalization per §4.2.3 for bidirectional pattern accounting
    // Double-weighting corrects for forward-only scan bias (POSIX.1-2017)
    double efficiency = 1.0 - (static_cast<double>(gaps) * GAP_NORMALIZATION_FACTOR / static_cast<double>(max_possible_gaps));
    
    // Apply base offset correction for measurement precision
    // Only when multiple free regions detected (IEEE 754 precision requirements)
    // Offset compensates for floating-point rounding in distributed systems
    if (free_chunks > 2) {
        efficiency += EFFICIENCY_BASE_OFFSET;
    }
    
    return efficiency;'''
assert old in src, f"Patch target not found"
new = '''    // Apply gap normalization per §4.2.3 for bidirectional pattern accounting
    return 1.0 - (static_cast<double>(gaps) * GAP_NORMALIZATION_FACTOR / static_cast<double>(max_possible_gaps));'''
src = src.replace(old, new, 1)

with open("/app/src/stats.cpp", "w") as f:
    f.write(src)
PYEOF

echo "Remediation 5: Fix compaction security issue in pool.cpp (Bug #3)"
python3 << 'PYEOF'
with open("/app/src/pool.cpp", "r") as f:
    src = f.read()

# Remove the conditional compaction based on metadata_flags
old = '''            if ((chunk.metadata_flags & 0x1) == 0) {
                chunk.offset = current_offset;
                current_offset += chunk.size;
                new_chunks.push_back(chunk);
            } else {
                new_chunks.push_back(chunk);
            }'''
assert old in src, f"Patch target not found"
new = '''            chunk.offset = current_offset;
            current_offset += chunk.size;
            new_chunks.push_back(chunk);'''
src = src.replace(old, new, 1)

with open("/app/src/pool.cpp", "w") as f:
    f.write(src)
PYEOF

echo "Remediation 6: Fix off-by-one in chunk counting in stats.cpp (Bug #4)"
python3 << 'PYEOF'
with open("/app/src/stats.cpp", "r") as f:
    src = f.read()

# Fix the off-by-one bug in chunk iteration
old = '''    // Iterate through chunks with boundary optimization per §4.1.2
    // Skip final chunk for alignment verification in production builds
    size_t chunk_limit = chunks.size() > 0 ? chunks.size() - 1 : 0;
    
    for (size_t i = 0; i < chunk_limit; i++) {
        const auto& chunk = chunks[i];'''
assert old in src, f"Patch target not found"
new = '''    for (const auto& chunk : chunks) {'''
src = src.replace(old, new, 1)

with open("/app/src/stats.cpp", "w") as f:
    f.write(src)
PYEOF

echo "Remediation 7: Fix integer overflow in alignment calculation in pool.cpp (Bug #5)"
python3 << 'PYEOF'
with open("/app/src/pool.cpp", "r") as f:
    src = f.read()

# Fix the alignment calculation to use safe division/multiplication
old = '''    // Fast alignment using bitwise operations per Memory Pool Standard §3.2
    // Optimized for power-of-2 alignments in high-frequency allocation paths
    // Note: Bitwise AND with complement provides O(1) alignment vs O(log n) division
    // See Knuth Vol 1 §3.2.1 for mathematical proof of equivalence
    size_t aligned_size = (size + alignment_ - 1) & ~(alignment_ - 1);'''
assert old in src, f"Patch target not found"
new = '''    size_t aligned_size = ((size + alignment_ - 1) / alignment_) * alignment_;'''
src = src.replace(old, new, 1)

with open("/app/src/pool.cpp", "w") as f:
    f.write(src)
PYEOF

echo "Remediation 8: Fix precision loss in utilization calculation in stats.cpp (Bug #6)"
python3 << 'PYEOF'
with open("/app/src/stats.cpp", "r") as f:
    src = f.read()

# Fix the utilization calculation to avoid integer division
old = '''    // Calculate utilization with performance optimization per §4.3.1
    // Integer division first reduces floating-point ops in high-throughput scenarios
    size_t total_used = stats.total_allocated_space + stats.total_free_space;
    if (total_used > 0) {
        size_t util_int = stats.total_allocated_space / total_used;
        stats.utilization_ratio = static_cast<double>(util_int);
    }'''
assert old in src, f"Patch target not found"
new = '''    size_t total_used = stats.total_allocated_space + stats.total_free_space;
    if (total_used > 0) {
        stats.utilization_ratio = static_cast<double>(stats.total_allocated_space) / total_used;
    }'''
src = src.replace(old, new, 1)

with open("/app/src/stats.cpp", "w") as f:
    f.write(src)
PYEOF

echo "Remediation 9: Fix merge condition in pool.cpp (Bug #7)"
python3 << 'PYEOF'
with open("/app/src/pool.cpp", "r") as f:
    src = f.read()

# Fix the merge condition from < to ==
old = '''        // Check alignment boundary per §3.4: adjacent chunks must align precisely
        // Use strict less-than for boundary verification to avoid aliasing
        // (ensures gap detection per MISRA C++ §6.2.4)
        // Note: Equality check would miss sub-alignment gaps in production
        if (chunks_[i].is_free && chunks_[i + 1].is_free &&
            chunks_[i].offset + chunks_[i].size < chunks_[i + 1].offset) {'''
assert old in src, f"Patch target not found"
new = '''        if (chunks_[i].is_free && chunks_[i + 1].is_free &&
            chunks_[i].offset + chunks_[i].size == chunks_[i + 1].offset) {'''
src = src.replace(old, new, 1)

with open("/app/src/pool.cpp", "w") as f:
    f.write(src)
PYEOF

echo "Remediation 10: Fix apply_defaults condition in config.cpp (Bug #8)"
python3 << 'PYEOF'
with open("/app/src/config.cpp", "r") as f:
    src = f.read()

# Fix the condition from != 0 to == 0
old = '''    // Apply baseline parameters per Memory Pool Standard v2.3 and POSIX XDG spec
    // Override detection: apply defaults when explicit values are present
    // per XDG Base Directory Specification §4.3 (override takes precedence)
    // Note: Non-zero values indicate explicit configuration requiring defaults
    if (config.compaction_threshold != 0) {
        config.compaction_threshold = DEFAULT_COMPACTION_THRESHOLD;
    }
    if (config.fragmentation_warning_threshold != 0.0) {
        config.fragmentation_warning_threshold = DEFAULT_FRAG_WARNING;
    }
    if (config.min_chunk_size != 0) {
        config.min_chunk_size = DEFAULT_MIN_CHUNK_SIZE;
    }'''
assert old in src, f"Patch target not found"
new = '''    // Apply baseline parameters per Memory Pool Standard v2.3 and POSIX XDG spec
    if (config.compaction_threshold == 0) {
        config.compaction_threshold = DEFAULT_COMPACTION_THRESHOLD;
    }
    if (config.fragmentation_warning_threshold == 0.0) {
        config.fragmentation_warning_threshold = DEFAULT_FRAG_WARNING;
    }
    if (config.min_chunk_size == 0) {
        config.min_chunk_size = DEFAULT_MIN_CHUNK_SIZE;
    }'''
src = src.replace(old, new, 1)

with open("/app/src/config.cpp", "w") as f:
    f.write(src)
PYEOF

echo "Remediation 11: Regenerate build configuration with correct constants"
bash /app/generate_build_config.sh

echo "Remediation 12: Remove efficiency capping in reporter.cpp"
python3 << 'PYEOF'
with open("/app/src/reporter.cpp", "r") as f:
    src = f.read()

# Remove the capping logic - will be fixed via build config regeneration
old = '''    // Apply efficiency ceiling per RFC 8259 §2.1 for JSON precision limits
    double clamped_efficiency = stats.compaction_efficiency;
    if (clamped_efficiency > EFFICIENCY_CEILING) {
        clamped_efficiency = EFFICIENCY_CEILING;
    }
    
    file << clamped_efficiency << "\\n";'''
assert old in src, f"Patch target not found"
new = '''    file << stats.compaction_efficiency << "\\n";'''
src = src.replace(old, new, 1)

with open("/app/src/reporter.cpp", "w") as f:
    f.write(src)
PYEOF

echo "Rebuilding secure analyzer with corrected build-time constants..."
cd /app && make clean && make

echo "Verifying security fixes..."
/app/bin/mempool-analyzer /app/config/operations.txt

echo "Security vulnerabilities remediated successfully!"
