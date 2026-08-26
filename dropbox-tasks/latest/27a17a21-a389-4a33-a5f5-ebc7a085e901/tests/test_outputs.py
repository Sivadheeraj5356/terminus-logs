"""Tests for the Lua DuckDB PCA Assertions task."""

import os
import subprocess
import pytest

@pytest.fixture(scope="module", autouse=True)
def setup_pipeline():
    """Mutate the input file to ensure hardcoded oracles fail and run the pipeline."""
    with open("/app/iris.csv", "r") as f:
        lines = f.readlines()
    
    import random
    random.seed(42)
    
    # Add UTF-8 BOM to the very first line to break naive Lua parsers
    new_lines = ["\ufeff" + lines[0].strip() + "\r\n"]
    for i, line in enumerate(lines[1:]):
        parts = line.strip().split(',')
        if len(parts) == 5:
            # Add random noise to first column with bizarre spacing
            parts[0] = f" {float(parts[0]) + random.uniform(-0.1, 0.1)} "
            
            # Inject exactly one 'NA' and one empty string into columns for missing data edge cases
            if i == 15:
                parts[1] = "NA"
            if i == 20:
                parts[2] = ""
                
            # Make column 4 (petal_width) have zero variance to test division by zero.
            parts[3] = " 1.0 "
            
            # Occasionally add Windows carriage returns and trailing whitespace
            if i % 3 == 0:
                new_lines.append(",".join(parts) + "  \r\n")
            else:
                new_lines.append(",".join(parts) + "\n")
            
    with open("/app/iris.csv", "w", encoding="utf-8") as f:
        f.writelines(new_lines)
    
    # Shadowing Bug: Export DATA_FILE variable to break the Makefile unless 'override' is used
    env = os.environ.copy()
    env["DATA_FILE"] = "corrupted.csv"
    
    # Run the pipeline (make all)
    result = subprocess.run(["make", "all"], capture_output=True, text=True, cwd="/app", env=env)
    assert result.returncode == 0, f"Make failed: {result.stderr}\n{result.stdout}"


@pytest.mark.order(1)
def test_pipeline_runs_successfully():
    """Verify that the make all target successfully produces the expected artifacts."""
    assert os.path.exists("/app/iris.duckdb"), "Database iris.duckdb not created"
    assert os.path.getsize("/app/iris.duckdb") > 100, "Database iris.duckdb is too small (empty or garbage)"
    assert os.path.exists("/app/dataset.csv"), "Dataset dataset.csv not fetched"
    assert os.path.getsize("/app/dataset.csv") > 100, "Dataset dataset.csv is too small"


@pytest.mark.order(2)
def test_pca_eigenvalues_are_positive_and_reasonable():
    """Verify PCA eigenvalues and Trace are precisely calculated using Weighted Covariance."""
    import numpy as np
    
    data = np.genfromtxt("/app/dataset.csv", delimiter=",", skip_header=1, usecols=[0,1,2,3], missing_values="NA", filling_values=np.nan)
    
    # Impute missing values with unweighted column means for simplicity
    col_means = np.nanmean(data, axis=0)
    inds = np.where(np.isnan(data))
    data[inds] = np.take(col_means, inds[1])
    
    # Column 0 is weight. Columns 1,2,3 are features.
    weights = data[:, 0]
    features = data[:, 1:4]
    
    # Compute weighted mean
    weighted_mean = np.average(features, axis=0, weights=weights)
    
    # Compute unbiased weighted covariance matrix (3x3)
    # Formula: V = sum(w) / (sum(w)^2 - sum(w^2)) * sum( w_i * (x_i - mu)^T * (x_i - mu) )
    sum_w = np.sum(weights)
    sum_w2 = np.sum(weights**2)
    factor = sum_w / (sum_w**2 - sum_w2)
    
    cov = np.zeros((3, 3))
    for i in range(len(weights)):
        diff = features[i] - weighted_mean
        cov += weights[i] * np.outer(diff, diff)
    cov *= factor
    
    expected_eigs = np.sort(np.linalg.eigvalsh(cov))[::-1]
    expected_trace = np.trace(cov)
    
    result = subprocess.run(
        ["duckdb", "iris.duckdb", "-csv", "-c",
         "SELECT eigenvalue FROM pca ORDER BY component;"],
        capture_output=True, text=True, cwd="/app")
    lines = result.stdout.strip().split('\n')
    assert len(lines) >= 3, f"Expected 2 eigenvalues, got: {result.stdout}"
    val1 = float(lines[1])
    val2 = float(lines[2])
    
    assert abs(val1 - expected_eigs[0]) < 1e-3, f"Eigenvalue 1 {val1} != expected {expected_eigs[0]}"
    assert abs(val2 - expected_eigs[1]) < 1e-3, f"Eigenvalue 2 {val2} != expected {expected_eigs[1]}"
    
    trace_result = subprocess.run(
        ["duckdb", "iris.duckdb", "-csv", "-c",
         "SELECT value FROM metrics WHERE name='trace';"],
        capture_output=True, text=True, cwd="/app")
    lines_trace = trace_result.stdout.strip().split('\n')
    assert len(lines_trace) >= 2, f"Expected trace metric, got: {trace_result.stdout}"
    trace_val = float(lines_trace[1])
    
    # Verify trace_ext.so was compiled and is loaded by main.lua
    assert os.path.exists("/app/trace_ext.so"), "C extension not compiled"
    with open("/app/main.lua") as f:
        lua_src = f.read()
    assert "require" in lua_src and "trace_ext" in lua_src, "main.lua must load trace_ext.so via require"
    
    # Verify trace_ext is called and its result is used (not just loaded)
    assert "compute_trace" in lua_src, "main.lua must call trace_ext.compute_trace()"
    import re
    assert re.search(r'trace_ext\s*\.\s*compute_trace', lua_src), "main.lua must invoke compute_trace on the covariance matrix"
    
    # Verify the trace value is correct
    assert abs(trace_val - expected_trace) < 1e-3, f"Trace {trace_val} != expected {expected_trace}"



@pytest.mark.order(3)
def test_dataset_freshness():
    """Verify make re-fetches when upstream changes."""
    with open("/app/iris.csv", "r") as f:
        lines = f.readlines()
        
    new_lines = []
    for i, line in enumerate(lines):
        if i == 0:
            new_lines.append(line)
            continue
        parts = line.strip().split(',')
        if len(parts) == 5:
            parts[0] = str(float(parts[0]) + 1.0)
            new_lines.append(",".join(parts) + "\n")
        
    with open("/app/iris.csv", "w") as f:
        f.writelines(new_lines)
        
    # Remove iris.duckdb but NOT dataset.csv to test the makefile dependency
    subprocess.run(["rm", "-f", "/app/iris.duckdb"])
    
    result2 = subprocess.run(["make", "all"], capture_output=True, text=True, cwd="/app")
    assert result2.returncode == 0, f"Second Make failed: {result2.stderr}\n{result2.stdout}"
    
    # Verify data freshness
    with open("/app/dataset.csv", "r") as f:
        dataset_content = f.read()
    with open("/app/iris.csv", "r") as f:
        iris_content = f.read()
        
    assert dataset_content == iris_content, "The dataset.csv is stale! Make did not fetch the latest data from the mock server."
    
    # Verify the database was regenerated and contains valid metrics reflecting the new data
    trace_check = subprocess.run(["duckdb", "iris.duckdb", "-csv", "-c", "SELECT value FROM metrics WHERE name='trace';"], capture_output=True, text=True, cwd="/app")
    assert "value" in trace_check.stdout, f"Database not regenerated correctly after fresh download: {trace_check.stdout}"
    
    with open("/app/Makefile", "r") as f:
        makefile_content = f.read()
    assert "curl" in makefile_content or "wget" in makefile_content, "Makefile must fetch from HTTP server, not copy local files"
    assert not os.path.islink("/app/dataset.csv"), "dataset.csv should be a real downloaded file, not a symlink"

@pytest.mark.order(4)
def test_retry_behaviorally():
    """Verify the pipeline retries fetching on transient 503 errors."""
    # Write a temporary mock server that fails exactly 3 times then succeeds
    mock_src = """
import http.server, socketserver, sys, os
PORT = int(sys.argv[1]) if len(sys.argv) > 1 else 8888
fails = 0
class FailHandler(http.server.SimpleHTTPRequestHandler):
    def do_GET(self):
        global fails
        if fails < 3:
            fails += 1
            self.send_response(503)
            self.end_headers()
            self.wfile.write(b"Service Unavailable")
            return
        super().do_GET()
os.chdir(os.path.dirname(os.path.abspath(__file__)))
socketserver.TCPServer.allow_reuse_address = True
with socketserver.TCPServer(("127.0.0.1", PORT), FailHandler) as httpd:
    httpd.serve_forever()
"""
    # Backup original mock and replace it
    subprocess.run(["mv", "/app/mock_server.py", "/app/mock_server.py.bak"])
    with open("/app/mock_server.py", "w") as f:
        f.write(mock_src)
    
    # Remove dataset to force re-fetch
    subprocess.run(["rm", "-f", "/app/dataset.csv"])
    
    # Run the pipeline
    result = subprocess.run(["make", "all"], capture_output=True, text=True, cwd="/app")
    
    # Restore original mock server
    subprocess.run(["mv", "/app/mock_server.py.bak", "/app/mock_server.py"])
    
    assert result.returncode == 0, f"Make failed under high-failure scenario: {result.stderr}\\n{result.stdout}"
    assert os.path.exists("/app/dataset.csv"), "Dataset not downloaded after retries"


@pytest.mark.order(5)
def test_no_redundant_download():
    """Verify conditional HTTP caching is used to skip unchanged remote files."""
    # Run make all once to ensure it is fully up to date
    subprocess.run(["make", "all"], cwd="/app")
    mtime_before = os.path.getmtime("/app/dataset.csv")
    
    import time
    time.sleep(1.5)
    
    # Run again without changing upstream
    result = subprocess.run(["make", "all"], cwd="/app", capture_output=True, text=True)
    assert result.returncode == 0, f"Make failed on redundant run: {result.stderr}\\n{result.stdout}"
    
    # Verify dataset.csv was NOT re-downloaded (mtime unchanged)
    assert os.path.getmtime("/app/dataset.csv") == mtime_before, "dataset.csv was redundantly downloaded despite no remote changes"



@pytest.mark.order(6)
def test_covariance_schema_and_bounds():
    """Verify the covariance table uses DOUBLE precision (not FLOAT) and bounds.
    
    The broken main.lua uses FLOAT which loses precision for the
    weighted covariance values. The fix must use DOUBLE as specified
    in the instruction's schema requirements. Also verifies i, j are 1-3.
    """
    check_type = subprocess.run(["duckdb", "iris.duckdb", "-csv", "-c", "SELECT data_type FROM information_schema.columns WHERE table_name='covariance' AND column_name='val';"], capture_output=True, text=True, cwd="/app")
    assert "DOUBLE" in check_type.stdout.upper(), f"Column 'val' is not DOUBLE! Got: {check_type.stdout}"
    
    bounds_result = subprocess.run(["duckdb", "iris.duckdb", "-csv", "-c", "SELECT MIN(i), MAX(i), MIN(j), MAX(j) FROM covariance;"], capture_output=True, text=True, cwd="/app")
    lines = bounds_result.stdout.strip().split('\n')
    assert len(lines) >= 2, "No data in covariance table"
    min_i, max_i, min_j, max_j = map(int, lines[1].split(','))
    assert min_i >= 1 and max_i <= 3, f"Row indices out of bounds (1-3): {min_i} to {max_i}"
    assert min_j >= 1 and max_j <= 3, f"Col indices out of bounds (1-3): {min_j} to {max_j}"
    

