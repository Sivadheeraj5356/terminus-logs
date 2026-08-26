"""Milestone 1 tests for the local WASI Preview 2 component build."""

import json
from pathlib import Path
import secrets
import subprocess


APP = Path("/app")
BUILD_SCRIPT = APP / "tools/build-component.sh"
GENERATED_RS = APP / "crates/edge-worker/src/generated.rs"
METADATA_JSON = APP / "target/component-build.json"
WASM_PATH = APP / "target/wasm32-wasip2/release/edge_worker.wasm"
WIT_PATH = APP / "wit/worker.wit"
MAIN_RS = APP / "crates/edge-worker/src/main.rs"


def run_component_build(timeout: int = 180) -> subprocess.CompletedProcess[str]:
    """Run the local component build script from the application root."""
    return subprocess.run(
        [str(BUILD_SCRIPT)],
        cwd=APP,
        text=True,
        capture_output=True,
        timeout=timeout,
    )


class TestMilestone1:
    """Verify the component build and generated WIT metadata."""

    def test_build_script_rejects_wit_without_stream_import(self) -> None:
        """The build should really validate the local WIT stream interface before writing outputs."""
        original = WIT_PATH.read_text()
        try:
            WIT_PATH.write_text(original.replace("wasi:io/streams", "wasi:io/notstreams"))
            result = run_component_build()
            assert result.returncode != 0, (
                "build unexpectedly passed with the stream import removed"
            )
        finally:
            WIT_PATH.write_text(original)

    def test_component_build_script_regenerates_bindings(self) -> None:
        """The offline component build should regenerate poisoned bindings and then compile."""
        GENERATED_RS.parent.mkdir(parents=True, exist_ok=True)
        GENERATED_RS.write_text("compile_error!(\"generated bindings were not refreshed\");\n")
        METADATA_JSON.unlink(missing_ok=True)
        WASM_PATH.unlink(missing_ok=True)

        result = run_component_build()
        assert result.returncode == 0, result.stderr + result.stdout
        generated = GENERATED_RS.read_text()
        assert 'BINDING_TOOL: &str = "wit-bindgen-lite"' in generated
        assert 'STREAM_INTERFACE: &str = "wasi:io/streams"' in generated

    def test_component_artifact_reflects_rust_source_compile(self) -> None:
        """The wasm artifact should be rebuilt from Rust source, not faked by the helper."""
        original = MAIN_RS.read_text()
        marker = f"verifier-rust-source-probe-{secrets.token_hex(8)}"
        try:
            MAIN_RS.write_text(
                original.replace(
                    "fn main() -> io::Result<()> {\n",
                    f"fn main() -> io::Result<()> {{\n    eprintln!(\"{marker}\");\n",
                )
            )
            WASM_PATH.unlink(missing_ok=True)

            result = run_component_build()
            assert result.returncode == 0, result.stderr + result.stdout
            data = WASM_PATH.read_bytes()
            assert marker.encode() in data
        finally:
            MAIN_RS.write_text(original)

    def test_component_artifact_is_wasm_at_preview2_path(self) -> None:
        """The build should leave a real compiled WASI artifact at the wasm32-wasip2 path."""
        if not WASM_PATH.exists():
            result = run_component_build()
            assert result.returncode == 0, result.stderr + result.stdout
        data = WASM_PATH.read_bytes()
        assert data.startswith(b"\0asm")
        assert len(data) > 50_000
        assert b"telemetry-edge-worker-preview2-component" not in data
        assert b"wasi:io/streams" in data

    def test_build_metadata_names_wit_bindgen_and_streams(self) -> None:
        """The build metadata should identify the local WIT binding flow and stream interface."""
        if not METADATA_JSON.exists():
            result = run_component_build()
            assert result.returncode == 0, result.stderr + result.stdout
        metadata = json.loads(METADATA_JSON.read_text())
        assert metadata["binding_tool"] == "wit-bindgen-lite"
        assert metadata["interface"] == "wasi:io/streams"
        assert metadata["world"] == "edge-worker"
