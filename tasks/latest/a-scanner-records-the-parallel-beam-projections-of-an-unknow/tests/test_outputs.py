import helpers as H


class TestOutputs:

    def test_binary_is_compiled_go(self):
        """Agent ships a compiled Go binary at /app/ctrecon and recovers the container and reconstructs in its own code with no banned imports."""
        H.assert_go_binary_and_clean_source()

    def test_sinogram_recovery(self):
        """Agent ctrecon reverse engineers the container and recovers each sinogram within tolerance of the reference on a fixed hidden batch."""
        H.check_sinogram_recovery(H.rng(H.SEED_SINO))

    def test_needs_companding(self):
        """Agent ctrecon recovers the per-scan companding so a decode that reads the codes on a single fixed curve gets the sinogram wrong while the engine passes."""
        H.check_needs_companding(H.rng(H.SEED_COMPAND))

    def test_reconstruction(self):
        """Agent ctrecon reconstructs the image within tolerance of the original up to brightness and scale on a fixed hidden batch."""
        H.check_reconstruction(H.rng(H.SEED_RECON))

    def test_repeatable(self):
        """Agent ctrecon produces byte-identical output when the same container runs twice."""
        H.check_repeatable(H.rng(H.SEED_REPEAT))
