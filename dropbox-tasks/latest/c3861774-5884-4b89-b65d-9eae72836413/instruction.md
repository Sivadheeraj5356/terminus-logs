The offline ReefBox reef-classifier rejects every capture because its deployment manifest is missing the per-device calibration embedded *inside* the PNG capture files. The deliverable is a single verified inference manifest at **`/app/out/inference_manifest.json`**, produced by running **`terraform apply`**. The calibration format and every processing rule are undocumented except in the field notebook; this file specifies the deliverable and its output contract, and the notebook defines how each value is computed.

## What you are given (under `/app`)
- **`docs/reefbox-field-notebook.md`** — the field-ops notebook. It is the authoritative and complete reference for the calibration format and every processing rule. It is a long, unindexed, append-mostly log of incident reports, cheat-sheets, and dated errata rather than a clean spec, and earlier entries are in places corrected by later dated ones.
- **`data/fixtures/*.png`** — 20 ReefBox capture PNGs. Each may carry a calibration record embedded in a PNG `tEXt` metadata chunk. Some are malformed, mislabeled, or duplicated, as the notebook's incident reports describe.
- **`data/modelcards/global.yaml`, `data/modelcards/sites/<site>.yaml`, `data/modelcards/devices/<device_id>.yaml`** — three layers of model-card configuration. The notebook is the reference for how they combine.
- **`main.tf`** — a Terraform config that, on `terraform apply`, runs `/app/pipeline/build_manifest.sh` (passing the fixtures/model-card/output locations as environment variables). **This file already works; do not modify it.**

## What you must build
Create **`/app/pipeline/build_manifest.sh`** (plus any helper scripts it invokes) so that `terraform apply` writes `/app/out/inference_manifest.json`. Constraints on the build:
- `jq` and `yq` are both installed; the pipeline is expected to be a Bash/`jq`/`yq` analysis.
- It must run fully offline (no network access).
- It must be deterministic: re-running `terraform apply` reproduces byte-identical output.

The verifier runs `terraform apply` itself and checks the resulting manifest.

## Output contract — `/app/out/inference_manifest.json`
A single JSON object with exactly these keys and types. The values below are placeholders — you compute the real ones from the notebook's rules:

```json
{
  "manifest_version": "1.0",
  "channel_order": ["RED", "GREEN", "NIR"],
  "devices": [
    {
      "device_id": "<id>",
      "site": "<site>",
      "source_png": "<png>",
      "sensor_variant": "<variant>",
      "channel_scales": { "RED": 0.0, "GREEN": 0.0, "NIR": 0.0 },
      "model_name": "<name>",
      "model_version": "<version>",
      "input_size": [0, 0],
      "confidence_threshold": 0.0,
      "labels_version": "<labels>"
    }
  ],
  "quarantined": [
    { "source_png": "<png>", "reason": "<reason>" }
  ],
  "summary": { "included": 0, "quarantined": 0 }
}
```

The following are part of the required output contract (the notebook defines how the values themselves are derived):

- **`manifest_version`** is the string `"1.0"`.
- **`channel_order`** is exactly `["RED", "GREEN", "NIR"]`.
- **`devices`** is an array **sorted by `device_id`**. In each entry, `channel_scales` are numbers **rounded to 6 decimal places** keyed `RED`/`GREEN`/`NIR`; `sensor_variant` is a bare single-letter string; and `source_png` is the **bare capture filename**, with no directory path.
- **`quarantined`** is an array **sorted by `source_png`**. Each entry is `{ "source_png", "reason" }`, where `source_png` is a bare filename and `reason` is exactly one of these tokens: `missing_calibration`, `bad_checksum`, `sensor_variant_c`, `unknown_site`, `superseded`.
- **`summary`** is `{ "included", "quarantined" }`, holding the lengths of the `devices` and `quarantined` arrays respectively.

Which captures are included versus quarantined and why, how each `reason` is chosen, the calibration decode, the per-channel scale arithmetic, and the model-card precedence (including its exceptions) are all defined in the field notebook.
