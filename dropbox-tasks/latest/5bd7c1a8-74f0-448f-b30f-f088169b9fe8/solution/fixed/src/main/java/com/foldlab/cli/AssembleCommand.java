package com.foldlab.cli;

import com.foldlab.balance.SkewBandClassifier;
import com.foldlab.csv.CohortCsvReader;
import com.foldlab.digest.AssignmentSeal;
import com.foldlab.digest.BalanceAnchor;
import com.foldlab.digest.CohortChecksum;
import com.foldlab.digest.CohortSpanDigest;
import com.foldlab.digest.FoldDigest;
import com.foldlab.digest.LabelQuorumWitness;
import com.foldlab.digest.LedgerCoupler;
import com.foldlab.digest.ManifestSeal;
import com.foldlab.digest.StagedByteAnchor;
import com.foldlab.digest.StratumSpreadDigest;
import com.foldlab.epoch.RotationEpochPlanner;
import com.foldlab.eval.AssembleAttestation;
import com.foldlab.eval.BalanceCoupler;
import com.foldlab.eval.BalanceDriftWitness;
import com.foldlab.eval.ClassPriorSeal;
import com.foldlab.eval.EpochManifestBinder;
import com.foldlab.eval.EvaluationSeal;
import com.foldlab.eval.EpochReceiptBinder;
import com.foldlab.eval.FoldCoverageLattice;
import com.foldlab.eval.FoldKitOuterSeal;
import com.foldlab.eval.FoldKitSeal;
import com.foldlab.eval.HoldoutTrainTension;
import com.foldlab.eval.SkewPriorWitness;
import com.foldlab.eval.FoldLoadSkew;
import com.foldlab.eval.FoldParityDigest;
import com.foldlab.eval.FoldSplitWitness;
import com.foldlab.eval.HoldoutEpochCoupler;
import com.foldlab.eval.HoldoutExclusionSeal;
import com.foldlab.eval.HoldoutMirror;
import com.foldlab.eval.KitClosure;
import com.foldlab.eval.LabelCardinality;
import com.foldlab.eval.LabelCoverageSeal;
import com.foldlab.eval.LabelPairCooccurrence;
import com.foldlab.eval.StratumEntropyHint;
import com.foldlab.eval.StratumStabilityIndex;
import com.foldlab.eval.TrainFoldMask;
import com.foldlab.fold.FoldManifestBuilder;
import com.foldlab.fold.StratifiedAssigner;
import com.foldlab.io.FoldReceiptWriter;
import com.foldlab.io.ManifestWriter;
import com.foldlab.model.FoldRecord;
import com.foldlab.model.FoldRow;
import com.foldlab.r.RBalanceRunner;
import com.foldlab.receipt.ReceiptChainSeal;
import com.foldlab.receipt.RunChainDigest;
import com.foldlab.stage.CohortStager;
import java.nio.file.Path;
import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

public final class AssembleCommand {
    private static final Path MANIFEST_PATH = Path.of("/app/var/fold_manifest.json");
    private static final Path RECEIPT_PATH = Path.of("/app/var/fold_receipt.jsonl");

    private final Path dataset;
    private final int foldCount;
    private final String labelColumn;

    private AssembleCommand(Path dataset, int foldCount, String labelColumn) {
        this.dataset = dataset;
        this.foldCount = foldCount;
        this.labelColumn = labelColumn;
    }

    public static AssembleCommand parse(String[] args) {
        String dataset = null;
        String labelColumn = null;
        Integer foldCount = null;
        for (int i = 1; i < args.length; i++) {
            String flag = args[i];
            if ("--dataset".equals(flag) && i + 1 < args.length) {
                dataset = args[++i];
            } else if ("--folds".equals(flag) && i + 1 < args.length) {
                foldCount = Integer.parseInt(args[++i]);
            } else if ("--label".equals(flag) && i + 1 < args.length) {
                labelColumn = args[++i];
            }
        }
        if (dataset == null || labelColumn == null || foldCount == null || foldCount < 1) {
            throw new IllegalArgumentException("missing required assemble flags");
        }
        return new AssembleCommand(Path.of(dataset), foldCount, labelColumn);
    }

    public void run() throws Exception {
        CohortStager stager = new CohortStager();
        Path stagedPath = stager.stage(dataset, labelColumn);
        String stagedFingerprint = new StagedByteAnchor().compute(stagedPath);

        CohortCsvReader reader = new CohortCsvReader();
        List<FoldRow> rows = reader.read(stagedPath, labelColumn);

        StratifiedAssigner assigner = new StratifiedAssigner();
        Map<Integer, List<String>> assignment = assigner.assign(rows, foldCount);

        String cohortChecksum = new CohortChecksum().compute(rows);
        String assignmentSeal = new AssignmentSeal().compute(rows, assignment);

        FoldManifestBuilder builder = new FoldManifestBuilder();
        List<FoldRecord> records = builder.buildRecords(rows, assignment);
        String quorumWitness = new LabelQuorumWitness().compute(records);
        String stratumSpreadDigest = new StratumSpreadDigest().compute(records);
        String foldParityDigest = new FoldParityDigest().compute(records);
        String labelCoverageSeal = new LabelCoverageSeal().compute(records, foldCount);
        String stratumEntropyHint = new StratumEntropyHint().compute(records, foldCount);

        Map<String, Object> interim = buildPayload(
                true,
                rows.size(),
                records,
                null,
                null,
                null,
                null,
                null,
                null,
                null,
                null,
                null,
                null,
                null,
                null,
                null,
                0,
                null,
                null,
                0,
                null,
                null,
                null);
        ManifestWriter writer = new ManifestWriter();
        writer.write(MANIFEST_PATH, interim);

        RBalanceRunner balanceRunner = new RBalanceRunner();
        Map<String, Object> balance = balanceRunner.run(MANIFEST_PATH);

        String digest = new FoldDigest().compute(records);
        double maxLabelSkew = ((Number) balance.get("max_label_skew")).doubleValue();
        String skewBand = String.valueOf(balance.get("skew_band"));
        SkewBandClassifier bandClassifier = new SkewBandClassifier();
        if (!bandClassifier.classify(maxLabelSkew).equals(skewBand)) {
            throw new IllegalStateException("skew_band from R does not match classifier bands");
        }
        String balanceAnchor = new BalanceAnchor().compute(digest, maxLabelSkew);
        String bandAnchor = bandClassifier.bandAnchor(skewBand, digest);
        String manifestSeal =
                new ManifestSeal().compute(cohortChecksum, assignmentSeal, balanceAnchor, foldCount);
        RotationEpochPlanner epochPlanner = new RotationEpochPlanner();
        int rotationEpoch = epochPlanner.nextEpoch();
        LedgerCoupler ledgerCoupler = new LedgerCoupler();
        String epochSeal = ledgerCoupler.epochSeal(rotationEpoch, manifestSeal);
        String ledgerRoot = ledgerCoupler.ledgerRoot(stagedFingerprint, cohortChecksum, epochSeal);
        String receiptChain = new ReceiptChainSeal().compute(manifestSeal, RECEIPT_PATH);
        int holdoutFoldId = new HoldoutMirror().holdoutFoldId(rotationEpoch, foldCount);
        String evaluationSeal =
                new EvaluationSeal()
                        .compute(foldParityDigest, labelCoverageSeal, holdoutFoldId, manifestSeal);
        String assembleAttestation =
                new AssembleAttestation()
                        .compute(evaluationSeal, ledgerRoot, stratumEntropyHint);
        int foldLoadSkew = new FoldLoadSkew().compute(records);
        int labelCardinality = new LabelCardinality().compute(records);
        String cohortSpanDigest = new CohortSpanDigest().compute(records);
        String balanceCoupler = new BalanceCoupler().compute(balanceAnchor, bandAnchor, skewBand);
        String kitClosure =
                new KitClosure()
                        .compute(
                                assembleAttestation,
                                foldLoadSkew,
                                labelCardinality,
                                cohortSpanDigest,
                                balanceCoupler);
        String runChainDigest = new RunChainDigest().compute(kitClosure, RECEIPT_PATH);

        String classPriorSeal = new ClassPriorSeal().compute(records, rows.size());
        String foldSplitWitness = new FoldSplitWitness().compute(records);
        String holdoutEpochCoupler =
                new HoldoutEpochCoupler()
                        .compute(holdoutFoldId, rotationEpoch, foldCount, evaluationSeal);
        String stratumStabilityIndex = new StratumStabilityIndex().compute(records);
        String trainFoldMask = new TrainFoldMask().compute(records, holdoutFoldId);
        String labelPairCooccurrence = new LabelPairCooccurrence().compute(records);
        String balanceDriftWitness =
                new BalanceDriftWitness()
                        .compute(records, rows.size(), maxLabelSkew, skewBand);
        String epochManifestBinder =
                new EpochManifestBinder()
                        .compute(rotationEpoch, digest, classPriorSeal);
        String holdoutExclusionSeal =
                new HoldoutExclusionSeal()
                        .compute(trainFoldMask, holdoutFoldId, foldLoadSkew);
        String foldKitSeal =
                new FoldKitSeal()
                        .compute(
                                kitClosure,
                                classPriorSeal,
                                foldSplitWitness,
                                holdoutEpochCoupler,
                                stratumStabilityIndex,
                                trainFoldMask,
                                labelPairCooccurrence,
                                balanceDriftWitness,
                                epochManifestBinder,
                                holdoutExclusionSeal);

        String foldCoverageLattice =
                new FoldCoverageLattice()
                        .compute(
                                labelCoverageSeal,
                                foldParityDigest,
                                stratumStabilityIndex,
                                labelCardinality);
        String holdoutTrainTension =
                new HoldoutTrainTension()
                        .compute(
                                trainFoldMask,
                                holdoutExclusionSeal,
                                holdoutEpochCoupler,
                                foldLoadSkew);
        String skewPriorWitness =
                new SkewPriorWitness()
                        .compute(
                                balanceDriftWitness,
                                classPriorSeal,
                                balanceCoupler,
                                maxLabelSkew);
        String epochReceiptBinder =
                new EpochReceiptBinder()
                        .compute(
                                epochManifestBinder,
                                runChainDigest,
                                receiptChain,
                                rotationEpoch);
        String foldKitOuterSeal =
                new FoldKitOuterSeal()
                        .compute(
                                foldKitSeal,
                                foldCoverageLattice,
                                holdoutTrainTension,
                                skewPriorWitness,
                                epochReceiptBinder);


        Map<String, Object> finalPayload = buildPayload(
                true,
                rows.size(),
                records,
                balance,
                digest,
                cohortChecksum,
                assignmentSeal,
                balanceAnchor,
                manifestSeal,
                stagedFingerprint,
                quorumWitness,
                stratumSpreadDigest,
                bandAnchor,
                receiptChain,
                epochSeal,
                ledgerRoot,
                rotationEpoch,
                foldParityDigest,
                labelCoverageSeal,
                holdoutFoldId,
                evaluationSeal,
                stratumEntropyHint,
                assembleAttestation);
        finalPayload.put("fold_load_skew", foldLoadSkew);
        finalPayload.put("label_cardinality", labelCardinality);
        finalPayload.put("cohort_span_digest", cohortSpanDigest);
        finalPayload.put("balance_coupler", balanceCoupler);
        finalPayload.put("kit_closure", kitClosure);
        finalPayload.put("run_chain_digest", runChainDigest);
        finalPayload.put("class_prior_seal", classPriorSeal);
        finalPayload.put("fold_split_witness", foldSplitWitness);
        finalPayload.put("holdout_epoch_coupler", holdoutEpochCoupler);
        finalPayload.put("stratum_stability_index", stratumStabilityIndex);
        finalPayload.put("train_fold_mask", trainFoldMask);
        finalPayload.put("label_pair_cooccurrence", labelPairCooccurrence);
        finalPayload.put("balance_drift_witness", balanceDriftWitness);
        finalPayload.put("epoch_manifest_binder", epochManifestBinder);
        finalPayload.put("holdout_exclusion_seal", holdoutExclusionSeal);
        finalPayload.put("fold_kit_seal", foldKitSeal);
        finalPayload.put("fold_coverage_lattice", foldCoverageLattice);
        finalPayload.put("holdout_train_tension", holdoutTrainTension);
        finalPayload.put("skew_prior_witness", skewPriorWitness);
        finalPayload.put("epoch_receipt_binder", epochReceiptBinder);
        finalPayload.put("fold_kit_outer_seal", foldKitOuterSeal);
        writer.write(MANIFEST_PATH, finalPayload);

        Map<String, Object> receipt = new LinkedHashMap<>();
        receipt.put("row_count", rows.size());
        receipt.put("fold_count", foldCount);
        receipt.put("label_column", labelColumn);
        receipt.put("manifest_seal", manifestSeal);
        receipt.put("fold_digest", digest);
        receipt.put("receipt_chain", receiptChain);
        receipt.put("rotation_epoch", rotationEpoch);
        receipt.put("ledger_root", ledgerRoot);
        receipt.put("evaluation_seal", evaluationSeal);
        receipt.put("assemble_attestation", assembleAttestation);
        receipt.put("holdout_fold_id", holdoutFoldId);
        receipt.put("kit_closure", kitClosure);
        receipt.put("run_chain_digest", runChainDigest);
        receipt.put("fold_load_skew", foldLoadSkew);
        receipt.put("label_cardinality", labelCardinality);
        receipt.put("balance_coupler", balanceCoupler);
        receipt.put("cohort_span_digest", cohortSpanDigest);
        receipt.put("class_prior_seal", classPriorSeal);
        receipt.put("fold_split_witness", foldSplitWitness);
        receipt.put("holdout_epoch_coupler", holdoutEpochCoupler);
        receipt.put("stratum_stability_index", stratumStabilityIndex);
        receipt.put("train_fold_mask", trainFoldMask);
        receipt.put("label_pair_cooccurrence", labelPairCooccurrence);
        receipt.put("balance_drift_witness", balanceDriftWitness);
        receipt.put("epoch_manifest_binder", epochManifestBinder);
        receipt.put("holdout_exclusion_seal", holdoutExclusionSeal);
        receipt.put("fold_kit_seal", foldKitSeal);
        receipt.put("fold_coverage_lattice", foldCoverageLattice);
        receipt.put("holdout_train_tension", holdoutTrainTension);
        receipt.put("skew_prior_witness", skewPriorWitness);
        receipt.put("epoch_receipt_binder", epochReceiptBinder);
        receipt.put("fold_kit_outer_seal", foldKitOuterSeal);
        new FoldReceiptWriter().append(RECEIPT_PATH, receipt);
        epochPlanner.commitEpoch(rotationEpoch);

        Map<String, Object> stdout = new LinkedHashMap<>(finalPayload);
        stdout.put("staged_path", stagedPath.toString());
        System.out.println(writer.toJson(stdout));
    }

    private Map<String, Object> buildPayload(
            boolean ok,
            int rowCount,
            List<FoldRecord> records,
            Map<String, Object> balance,
            String digest,
            String cohortChecksum,
            String assignmentSeal,
            String balanceAnchor,
            String manifestSeal,
            String stagedFingerprint,
            String quorumWitness,
            String stratumSpreadDigest,
            String bandAnchor,
            String receiptChain,
            String epochSeal,
            String ledgerRoot,
            int rotationEpoch,
            String foldParityDigest,
            String labelCoverageSeal,
            int holdoutFoldId,
            String evaluationSeal,
            String stratumEntropyHint,
            String assembleAttestation) {
        Map<String, Object> payload = new LinkedHashMap<>();
        payload.put("ok", ok);
        payload.put("row_count", rowCount);
        payload.put("fold_count", foldCount);
        payload.put("label_column", labelColumn);
        payload.put("folds", toFoldMaps(records));
        payload.put("balance", balance == null ? new LinkedHashMap<>() : balance);
        payload.put("fold_digest", digest == null ? "" : digest);
        payload.put("cohort_checksum", cohortChecksum == null ? "" : cohortChecksum);
        payload.put("assignment_seal", assignmentSeal == null ? "" : assignmentSeal);
        payload.put("balance_anchor", balanceAnchor == null ? "" : balanceAnchor);
        payload.put("manifest_seal", manifestSeal == null ? "" : manifestSeal);
        payload.put("staged_fingerprint", stagedFingerprint == null ? "" : stagedFingerprint);
        payload.put("quorum_witness", quorumWitness == null ? "" : quorumWitness);
        payload.put("stratum_spread_digest", stratumSpreadDigest == null ? "" : stratumSpreadDigest);
        payload.put("band_anchor", bandAnchor == null ? "" : bandAnchor);
        payload.put("receipt_chain", receiptChain == null ? "" : receiptChain);
        payload.put("epoch_seal", epochSeal == null ? "" : epochSeal);
        payload.put("ledger_root", ledgerRoot == null ? "" : ledgerRoot);
        payload.put("rotation_epoch", rotationEpoch);
        payload.put("fold_parity_digest", foldParityDigest == null ? "" : foldParityDigest);
        payload.put("label_coverage_seal", labelCoverageSeal == null ? "" : labelCoverageSeal);
        payload.put("holdout_fold_id", holdoutFoldId);
        payload.put("evaluation_seal", evaluationSeal == null ? "" : evaluationSeal);
        payload.put("stratum_entropy_hint", stratumEntropyHint == null ? "" : stratumEntropyHint);
        payload.put("assemble_attestation", assembleAttestation == null ? "" : assembleAttestation);
        return payload;
    }

    private List<Map<String, Object>> toFoldMaps(List<FoldRecord> records) {
        List<Map<String, Object>> folds = new ArrayList<>();
        for (FoldRecord record : records) {
            Map<String, Object> fold = new LinkedHashMap<>();
            fold.put("fold_id", record.getFoldId());
            fold.put("row_ids", record.getRowIds());
            fold.put("label_counts", record.getLabelCounts());
            folds.add(fold);
        }
        return folds;
    }
}
