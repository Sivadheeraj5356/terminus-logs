# Trust envelope charter

Release engineering binds third-party shared objects to internal trust envelopes before they enter the dependency graph. Custom vendor linkers may emit cipher-masked or envelope-packed relocation tables as an obfuscation layer; relbind is the offline gate that normalizes those tables into witness-ready ELF64 form.

Decoy modules under `/app/elf/` are never linked into the attestation path. Bundled attestation libraries live under `/app/data/binaries/`. Policy gates compare bound witnesses against independent reference checks during grading.

Agents extend relbind kernel modules under `/app/trust_probe`, `/app/cipher_unmask`, `/app/envelope_unpack`, and `/app/witness_router` per the contracts above.
