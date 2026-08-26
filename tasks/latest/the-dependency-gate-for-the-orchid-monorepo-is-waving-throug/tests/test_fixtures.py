"""The shipped ledger fixtures and registry snapshot must be untouched — the
policy bundle is the thing under repair, not the data it evaluates."""

import hashlib

LEDGER_PINS = {
    "/app/ledger/dependency_ledger.csv": "edfcd13570f3f848d75ca78287861752a40996c5e40761439eed7b9037c96d16",
    "/app/ledger/quarantine.csv": "70ed6bbe508ac40eae436d21f0d5eec6892da8594bc3484269d90211cecec2d2",
    "/app/ledger/meta.json": "10bb680182b4340901990d80987bc440884494b0d12d5558253f5fc7cf0f574a",
}

REGISTRY_PINS = {
    "/app/models/registry/orchid-internal/ledger-embedder-v2/config.json": "45bcb681809da9aaabf4c59a3ba2b86a9c481ee9f0fae5ac5e2625e48ece416f",
    "/app/models/registry/orchid-internal/ledger-embedder-v2/projection.tsv": "962c27ef3478dcb0cbaee5c3c7215c47f04f81f6c9763e53e6f837490d11cd89",
    "/app/models/registry/orchid-internal/title-scorer/calibration.tsv": "71b2983da9d148b1ce9ac0fddda38f173fd68d8204a30e97b72a497a41d28435",
    "/app/models/registry/orchid-internal/title-scorer/config.json": "5cdb9bfa063753aba01afde6ecc46ade17502e1d02dc8ef15816380b32a04c18",
    "/app/models/registry/sentence-transformers/all-MiniLM-L6-v2/1_Pooling/config.json": "4be450dde3b0273bb9787637cfbd28fe04a7ba6ab9d36ac48e92b11e350ffc23",
    "/app/models/registry/sentence-transformers/all-MiniLM-L6-v2/config.json": "953f9c0d463486b10a6871cc2fd59f223b2c70184f49815e7efbcab5d8908b41",
    "/app/models/registry/sentence-transformers/all-MiniLM-L6-v2/modules.json": "84e40c8e006c9b1d6c122e02cba9b02458120b5fb0c87b746c41e0207cf642cf",
    "/app/models/registry/sentence-transformers/all-MiniLM-L6-v2/sentence_bert_config.json": "fc1993fde0a95c24ec6c022539d41cf6e2f7c9721e5415d6fb6897472a9cd4b7",
    "/app/models/registry/sentence-transformers/all-MiniLM-L6-v2/special_tokens_map.json": "303df45a03609e4ead04bc3dc1536d0ab19b5358db685b6f3da123d05ec200e3",
    "/app/models/registry/sentence-transformers/all-MiniLM-L6-v2/tokenizer_config.json": "acb92769e8195aabd29b7b2137a9e6d6e25c476a4f15aa4355c233426c61576b",
    "/app/models/registry/sentence-transformers/all-MiniLM-L6-v2/vocab.txt": "07eced375cec144d27c900241f3e339478dec958f92fddbc551f295c992038a3",
}


def _sha256(path):
    """Hash one file with SHA-256 and return the hex digest."""
    with open(path, "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()


def test_ledger_fixtures_unmodified():
    """The ledger CSVs and generation metadata carry their shipped content."""
    for path, digest in LEDGER_PINS.items():
        assert _sha256(path) == digest, f"{path} was modified"


def test_registry_snapshot_unmodified():
    """Every model artifact in the registry snapshot carries its shipped content."""
    for path, digest in REGISTRY_PINS.items():
        assert _sha256(path) == digest, f"{path} was modified"
