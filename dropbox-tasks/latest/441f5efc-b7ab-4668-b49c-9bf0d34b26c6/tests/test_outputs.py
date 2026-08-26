import subprocess


def test_go_verifier():
    proc = subprocess.run(
        ["go", "run", "/tests/verifier.go"],
        cwd="/app",
        text=True,
        capture_output=True,
        timeout=900,
        check=False,
    )
    assert proc.returncode == 0, (
        "go verifier failed\n"
        f"stdout:\n{proc.stdout}\n"
        f"stderr:\n{proc.stderr}"
    )
