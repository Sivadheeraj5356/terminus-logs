import subprocess
from pathlib import Path


def _execute_independent_lattice_matrix() -> subprocess.CompletedProcess[str]:
    suite_dir = Path(__file__).resolve().parent
    return subprocess.run(
        ["go", "-C", str(suite_dir), "run", "."],
        text=True,
        capture_output=True,
        check=False,
    )


def test_rebuilt_lattice_obeys_quasistatic_hysteresis() -> None:
    """Rebuild the simulator, inspect public artifacts, and run generated RFIM studies."""
    app_dir = Path("/app/environment")
    smoke_dir = Path("/app/output")

    build = subprocess.run(
        ["go", "build", "/app/environment/cmd/fieldloop"],
        cwd=app_dir,
        text=True,
        capture_output=True,
        check=False,
    )
    smoke = subprocess.run(
        [
            "go",
            "run",
            "/app/environment/cmd/fieldloop",
            "--model",
            "/app/environment/fixtures/model.json",
            "--field",
            "/app/environment/fixtures/field.tsv",
            "--output-dir",
            str(smoke_dir),
        ],
        cwd=app_dir,
        text=True,
        capture_output=True,
        check=False,
    )
    assert (build.returncode, smoke.returncode) == (0, 0), (
        build.stdout + build.stderr + smoke.stdout + smoke.stderr
    )

    completed = _execute_independent_lattice_matrix()
    assert completed.returncode == 0, completed.stdout + completed.stderr
