# Relocation trust policy

Policy gates refuse libraries whose dynamic relocation tables cannot be bound to a standard witness envelope. Each encoding profile defines how relocation bytes are stored before attestation:

| Profile | Trust posture | Section signal |
|---------|---------------|----------------|
| Alpha | Witness-ready | Standard 24-byte `Elf64_Rela` rows |
| Beta | Cipher-masked | Valid row size but scrambled `r_info` fields |
| Gamma | Envelope-packed | GMRL magic header at section start |

Relbind must probe profiles by inspecting `.rela.dyn` and `.rela.plt` contents, never by filename heuristics. Unknown or tampered ELF structures must refuse with non-zero exit and a policy diagnostic on stderr.
