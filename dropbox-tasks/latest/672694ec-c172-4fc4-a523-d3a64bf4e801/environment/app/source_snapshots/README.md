# Source grounding — TPM 2.0 quote / integrity measurement

This task uses a **bounded TPM 2.0-inspired offline attestation profile**. It does
not claim to implement the full TPM 2.0 Library, unrestricted TCG/EFI event logs,
or platform attestation protocols.

## Primary sources

| Document | Publisher | Version / date | Relevant focus | Retrieval date |
|---|---|---|---|---|
| TPM 2.0 Library Specification | Trusted Computing Group | Family 2.0, Level 00 Revision 01.85 (Version 185), March 2026 | `TPMS_ATTEST`, `TPMS_QUOTE_INFO`, `TPM2_Quote`, attestation magic/type, PCR selection and digest, signature coverage of attestation structure | 2026-07-20 |
| TCG Guidance / event-log verification practices | Trusted Computing Group | Current published event-log / attestation verification guidance as of retrieval | Verify quote signature; compare verifier challenge (freshness); extract selected-PCR digest; treat event ordering as significant because PCR extension is order-dependent | 2026-07-20 |

Portal / catalog entry points commonly used for TCG publications:

- https://trustedcomputinggroup.org/resource/tpm-library-specification/
- https://trustedcomputinggroup.org/ (TCG resource catalog for event-log / attestation guidance)

## Concise conceptual citations

1. **`TPMS_ATTEST`** carries TPM-generated magic, attestation type, qualified signer,
   caller-supplied extra data, clock information, firmware version, and
   type-specific attested information. For quotes, **`TPMS_QUOTE_INFO`** carries a
   PCR selection and PCR digest; the signature covers the attestation structure.

2. **`TPM2_Quote`** hashes the concatenation of the selected PCR digest values
   using the signing-scheme hash algorithm and returns a signed quote structure.

3. Common quote verification checks the signature, qualifying data used as a
   freshness nonce, and the quoted PCR values.

4. Event-log guidance treats event ordering as significant: PCR extension is
   order-dependent, so replay must follow semantic event order.

## Task profile mapping

| Official concept | Bounded profile treatment |
|---|---|
| `TPM_GENERATED_VALUE` | `magic = 0xff544347` |
| `TPM_ST_ATTEST_QUOTE` | `type = 0x8018` |
| `TPM_ALG_SHA256` | `0x000b` (quote hash + signature hash) |
| `TPM_ALG_ECDSA` | `0x0018` over P-256 |
| Qualifying data / extraData | Exact 32-byte verifier nonce in `extra_data` |
| Selected PCR digest | SHA-256 over concatenated selected PCR values in ascending index order |
| Event-log PCR extend | SHA-256(`old_pcr \|\| measurement_digest_bytes`) |

No full official specification text is reproduced here.
