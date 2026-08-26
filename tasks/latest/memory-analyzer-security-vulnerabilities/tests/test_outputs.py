"""Test suite for memory analyzer security vulnerabilities."""
import json
import os
import pytest


EXPECTED_LARGEST_FREE_BLOCK = 1000624
EXPECTED_TOTAL_FREE_SPACE = 1000624
EXPECTED_TOTAL_ALLOCATED_SPACE = 47952
EXPECTED_FREE_CHUNKS = 1
EXPECTED_ALLOCATED_CHUNKS = 13
EXPECTED_TOTAL_CHUNKS = 14
EXPECTED_FRAGMENTATION_INDEX = 1.0
EXPECTED_UTILIZATION_RATIO = 0.0457458496
EXPECTED_COMPACTION_EFFICIENCY = 1.0


def get_report():
    """Load security metrics report."""
    with open("/app/output/report.json") as f:
        return json.load(f)


@pytest.mark.score(0.0)
def test_binary_exists():
    """Verify analyzer binary exists."""
    assert os.path.exists("/app/bin/mempool-analyzer")


@pytest.mark.score(0.0)
def test_report_generated():
    """Verify security metrics report generated."""
    assert os.path.exists("/app/output/report.json")


@pytest.mark.score(0.20)
def test_fragmentation_index_formula():
    """
    Verify fragmentation_index security vulnerability remediated.
    
    Security requirement: largest_free_block / total_free_space
    Prevents false negatives in DoS detection.
    """
    report = get_report()
    
    largest_free = report["largest_free_block"]
    total_free = report["total_free_space"]
    frag_index = report["fragmentation_index"]
    
    # Assert exact expected values from operations simulation
    assert largest_free == EXPECTED_LARGEST_FREE_BLOCK, \
        f"Largest free block must be {EXPECTED_LARGEST_FREE_BLOCK}, got {largest_free}"
    assert total_free == EXPECTED_TOTAL_FREE_SPACE, \
        f"Total free space must be {EXPECTED_TOTAL_FREE_SPACE}, got {total_free}"
    
    # Verify fragmentation index formula is correct
    if total_free > 0:
        expected_index = largest_free / total_free
        assert abs(frag_index - expected_index) < 0.0001, \
            f"Security metric must be {expected_index:.4f}, got {frag_index:.4f}"
    
    # Verify against known expected fragmentation index
    assert abs(frag_index - EXPECTED_FRAGMENTATION_INDEX) < 0.0001, \
        f"Fragmentation index must be {EXPECTED_FRAGMENTATION_INDEX}, got {frag_index}"
    
    assert 0.0 <= frag_index <= 1.0, \
        "Security metric must be in valid range [0.0, 1.0]"


@pytest.mark.score(0.15)
def test_fragmentation_index_component_values():
    """
    Verify fragmentation index components match expected values from operations.
    
    Independent verification that largest_free_block and total_free_space
    are computed correctly, not just that the ratio is self-consistent.
    """
    report = get_report()
    
    largest_free = report["largest_free_block"]
    total_free = report["total_free_space"]
    total_allocated = report["total_allocated_space"]
    
    # Assert exact expected values from simulation
    assert largest_free == EXPECTED_LARGEST_FREE_BLOCK, \
        f"Largest free block must be {EXPECTED_LARGEST_FREE_BLOCK}, got {largest_free}"
    assert total_free == EXPECTED_TOTAL_FREE_SPACE, \
        f"Total free space must be {EXPECTED_TOTAL_FREE_SPACE}, got {total_free}"
    assert total_allocated == EXPECTED_TOTAL_ALLOCATED_SPACE, \
        f"Total allocated space must be {EXPECTED_TOTAL_ALLOCATED_SPACE}, got {total_allocated}"
    
    # Verify total free space is non-zero and reasonable
    assert total_free > 0, "Total free space must be positive after operations"
    assert total_free < report["pool_size"], "Total free cannot exceed pool size"
    
    # Verify largest free block is within total free space
    assert largest_free <= total_free, \
        f"Largest free block ({largest_free}) cannot exceed total free ({total_free})"


@pytest.mark.score(0.20)
def test_compaction_efficiency_not_clamped():
    """
    Verify compaction_efficiency security vulnerability remediated.
    
    Artificial capping could mask memory pressure indicators.
    Verifies efficiency matches expected value and is not artificially clamped.
    """
    report = get_report()
    
    efficiency = report["compaction_efficiency"]
    free_chunks = report["free_chunks_count"]
    
    assert efficiency >= 0.0 and efficiency <= 1.0, \
        "Security metric must be in valid range [0.0, 1.0]"
    
    # Assert exact expected efficiency from simulation
    assert abs(efficiency - EXPECTED_COMPACTION_EFFICIENCY) < 0.0001, \
        f"Compaction efficiency must be {EXPECTED_COMPACTION_EFFICIENCY}, got {efficiency:.4f}"
    
    # Verify consistency with chunk count
    if free_chunks <= 1:
        # Perfect compaction: all free space in one chunk
        assert abs(efficiency - 1.0) < 0.0001, \
            f"With {free_chunks} free chunks, must report 1.0 for accurate security monitoring, got {efficiency:.4f}"
    
    # Critical: Verify efficiency is NOT artificially clamped
    # The bug might clamp at various values (0.95, 0.96, etc.)
    # With perfect compaction (efficiency = 1.0), any value < 1.0 indicates clamping
    assert efficiency >= 0.999, \
        f"Efficiency={efficiency:.4f} appears clamped - must be able to reach 1.0 for perfect compaction"


@pytest.mark.score(0.05)
def test_compaction_efficiency_range_validation():
    """
    Verify compaction efficiency can represent high-quality compaction states.
    
    Values should not be artificially limited below 1.0 when actual
    compaction quality warrants reporting near-perfect efficiency.
    """
    report = get_report()
    
    efficiency = report["compaction_efficiency"]
    free_chunks = report["free_chunks_count"]
    allocated_chunks = report["allocated_chunks_count"]
    
    # Verify expected chunk counts
    assert free_chunks == EXPECTED_FREE_CHUNKS, \
        f"Free chunks must be {EXPECTED_FREE_CHUNKS}, got {free_chunks}"
    assert allocated_chunks == EXPECTED_ALLOCATED_CHUNKS, \
        f"Allocated chunks must be {EXPECTED_ALLOCATED_CHUNKS}, got {allocated_chunks}"
    
    # With perfect compaction (1 free chunk), efficiency should be 1.0
    # Check it's not artificially clamped below 1.0
    if allocated_chunks > 5 and free_chunks <= 1:
        assert efficiency > 0.99, \
            f"With perfect compaction ({allocated_chunks} allocated, {free_chunks} free), " \
            f"efficiency {efficiency:.4f} appears artificially limited"


@pytest.mark.score(0.20)
def test_config_fallback_vulnerability():
    """
    Verify configuration loading vulnerability remediated.
    
    When pool_overrides.toml is removed, the system must use the
    JSON config values directly without applying hardcoded defaults.
    This prevents unauthorized configuration tampering via file removal.
    """
    # After the solution is applied, TOML should be removed
    # and the system should use JSON values directly
    toml_path = "/app/config/pool_overrides.toml"
    
    # Verify TOML was removed (part of vulnerability fix)
    assert not os.path.exists(toml_path), \
        "TOML override should be removed as part of security fix"
    
    # Get the current report (generated with JSON-only config)
    report = get_report()
    
    # Verify that pool_size and alignment match JSON exactly
    # JSON specifies pool_size=1048576, alignment=16
    assert report["pool_size"] == 1048576, \
        "Pool size must match JSON config"
    assert report["alignment"] == 16, \
        "Alignment must match JSON config"
    
    # Verify the system produced correct metrics with JSON-only config
    # If Bug #8 was not fixed, apply_defaults would incorrectly apply
    # defaults (8, 2.5, 32) even though JSON has explicit zeros
    
    # With correct implementation, we should see the expected ground-truth values
    assert report["fragmentation_index"] == EXPECTED_FRAGMENTATION_INDEX, \
        f"Fragmentation index must be {EXPECTED_FRAGMENTATION_INDEX} with correct config fallback"
    assert report["total_chunks"] == EXPECTED_TOTAL_CHUNKS, \
        f"Total chunks must be {EXPECTED_TOTAL_CHUNKS} with correct config fallback"
    
    # Successful generation of report with correct values proves
    # that JSON's explicit zero values were respected


@pytest.mark.score(0.05)
def test_utilization_ratio():
    """Verify utilization ratio for security monitoring."""
    report = get_report()
    
    allocated = report["total_allocated_space"]
    free_space = report["total_free_space"]
    utilization = report["utilization_ratio"]
    
    # Assert exact expected values
    assert allocated == EXPECTED_TOTAL_ALLOCATED_SPACE, \
        f"Total allocated must be {EXPECTED_TOTAL_ALLOCATED_SPACE}, got {allocated}"
    assert free_space == EXPECTED_TOTAL_FREE_SPACE, \
        f"Total free must be {EXPECTED_TOTAL_FREE_SPACE}, got {free_space}"
    
    total = allocated + free_space
    if total > 0:
        expected_util = allocated / total
        assert abs(utilization - expected_util) < 0.0001, \
            f"Utilization must be {expected_util:.10f}, got {utilization:.10f}"
    
    # Verify against expected utilization ratio
    assert abs(utilization - EXPECTED_UTILIZATION_RATIO) < 0.0001, \
        f"Utilization must be {EXPECTED_UTILIZATION_RATIO:.10f}, got {utilization:.10f}"


@pytest.mark.score(0.05)
def test_chunk_counts():
    """Verify chunk accounting for security analysis."""
    report = get_report()
    
    free_count = report["free_chunks_count"]
    allocated_count = report["allocated_chunks_count"]
    total_chunks = report["total_chunks"]
    
    # Assert exact expected values
    assert free_count == EXPECTED_FREE_CHUNKS, \
        f"Free chunks must be {EXPECTED_FREE_CHUNKS}, got {free_count}"
    assert allocated_count == EXPECTED_ALLOCATED_CHUNKS, \
        f"Allocated chunks must be {EXPECTED_ALLOCATED_CHUNKS}, got {allocated_count}"
    assert total_chunks == EXPECTED_TOTAL_CHUNKS, \
        f"Total chunks must be {EXPECTED_TOTAL_CHUNKS}, got {total_chunks}"
    
    # Verify arithmetic consistency
    assert free_count + allocated_count == total_chunks, \
        f"Chunk count mismatch: {free_count} + {allocated_count} != {total_chunks}"


@pytest.mark.score(0.0)
def test_space_accounting():
    """Verify memory accounting for security monitoring."""
    report = get_report()
    
    pool_size = report["pool_size"]
    total_free = report["total_free_space"]
    total_allocated = report["total_allocated_space"]
    
    assert total_free + total_allocated <= pool_size


@pytest.mark.score(0.0)
def test_fragmentation_index_range():
    """Verify security metric is in valid range."""
    report = get_report()
    
    frag_index = report["fragmentation_index"]
    
    assert frag_index >= 0.0
    assert frag_index <= 1.0, "Security metric must not exceed 1.0"


@pytest.mark.score(0.05)
def test_allocation_alignment_safety():
    """
    Verify alignment calculation safety for large allocations.
    
    Tests Bug #5: Integer overflow in alignment calculation.
    Bitwise operations can produce incorrect results with overflow.
    """
    report = get_report()
    
    # After operations with various allocation sizes, verify all allocated
    # space is properly aligned and doesn't show signs of overflow
    allocated_space = report["total_allocated_space"]
    
    # With correct implementation, allocated space should match expected value
    assert allocated_space == EXPECTED_TOTAL_ALLOCATED_SPACE, \
        f"Allocated space mismatch suggests alignment overflow: " \
        f"expected {EXPECTED_TOTAL_ALLOCATED_SPACE}, got {allocated_space}"
    
    # Verify total chunks count is correct (overflow would cause incorrect chunk tracking)
    total_chunks = report["total_chunks"]
    assert total_chunks == EXPECTED_TOTAL_CHUNKS, \
        f"Chunk count mismatch suggests allocation error: " \
        f"expected {EXPECTED_TOTAL_CHUNKS}, got {total_chunks}"


@pytest.mark.score(0.05)
def test_free_space_merge_behavior():
    """
    Verify adjacent free chunks are properly merged.
    
    Tests Bug #7: Incorrect merge condition prevents adjacent free chunks
    from being merged, leading to incorrect fragmentation reporting.
    """
    report = get_report()
    
    # After multiple FREE operations followed by COMPACT,
    # free chunks should be properly merged
    free_chunks = report["free_chunks_count"]
    
    # Expected: only 1 free chunk after compaction (all free space merged)
    assert free_chunks == EXPECTED_FREE_CHUNKS, \
        f"Free chunks not properly merged: expected {EXPECTED_FREE_CHUNKS}, got {free_chunks}"
    
    # With proper merging, largest free block equals total free space
    largest_free = report["largest_free_block"]
    total_free = report["total_free_space"]
    
    assert largest_free == total_free, \
        f"Merge failure: largest_free={largest_free} != total_free={total_free}"
