"""Visible verifier helpers for the RNPX RNA folding task.

These helpers evaluate bundled RNA folding fixtures and compare normalized
output digests plus a few RNPX record-format edge cases.
"""

import hashlib
import os
import pwd
import shutil
import stat
import subprocess
import tempfile

APP_DIR = os.environ.get("APP_DIR", "/app")
HERE = os.path.dirname(os.path.abspath(__file__))

EXPECTED_HASHES = {
    "public": "e85715d2a98930d3814a2d88ac4af30ed290579ec61b7845955cce3d3b4d4735",
    "holdout_1": "e2bcc750046cc3d0d199aaac78ad0ba443445307dc21bde3d182cca65371444b",
    "holdout_2": "826a8015d29be2d0e628fb57644351b54f8a8dcb3495fc5a7e01b9bfadc3d8d7",
    "holdout_3": "cfe2d2a87525f553758af8920aad062716f472cd6350bce410fbdbbe6b2f737b",
    "holdout_4": "56f1495f54373e4ca27c61433c8b7da54b8da0cf02b2dd4fdc90133ef630c411",
    "holdout_5": "d67a748683024af1f016416ac2ae3e42189e34f17719d45e9982bc7879101f8c",
}


def build_evaluator(src_path=None):
    if src_path is None:
        src_path = os.path.join(APP_DIR, "src", "fold.cpp")
    if not os.path.exists(src_path):
        raise RuntimeError("expected %s" % src_path)
    build_dir = tempfile.mkdtemp(prefix="rnpx_eval_")
    evaluator = os.path.join(build_dir, "fold_eval")
    proc = subprocess.run(
        ["g++", "-std=c++17", "-O2", "-Wall", "-Wextra", "-Werror", "-pedantic",
         "-o", evaluator, src_path],
        capture_output=True, text=True, timeout=120,
    )
    if proc.returncode != 0:
        raise RuntimeError("fold evaluator did not build:\n%s" % proc.stderr[-2000:])
    return evaluator


def clean(text):
    return [line.strip() for line in text.splitlines()
            if line.strip() and not line.lstrip().startswith("#")]


def digest(text):
    normalized = "\n".join(clean(text)) + "\n"
    return hashlib.sha256(normalized.encode()).hexdigest()


def evaluate(evaluator, rna):
    sandbox = tempfile.mkdtemp(prefix="rnpx_case_")
    old_tests_mode = None
    try:
        local_evaluator = os.path.join(sandbox, "fold_eval")
        local_rna = os.path.join(sandbox, "rna.txt")
        shutil.copyfile(evaluator, local_evaluator)
        shutil.copyfile(rna, local_rna)
        os.chmod(local_evaluator, 0o755)
        os.chmod(local_rna, 0o644)
        os.chmod(sandbox, 0o755)

        preexec = None
        if hasattr(os, "geteuid") and os.geteuid() == 0:
            nobody = pwd.getpwnam("nobody")
            os.chown(sandbox, nobody.pw_uid, nobody.pw_gid)
            os.chown(local_evaluator, nobody.pw_uid, nobody.pw_gid)
            os.chown(local_rna, nobody.pw_uid, nobody.pw_gid)
            old_tests_mode = stat.S_IMODE(os.stat(HERE).st_mode)
            os.chmod(HERE, 0o700)

            def demote():
                os.setgid(nobody.pw_gid)
                os.setuid(nobody.pw_uid)

            preexec = demote

        proc = subprocess.run([local_evaluator, "rna.txt"], cwd=sandbox, capture_output=True,
                              text=True, timeout=15, preexec_fn=preexec)
        if proc.returncode != 0:
            raise RuntimeError("fold evaluator exited %d on %s\n%s" %
                               (proc.returncode, os.path.basename(rna), proc.stderr[-2000:]))
        if proc.stderr.strip():
            raise RuntimeError("fold evaluator wrote to stderr on %s\n%s" %
                               (os.path.basename(rna), proc.stderr[-2000:]))
        return proc.stdout
    finally:
        if old_tests_mode is not None:
            os.chmod(HERE, old_tests_mode)
        shutil.rmtree(sandbox, ignore_errors=True)


def systems():
    return [
        ("public", os.path.join(APP_DIR, "input_data", "rna_public.txt")),
        ("holdout_1", os.path.join(HERE, "holdout", "rna_h1.txt")),
        ("holdout_2", os.path.join(HERE, "holdout", "rna_h2.txt")),
        ("holdout_3", os.path.join(HERE, "holdout", "rna_h3.txt")),
        ("holdout_4", os.path.join(HERE, "holdout", "rna_h4.txt")),
        ("holdout_5", os.path.join(HERE, "holdout", "rna_h5.txt")),
    ]


def grade(src_path=None):
    evaluator = build_evaluator(src_path)
    report = {}
    for label, rna in systems():
        got_hash = digest(evaluate(evaluator, rna))
        expected_hash = EXPECTED_HASHES[label]
        ok = got_hash == expected_hash
        diff = None if ok else "sha256 got %s expected %s" % (got_hash, expected_hash)
        report[label] = {"ok": ok, "first_diff": diff}
    report["_all_ok"] = all(v["ok"] for v in report.values())
    return report
