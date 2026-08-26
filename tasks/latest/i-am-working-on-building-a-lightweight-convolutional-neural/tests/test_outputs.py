import subprocess
import os

def run_go_test(test_name: str):
    """Helper to run a specific Go test with the race detector enabled."""
    env = os.environ.copy()
    env["CGO_ENABLED"] = "1"
    
    cmd = ["go", "test", "-race", "-v", "-run", f"^{test_name}$", "./..."]
    res = subprocess.run(cmd, cwd="/app", capture_output=True, text=True, env=env)
    
    assert res.returncode == 0, (
        f"{test_name} failed or race detected (exit code: {res.returncode}).\n"
        f"STDOUT:\n{res.stdout}\n"
        f"STDERR:\n{res.stderr}"
    )
    assert "no tests to run" not in res.stdout, (
        f"{test_name} matched no Go tests — check spelling"
    )
    assert "PASS" in res.stdout, (
        f"{test_name} did not produce PASS output"
    )

def test_conv2d_gradient_check():
    """Verify numerical gradient check for DeformableConv2D layer."""
    run_go_test("TestDeformableConv2DGradientCheck")

def test_groupevonorm2d_gradient_check():
    """Verify numerical gradient check for GroupEvoNorm2D layer."""
    run_go_test("TestGroupEvoNorm2DGradientCheck")

def test_blurpool2d_gradient_check():
    """Verify numerical gradient check for BlurPool2D layer."""
    run_go_test("TestBlurPool2DGradientCheck")

def test_model_training_convergence():
    """Verify training convergence to loss < 0.1 on a synthetic dataset."""
    run_go_test("TestModelTrainingConvergence")

def test_conv2d_golden_outputs():
    """Verify golden outputs for normalization, polar coordinate warping and boundaries."""
    run_go_test("TestDeformableConv2DGoldenOutputs")

def test_gradient_accumulation_and_reset():
    """Verify direct gradient accumulation and parameter Update/reset behavior."""
    run_go_test("TestGradientAccumulationAndReset")
