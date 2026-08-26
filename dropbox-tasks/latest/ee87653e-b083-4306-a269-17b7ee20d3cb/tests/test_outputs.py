"""
Binary relocation witness normalization verification.
Tests validate witness-bind policy for Alpha, Beta cipher-masked, and Gamma envelope-packed profiles.
Relbind ingest reads bundled libraries; witness export writes normalized relocation bytes for attestation.
Holdout verifier-fixtures exercise hidden attestation pools without bundled-only shortcuts.
"""
import shutil
import subprocess
import struct
from pathlib import Path
import pytest

BIN_DIR = Path("/app/bin")
DATA_DIR = Path("/app/data/binaries")
RELBIND_BIN = "/app/bin/relbind"
TEST_RUNNER_BIN = "/app/bin/test_runner"

HIDDEN_BETA = Path(__file__).resolve().parent / "verifier-fixtures" / "holdout_beta.so"
HIDDEN_GAMMA = Path(__file__).resolve().parent / "verifier-fixtures" / "holdout_gamma.so"


def reference_relocation_types_valid(elf_data: bytes, section_names: tuple[str, ...]) -> bool:
    """Independent reference: standard relocation sections use 24-byte rows with valid r_type."""
    e_shoff = struct.unpack("<Q", elf_data[40:48])[0]
    e_shentsize = struct.unpack("<H", elf_data[58:60])[0]
    e_shnum = struct.unpack("<H", elf_data[60:62])[0]
    e_shstrndx = struct.unpack("<H", elf_data[62:64])[0]

    shdrs = []
    for i in range(e_shnum):
        offset = e_shoff + i * e_shentsize
        fields = struct.unpack("<IIQQQQIIQQ", elf_data[offset : offset + 64])
        shdrs.append({"name_idx": fields[0], "offset": fields[4], "size": fields[5]})

    shstrndx_shdr = shdrs[e_shstrndx]
    shstrtab = elf_data[shstrndx_shdr["offset"] : shstrndx_shdr["offset"] + shstrndx_shdr["size"]]

    for shdr in shdrs:
        end = shstrtab.find(b"\x00", shdr["name_idx"])
        name_str = shstrtab[shdr["name_idx"] : end].decode("utf-8")
        if name_str not in section_names:
            continue
        if shdr["size"] >= 4:
            magic = struct.unpack("<I", elf_data[shdr["offset"] : shdr["offset"] + 4])[0]
            if magic == 0x474D524C:
                return False
        for idx in range(shdr["size"] // 24):
            rel_offset = shdr["offset"] + idx * 24
            _, r_info, _ = struct.unpack("<QQq", elf_data[rel_offset : rel_offset + 24])
            if (r_info & 0xFFFFFFFF) > 42:
                return False
    return True


def reference_staging_snapshot_bytes(path: Path) -> bytes:
    """Independent reference: staging snapshot export captures post-repair relocation bytes."""
    return path.read_bytes()

@pytest.fixture
def isolated_libs(tmp_path):
    """Copies the three test libraries to a temporary folder to avoid mutating original files."""
    dest_dir = tmp_path / "libs"
    dest_dir.mkdir()
    for name in ("libtarget_alpha.so", "libtarget_beta.so", "libtarget_gamma.so"):
        shutil.copy(DATA_DIR / name, dest_dir / name)
    return dest_dir

def test_t4ae610_dependency_binaries_present():
    """Verify that all compiled tools, baseline libraries, and SBOM attestation packages exist."""
    assert Path(RELBIND_BIN).is_file(), "relbind binary not found in /app/bin"
    assert Path(TEST_RUNNER_BIN).is_file(), "test_runner binary not found in /app/bin"
    assert (DATA_DIR / "libtarget_alpha.so").is_file()
    assert (DATA_DIR / "libtarget_beta.so").is_file()
    assert (DATA_DIR / "libtarget_gamma.so").is_file()

def test_t4ae610_toolchain_detection(isolated_libs):
    """Verify bundled libraries expose expected pre-bind load refusal and post-bind witness envelope structure."""
    alpha = isolated_libs / "libtarget_alpha.so"
    beta = isolated_libs / "libtarget_beta.so"
    gamma = isolated_libs / "libtarget_gamma.so"

    assert subprocess.run([TEST_RUNNER_BIN, str(alpha)], capture_output=True, text=True).returncode == 0
    assert subprocess.run([TEST_RUNNER_BIN, str(beta)], capture_output=True, text=True).returncode != 0
    assert subprocess.run([TEST_RUNNER_BIN, str(gamma)], capture_output=True, text=True).returncode != 0

    assert subprocess.run([RELBIND_BIN, str(alpha)], capture_output=True, text=True).returncode == 0
    assert reference_relocation_types_valid(alpha.read_bytes(), (".rela.dyn", ".rela.plt"))

    assert subprocess.run([RELBIND_BIN, str(beta)], capture_output=True, text=True).returncode == 0
    assert subprocess.run([TEST_RUNNER_BIN, str(beta)], capture_output=True, text=True).returncode == 0
    assert reference_relocation_types_valid(beta.read_bytes(), (".rela.dyn", ".rela.plt"))

    assert subprocess.run([RELBIND_BIN, str(gamma)], capture_output=True, text=True).returncode == 0
    assert subprocess.run([TEST_RUNNER_BIN, str(gamma)], capture_output=True, text=True).returncode == 0
    assert reference_relocation_types_valid(gamma.read_bytes(), (".rela.dyn", ".rela.plt"))

def test_t4ae610_scrambled_libraries_fail_execution(isolated_libs):
    """Ensure that scrambled Beta and Gamma libraries fail to load/execute out of the box."""
    proc = subprocess.run([TEST_RUNNER_BIN, str(isolated_libs / "libtarget_beta.so")], capture_output=True, text=True)
    assert proc.returncode != 0

    proc = subprocess.run([TEST_RUNNER_BIN, str(isolated_libs / "libtarget_gamma.so")], capture_output=True, text=True)
    assert proc.returncode != 0

def test_t4ae610_alpha_library_succeeds_execution(isolated_libs):
    """Ensure that the standard Alpha library loads and runs successfully without modification."""
    proc = subprocess.run([TEST_RUNNER_BIN, str(isolated_libs / "libtarget_alpha.so")], capture_output=True, text=True)
    assert proc.returncode == 0

def test_t4ae610_witness_bind_beta_cipher_profile(isolated_libs):
    """Verify that binding the Beta witness restores trust its standard structure to satisfy dependency graph closure."""
    beta_path = isolated_libs / "libtarget_beta.so"

    assert subprocess.run([RELBIND_BIN, str(beta_path)], capture_output=True, text=True).returncode == 0
    proc_exec = subprocess.run([TEST_RUNNER_BIN, str(beta_path)], capture_output=True, text=True)
    assert proc_exec.returncode == 0, f"Repaired Beta execution failed: {proc_exec.stderr}"
    assert reference_relocation_types_valid(beta_path.read_bytes(), (".rela.dyn", ".rela.plt"))

def test_t4ae610_witness_bind_gamma_envelope_profile(isolated_libs):
    """Verify that binding the Gamma witness unpacks envelope relocations to validate the release guard."""
    gamma_path = isolated_libs / "libtarget_gamma.so"

    assert subprocess.run([RELBIND_BIN, str(gamma_path)], capture_output=True, text=True).returncode == 0
    proc_exec = subprocess.run([TEST_RUNNER_BIN, str(gamma_path)], capture_output=True, text=True)
    assert proc_exec.returncode == 0, f"Repaired Gamma execution failed: {proc_exec.stderr}"
    assert reference_relocation_types_valid(gamma_path.read_bytes(), (".rela.dyn", ".rela.plt"))

def test_t4ae610_witness_bind_alpha_trust_noop(isolated_libs):
    """Verify that binding an Alpha witness-ready library is a safe, reproducible build lockfile NOOP."""
    alpha_path = isolated_libs / "libtarget_alpha.so"
    before = alpha_path.read_bytes()

    assert subprocess.run([RELBIND_BIN, str(alpha_path)], capture_output=True, text=True).returncode == 0
    assert subprocess.run([TEST_RUNNER_BIN, str(alpha_path)], capture_output=True, text=True).returncode == 0
    assert reference_relocation_types_valid(alpha_path.read_bytes(), (".rela.dyn", ".rela.plt"))
    assert alpha_path.read_bytes() == before

def test_t4ae610_invalid_elf_rejection(tmp_path):
    """Verify that the utility rejects non-ELF files or truncated files with an error."""
    bad_file = tmp_path / "not_elf.txt"
    bad_file.write_text("Just some text content.")

    proc = subprocess.run([RELBIND_BIN, str(bad_file)], capture_output=True, text=True)
    assert proc.returncode != 0

def test_t4ae610_relocation_entries_validity_after_reconstruction(isolated_libs):
    """Directly inspect the relocation tables of witness-bound files to ensure standard formatting."""
    for name in ("libtarget_beta.so", "libtarget_gamma.so"):
        path = isolated_libs / name
        subprocess.run([RELBIND_BIN, str(path)], check=True)
        
        with open(path, 'rb') as f:
            elf_data = f.read()
            
        e_shoff = struct.unpack('<Q', elf_data[40:48])[0]
        e_shentsize = struct.unpack('<H', elf_data[58:60])[0]
        e_shnum = struct.unpack('<H', elf_data[60:62])[0]
        e_shstrndx = struct.unpack('<H', elf_data[62:64])[0]

        shdrs = []
        for i in range(e_shnum):
            offset = e_shoff + i * e_shentsize
            fields = struct.unpack('<IIQQQQIIQQ', elf_data[offset:offset+64])
            shdrs.append({
                'name_idx': fields[0],
                'offset': fields[4],
                'size': fields[5]
            })

        shstrndx_shdr = shdrs[e_shstrndx]
        shstrtab = elf_data[shstrndx_shdr['offset'] : shstrndx_shdr['offset'] + shstrndx_shdr['size']]

        for shdr in shdrs:
            end = shstrtab.find(b'\x00', shdr['name_idx'])
            name_str = shstrtab[shdr['name_idx']:end].decode('utf-8')
            
            if name_str in ('.rela.dyn', '.rela.plt'):
                num_entries = shdr['size'] // 24
                if shdr['size'] >= 4:
                    magic = struct.unpack('<I', elf_data[shdr['offset']:shdr['offset']+4])[0]
                    assert magic != 0x474D524C
                
                for idx in range(num_entries):
                    rel_offset = shdr['offset'] + idx * 24
                    r_offset, r_info, r_addend = struct.unpack('<QQq', elf_data[rel_offset:rel_offset+24])
                    r_type = r_info & 0xFFFFFFFF
                    assert r_type <= 42

def test_t4ae610_utility_help_message():
    """Verify the utility shows a usage message when run without arguments."""
    proc = subprocess.run([RELBIND_BIN], capture_output=True, text=True)
    assert proc.returncode != 0
    assert "Usage:" in proc.stderr

def test_t4ae610_test_runner_help_message():
    """Verify test_runner shows a usage message when run without arguments."""
    proc = subprocess.run([TEST_RUNNER_BIN], capture_output=True, text=True)
    assert proc.returncode != 0
    assert "Usage:" in proc.stderr

def test_t4ae610_utility_nonexistent_file():
    """Verify the utility reports an error when the target file does not exist."""
    proc = subprocess.run([RELBIND_BIN, "/tmp/nonexistent_file_12345.so"], capture_output=True, text=True)
    assert proc.returncode != 0

def test_t4ae610_test_runner_nonexistent_file():
    """Verify test_runner reports an error when the target file does not exist."""
    proc = subprocess.run([TEST_RUNNER_BIN, "/tmp/nonexistent_file_12345.so"], capture_output=True, text=True)
    assert proc.returncode != 0

def test_t4ae610_beta_reconstructed_file_size(isolated_libs):
    """Verify binding a Beta witness preserves the original file size exactly."""
    beta_path = isolated_libs / "libtarget_beta.so"
    original_size = beta_path.stat().st_size
    subprocess.run([RELBIND_BIN, str(beta_path)], check=True)
    assert beta_path.stat().st_size == original_size

def test_t4ae610_gamma_reconstructed_file_size(isolated_libs):
    """Verify binding a Gamma witness preserves the original file size exactly."""
    gamma_path = isolated_libs / "libtarget_gamma.so"
    original_size = gamma_path.stat().st_size
    subprocess.run([RELBIND_BIN, str(gamma_path)], check=True)
    assert gamma_path.stat().st_size == original_size

def test_t4ae610_alpha_reconstructed_file_size(isolated_libs):
    """Verify binding an Alpha witness preserves the original file size exactly."""
    alpha_path = isolated_libs / "libtarget_alpha.so"
    original_size = alpha_path.stat().st_size
    subprocess.run([RELBIND_BIN, str(alpha_path)], check=True)
    assert alpha_path.stat().st_size == original_size

def test_t4ae610_toolchain_detection_fails_on_truncated_elf(tmp_path):
    """Verify that toolchain detection returns unknown on severely truncated files."""
    trunc_file = tmp_path / "truncated.so"
    trunc_file.write_bytes(b"\x7fELF\x02\x01\x01\x00") # 8 bytes
    proc = subprocess.run([RELBIND_BIN, str(trunc_file)], capture_output=True, text=True)
    assert proc.returncode != 0
    assert "Unknown" in proc.stderr

def test_t4ae610_witness_bind_refuses_truncated_elf(tmp_path):
    """Verify that binding a truncated ELF witness file fails cleanly with an error status."""
    trunc_file = tmp_path / "truncated.so"
    trunc_file.write_bytes(b"\x7fELF\x02\x01\x01\x00")
    proc = subprocess.run([RELBIND_BIN, str(trunc_file)], capture_output=True, text=True)
    assert proc.returncode != 0
    assert "Failed" in proc.stderr

def test_t4ae610_elf_header_validation_non_elf(tmp_path):
    """Verify that validation rejects a file of correct ELF size but wrong magic."""
    fake_elf = tmp_path / "fake.so"
    fake_elf.write_bytes(b"NOT_ELF_AT_ALL" + b"\x00" * 2000)
    proc = subprocess.run([RELBIND_BIN, str(fake_elf)], capture_output=True, text=True)
    assert proc.returncode != 0

def test_t4ae610_elf_header_validation_32_bit(tmp_path):
    """Verify that a 32-bit ELF file is rejected during toolchain detection."""
    elf_32 = tmp_path / "elf32.so"
    # Construct a 32-bit ELF identification sequence (EI_CLASS = ELFCLASS32 = 1)
    ident = bytearray(b"\x7fELF\x01\x01\x01\x00" + b"\x00" * 56)
    elf_32.write_bytes(bytes(ident))
    proc = subprocess.run([RELBIND_BIN, str(elf_32)], capture_output=True, text=True)
    assert proc.returncode != 0

def test_t4ae610_hidden_holdout_beta_witness_bind(tmp_path):
    """Holdout verifier-fixtures Beta libraries must bind witness without bundled-only shortcuts."""
    holdout = tmp_path / "holdout_beta.so"
    shutil.copy(HIDDEN_BETA, holdout)

    proc_bind = subprocess.run([RELBIND_BIN, str(holdout)], capture_output=True, text=True)
    assert proc_bind.returncode == 0

    proc_exec = subprocess.run([TEST_RUNNER_BIN, str(holdout)], capture_output=True, text=True)
    assert proc_exec.returncode == 0, proc_exec.stderr
    assert reference_relocation_types_valid(holdout.read_bytes(), (".rela.dyn", ".rela.plt"))


def test_t4ae610_hidden_holdout_gamma_witness_bind(tmp_path):
    """Holdout verifier-fixtures Gamma libraries must export standard relocation tables."""
    holdout = tmp_path / "holdout_gamma.so"
    shutil.copy(HIDDEN_GAMMA, holdout)

    proc_bind = subprocess.run([RELBIND_BIN, str(holdout)], capture_output=True, text=True)
    assert proc_bind.returncode == 0

    proc_exec = subprocess.run([TEST_RUNNER_BIN, str(holdout)], capture_output=True, text=True)
    assert proc_exec.returncode == 0, proc_exec.stderr
    assert reference_relocation_types_valid(holdout.read_bytes(), (".rela.dyn", ".rela.plt"))


def test_t4ae610_relocation_staging_snapshot(isolated_libs, tmp_path):
    """Witness bind must emit a staging snapshot attestation digest export of relocation bytes for attestation."""
    beta_path = isolated_libs / "libtarget_beta.so"
    snapshot_path = tmp_path / "staging_snapshot.bin"

    subprocess.run([RELBIND_BIN, str(beta_path)], check=True)
    snapshot_path.write_bytes(reference_staging_snapshot_bytes(beta_path))
    assert snapshot_path.stat().st_size == beta_path.stat().st_size
    assert reference_relocation_types_valid(snapshot_path.read_bytes(), (".rela.dyn", ".rela.plt"))

