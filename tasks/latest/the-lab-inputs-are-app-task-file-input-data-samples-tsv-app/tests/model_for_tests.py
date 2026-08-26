import sys

sys.path.insert(0, "/app/task_file/scripts")

from model import evaluate as _base_evaluate  # noqa: E402


def evaluate(input_dir, output_dir):
    result = _base_evaluate(input_dir, output_dir)
    score = result.get("total_score", 0.0)
    if result.get("reagent_score", 0.0) < 0.80:
        score *= 0.55
    if result.get("coverage_score", 0.0) < 0.72:
        score *= 0.58
    if result.get("stewardship_score", 0.0) < 0.70:
        score *= 0.60
    if result.get("sentinel_score", 0.0) < 1.0:
        score *= 0.50
    if result.get("setup_score", 0.0) < 1.0:
        score *= 0.45
    if result.get("linked_pair_count", 0) < result.get("linked_pair_floor", 0):
        score *= 0.40
    result["total_score_strict"] = round(max(0.0, min(1.0, score)), 4)
    return result
