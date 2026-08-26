"""End-to-end demonstration of milestone 3: submit a signed manifest to the
transparency-log API and persist the returned receipt and audit log."""

import json
import sys
from pathlib import Path

sys.path.insert(0, "/app/transparency")

from app import create_app  # noqa: E402

manifest = json.loads(Path("/app/data/manifest.json").read_text())
signature = Path("/app/out/manifest.sig").read_text().strip()
public_key_pem = Path("/app/keys/ed25519_public.pem").read_text()

app = create_app("/app/out/transparency_log.jsonl")
client = app.test_client()

resp = client.post(
    "/signatures",
    json={"manifest": manifest, "signature": signature, "public_key_pem": public_key_pem},
)
receipt = resp.get_json()
Path("/app/out/receipt.json").write_text(json.dumps(receipt, indent=2))

audit = client.get("/audit").get_json()
Path("/app/out/audit.json").write_text(json.dumps(audit, indent=2))

print(f"submit status={resp.status_code}")
print(f"receipt index={receipt.get('receipt', {}).get('index')}")
print(f"chain_valid={audit.get('chain_valid')}")
