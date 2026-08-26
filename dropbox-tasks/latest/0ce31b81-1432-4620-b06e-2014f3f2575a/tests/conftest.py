import json
import os
import subprocess

import pytest

APP = "/app"
BINARY = os.path.join(APP, "build", "chess960_perft")


@pytest.fixture(scope="session")
def built_binary():
    result = subprocess.run(
        ["make"],
        cwd=APP,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, "make failed:\n" + result.stderr
    assert os.path.exists(BINARY), "binary missing after build"
    return BINARY


@pytest.fixture
def run_engine(built_binary, tmp_path):
    def _run(position_path, extra_env=None, timeout=None):
        output_path = str(tmp_path / "engine_output.json")
        env = dict(os.environ)
        env["POSITION_PATH"] = position_path
        env["OUTPUT_PATH"] = output_path
        if extra_env:
            env.update(extra_env)
        try:
            result = subprocess.run(
                [built_binary],
                cwd=APP,
                capture_output=True,
                text=True,
                env=env,
                timeout=timeout,
            )
        except subprocess.TimeoutExpired:
            raise AssertionError(
                "engine did not finish within %ss on %s" % (timeout, position_path)
            )
        assert result.returncode == 0, "engine run failed:\n" + result.stderr
        assert os.path.exists(output_path), (
            "engine did not produce output at " + output_path
        )
        with open(output_path) as handle:
            return json.load(handle)

    return _run
