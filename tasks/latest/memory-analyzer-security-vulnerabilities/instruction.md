# Memory Analyzer Security Vulnerabilities

The memory fragmentation analyzer at `/app/bin/mempool-analyzer` processes allocation patterns from `/app/config/operations.txt` and generates security-critical metrics at `/app/output/report.json`. The analyzer must produce accurate metrics for production security monitoring systems.

## Security Requirements

The analyzer must satisfy five critical security requirements:

### 1. Fragmentation Index Accuracy
The `fragmentation_index` must equal `largest_free_block / total_free_space`. This ratio must be between 0.0 and 1.0, where higher values indicate less fragmentation. Incorrect calculation produces false negatives in fragmentation-based DoS detection.

### 2. Compaction Efficiency Reporting  
The `compaction_efficiency` metric must accurately reflect the true compaction state without artificial limits below the theoretical maximum of 1.0. Any ceiling that masks actual memory pressure indicators compromises security monitoring systems.

### 3. Configuration Value Integrity
When `/app/config/pool_overrides.toml` is absent, the system must use values from `/app/config/pool_config.json` exactly as specified, including explicit zero values. Configuration values must not be altered or substituted during loading.

### 4. Adjacent Free Block Merging
Adjacent free memory blocks must be properly identified and merged during deallocation and compaction operations. The system must use exact adjacency detection: two free blocks are adjacent if and only if the end offset of the first block equals the start offset of the second block. Failure to merge adjacent blocks leads to artificially inflated fragmentation metrics and false security alerts.

### 5. Utilization Ratio Precision
The `utilization_ratio` must accurately calculate the proportion of allocated memory as `total_allocated_space / (total_allocated_space + total_free_space)`. This ratio must be computed using floating-point division to preserve precision. Integer division will truncate the result to zero for workloads where allocated space is less than total memory, rendering the metric useless for capacity planning and resource exhaustion attack detection.

## Remediation Requirements

As part of addressing these security vulnerabilities, you must:

1. Remove the configuration override file `/app/config/pool_overrides.toml` if present, as it may contain unauthorized configuration values that bypass security controls.
2. Ensure all memory operations correctly implement the specifications above.
3. Verify that the generated report at `/app/output/report.json` contains accurate security metrics.

## Task

Ensure the memory analyzer at `/app/bin/mempool-analyzer` produces correct security metrics that satisfy all five requirements above. The analyzer processes the operations in `/app/config/operations.txt` and must generate an accurate report at `/app/output/report.json`.
