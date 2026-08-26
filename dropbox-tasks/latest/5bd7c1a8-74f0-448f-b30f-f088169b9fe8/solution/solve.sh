#!/usr/bin/env bash
set -euo pipefail
cd /app

MARKER=/app/.oracle_fold_fixed
if [[ -f "$MARKER" ]]; then
  exit 0
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

cp -f "$SCRIPT_DIR/fixed/scripts/stage_cohort.sh" /app/scripts/stage_cohort.sh
cp -f "$SCRIPT_DIR/fixed/r/fold_balance.R" /app/r/fold_balance.R

copy_java() {
  local rel="$1"
  install -D "$SCRIPT_DIR/fixed/src/main/java/${rel}" "/app/src/main/java/${rel}"
}

copy_java com/foldlab/util/CohortIds.java
copy_java com/foldlab/cli/AssembleCommand.java
copy_java com/foldlab/csv/CohortCsvReader.java
copy_java com/foldlab/digest/FoldDigest.java
copy_java com/foldlab/digest/CohortChecksum.java
copy_java com/foldlab/digest/AssignmentSeal.java
copy_java com/foldlab/digest/BalanceAnchor.java
copy_java com/foldlab/digest/ManifestSeal.java
copy_java com/foldlab/digest/StagedByteAnchor.java
copy_java com/foldlab/digest/LabelQuorumWitness.java
copy_java com/foldlab/digest/StratumSpreadDigest.java
copy_java com/foldlab/digest/LedgerCoupler.java
copy_java com/foldlab/balance/SkewBandClassifier.java
copy_java com/foldlab/epoch/RotationEpochPlanner.java
copy_java com/foldlab/receipt/ReceiptChainSeal.java
copy_java com/foldlab/eval/FoldParityDigest.java
copy_java com/foldlab/eval/LabelCoverageSeal.java
copy_java com/foldlab/eval/HoldoutMirror.java
copy_java com/foldlab/eval/EvaluationSeal.java
copy_java com/foldlab/eval/StratumEntropyHint.java
copy_java com/foldlab/eval/AssembleAttestation.java
copy_java com/foldlab/eval/FoldLoadSkew.java
copy_java com/foldlab/eval/LabelCardinality.java
copy_java com/foldlab/digest/CohortSpanDigest.java
copy_java com/foldlab/eval/BalanceCoupler.java
copy_java com/foldlab/eval/KitClosure.java
copy_java com/foldlab/receipt/RunChainDigest.java
copy_java com/foldlab/fold/FoldManifestBuilder.java
copy_java com/foldlab/fold/StratifiedAssigner.java
copy_java com/foldlab/r/RBalanceRunner.java
copy_java com/foldlab/stage/CohortStager.java
copy_java com/foldlab/io/FoldReceiptWriter.java
copy_java com/foldlab/eval/ClassPriorSeal.java
copy_java com/foldlab/eval/FoldSplitWitness.java
copy_java com/foldlab/eval/HoldoutEpochCoupler.java
copy_java com/foldlab/eval/StratumStabilityIndex.java
copy_java com/foldlab/eval/TrainFoldMask.java
copy_java com/foldlab/eval/LabelPairCooccurrence.java
copy_java com/foldlab/eval/BalanceDriftWitness.java
copy_java com/foldlab/eval/EpochManifestBinder.java
copy_java com/foldlab/eval/HoldoutExclusionSeal.java
copy_java com/foldlab/eval/FoldKitSeal.java
copy_java com/foldlab/eval/FoldCoverageLattice.java
copy_java com/foldlab/eval/HoldoutTrainTension.java
copy_java com/foldlab/eval/SkewPriorWitness.java
copy_java com/foldlab/eval/EpochReceiptBinder.java
copy_java com/foldlab/eval/FoldKitOuterSeal.java

chmod +x /app/scripts/stage_cohort.sh /app/r/fold_balance.R
mvn -q -o -f /app/pom.xml package
touch "$MARKER"
