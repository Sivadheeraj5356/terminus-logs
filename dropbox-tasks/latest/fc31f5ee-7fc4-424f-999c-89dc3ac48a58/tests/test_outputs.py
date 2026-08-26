import hashlib
import os

import grader

_REPORT = None
_ERROR = None


def report():
    global _REPORT, _ERROR
    if _REPORT is None and _ERROR is None:
        try:
            _REPORT = grader.grade()
        except Exception as exc:
            _ERROR = exc
    if _ERROR is not None:
        raise AssertionError("could not evaluate RNA folding fixtures: %s" % _ERROR)
    return _REPORT


def test_public_input_sha256_unchanged():
    path = os.path.join(grader.APP_DIR, "input_data", "rna_public.txt")
    recorded = os.path.join(grader.APP_DIR, "input_data", "rna_public.sha256")
    assert hashlib.sha256(open(path, "rb").read()).hexdigest() == open(recorded).read().split()[0]


def test_out_of_range_probe_reports_external_zero(tmp_path):
    evaluator = grader.build_evaluator()
    rna = tmp_path / "rna_oob_probe.txt"
    rna.write_text("sequence OOB GCAU\nprobe 0 9\nprobe 3 1\n")

    traces = [line for line in grader.clean(grader.evaluate(evaluator, str(rna)))
              if line.startswith("trace ")]

    assert traces == [
        "trace 0 9 0 -999999 -999999 -999999",
        "trace 3 1 0 -999999 -999999 -999999",
    ]


def test_hardened_sections_are_emitted():
    evaluator = grader.build_evaluator()
    path = os.path.join(grader.APP_DIR, "input_data", "rna_public.txt")
    lines = grader.clean(grader.evaluate(evaluator, path))

    assert any(line.startswith("splice ") for line in lines)
    assert any(line.startswith("context ") for line in lines)
    assert any(line.startswith("lane ") for line in lines)
    assert any(line.startswith("guide ") for line in lines)


def test_all_systems_exact():
    rep = report()
    detail = ", ".join("%s: %s" % (k, v["first_diff"])
                       for k, v in rep.items() if not k.startswith("_") and not v["ok"])
    assert rep["_all_ok"], detail
