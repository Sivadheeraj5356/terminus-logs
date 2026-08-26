#!/usr/bin/env python3
"""Apply all three oracle fixes."""
from pathlib import Path

# Fix A: correct byte offsets in a1.rs
print("[oracle] applying fix A...")
a1 = Path("/app/environment/src/a1.rs").read_text()
a1 = a1.replace(
    "let datum_len = u32::from_le_bytes([b[8], b[9], b[8], b[9]]);",
    "let datum_len = u32::from_le_bytes([b[4], b[5], b[6], b[7]]);"
)
a1 = a1.replace(
    "let checksum = u16::from_le_bytes([b[4], b[5]]);",
    "let checksum = u16::from_le_bytes([b[8], b[9]]);"
)
Path("/app/environment/src/a1.rs").write_text(a1)
print("[oracle] fixed src/a1.rs")

# Fix B: full-field comparison in b1.rs
print("[oracle] applying fix B...")
b1 = Path("/app/environment/src/b1.rs").read_text()
old_b = (
    "    if bin_view.seq_id == txt_view.seq_id {\n"
    "        return CompatTrace {\n"
    "            seq_id: bin_view.seq_id,\n"
    "            state: CompatState::Compatible,\n"
    "            diverged_fields: vec![],\n"
    "        };\n"
    "    }\n"
    "\n"
    "    CompatTrace {\n"
    "        seq_id: bin_view.seq_id,\n"
    "        state: CompatState::Diverged,\n"
    '        diverged_fields: vec!["seq_id".to_string()],\n'
    "    }"
)
new_b = (
    "    let mut diverged: Vec<String> = Vec::new();\n"
    '    if bin_view.datum_len != txt_view.datum_len { diverged.push("datum_len".to_string()); }\n'
    '    if bin_view.checksum != txt_view.checksum { diverged.push("checksum".to_string()); }\n'
    '    if bin_view.status_nibble != txt_view.status_nibble { diverged.push("status_nibble".to_string()); }\n'
    '    if bin_view.revision_tag != txt_view.revision_tag { diverged.push("revision_tag".to_string()); }\n'
    '    if bin_view.label != txt_view.label { diverged.push("label".to_string()); }\n'
    "    if diverged.is_empty() {\n"
    "        CompatTrace { seq_id: bin_view.seq_id, state: CompatState::Compatible, diverged_fields: vec![] }\n"
    "    } else {\n"
    "        CompatTrace { seq_id: bin_view.seq_id, state: CompatState::Diverged, diverged_fields: diverged }\n"
    "    }"
)
b1 = b1.replace(old_b, new_b)
Path("/app/environment/src/b1.rs").write_text(b1)
print("[oracle] fixed src/b1.rs")

# Fix C: propagate raw_status in engine.rs
print("[oracle] applying fix C...")
eng = Path("/app/environment/tools/xscope/src/engine.rs").read_text()
eng = eng.replace(
    "        let raw_status: u8 = 0; // status byte not propagated from the raw buffer",
    "        let raw_status = if cursor + 10 < buf.len() { buf[cursor + 10] } else { 0 };"
)
eng = eng.replace("    let _ = cursor;\n\n", "")
Path("/app/environment/tools/xscope/src/engine.rs").write_text(eng)
print("[oracle] fixed tools/xscope/src/engine.rs")
