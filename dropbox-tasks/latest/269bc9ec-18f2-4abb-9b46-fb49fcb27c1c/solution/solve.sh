#!/bin/bash
set -euo pipefail

for source in \
  AtomicPublisher.java \
  CliOptions.java \
  EngineRunner.java \
  Labels.java \
  ManifestReader.java \
  ParityEvaluator.java \
  Policy.java \
  PpmImage.java \
  Preprocessor.java \
  SourceSpec.java; do
  cp "/solution/fixed/$source" "/app/src/main/java/org/example/parity/$source"
done

cp /solution/fixed/TensorFingerprint.java /app/src/main/java/org/example/parity/TensorFingerprint.java

/app/scripts/fetch_model.sh
/app/scripts/build.sh
/app/scripts/run_trial.sh

python - <<'PY'
import json
from pathlib import Path

report = json.loads(Path('/app/output/parity-report.json').read_text())
assert report['summary']['sample_count'] == 3
assert len(report['samples']) == 3
assert all(len(sample['engines']['pytorch']['probabilities']) == 33 for sample in report['samples'])
PY
