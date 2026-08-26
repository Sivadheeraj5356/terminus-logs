#!/bin/bash
set -eo pipefail

cd /app

cat > coinsurance-report/src/main/java/com/coinsurancerecovery/report/FinancePolicy.java << 'EOF'
package com.coinsurancerecovery.report;

import java.math.BigDecimal;
import java.math.RoundingMode;

public class FinancePolicy {
    public static BigDecimal netRecovery(
            BigDecimal indemnityShare,
            BigDecimal tierAdjustmentAmount,
            BigDecimal quotaCreditAmount,
            BigDecimal processingFeeAmount,
            BigDecimal premiumHoldbackAmount
    ) {
        return indemnityShare
                .subtract(tierAdjustmentAmount)
                .subtract(quotaCreditAmount)
                .add(processingFeeAmount)
                .subtract(premiumHoldbackAmount)
                .setScale(2, RoundingMode.HALF_UP);
    }
}
EOF

cat > coinsurance-engine/src/main/java/com/coinsurancerecovery/engine/CoinsuranceProcessor.java << 'EOF'
package com.coinsurancerecovery.engine;

import com.coinsurancerecovery.core.EligibilityRules;
import com.coinsurancerecovery.core.CoinsurancePolicy;
import com.coinsurancerecovery.core.CoinsuranceConfig;
import com.coinsurancerecovery.report.FinancePolicy;
import com.coinsurancerecovery.report.ProcessedCoinsurancePolicy;

import java.math.BigDecimal;
import java.util.ArrayList;
import java.util.Comparator;
import java.util.List;

public class CoinsuranceProcessor {
    private final CoinsuranceConfig config;
    private final IndemnityShareCalculator indemnityShareCalculator = new IndemnityShareCalculator();
    private final ProcessingFeeCalculator processingFeeCalculator = new ProcessingFeeCalculator();
    private final TierAdjustmentEngine tierAdjustmentEngine = new TierAdjustmentEngine();
    private final QuotaCreditEngine quotaCreditEngine = new QuotaCreditEngine();
    private final PremiumHoldbackCalculator premiumHoldbackCalculator = new PremiumHoldbackCalculator();
    private final EligibilityRules eligibilityRules = new EligibilityRules();

    public CoinsuranceProcessor(CoinsuranceConfig config) {
        this.config = config;
    }

    public List<ProcessedCoinsurancePolicy> process(List<CoinsurancePolicy> policies) {
        List<ProcessedCoinsurancePolicy> processed = new ArrayList<>();
        for (CoinsurancePolicy towerLayer : policies) {
            if (!eligibilityRules.isApproved(towerLayer) || !eligibilityRules.hasLossAmount(towerLayer)) {
                continue;
            }
            if (!eligibilityRules.meetsMinimum(towerLayer, config)) {
                continue;
            }

            BigDecimal indemnityShare = indemnityShareCalculator.indemnityShare(towerLayer, config);
            BigDecimal processingFeeAmount = processingFeeCalculator.processingFeeAmount(towerLayer, config);
            BigDecimal adjustmentRate = tierAdjustmentEngine.adjustmentRate(towerLayer, config);
            BigDecimal quotaCreditAmount = quotaCreditEngine.quotaCreditAmount(towerLayer, indemnityShare, config);
            BigDecimal tierAdjustmentAmount = tierAdjustmentEngine.tierAdjustmentAmount(
                    towerLayer, indemnityShare, quotaCreditAmount, config
            );
            BigDecimal premiumHoldbackAmount = premiumHoldbackCalculator.premiumHoldbackAmount(
                    towerLayer, indemnityShare, tierAdjustmentAmount, quotaCreditAmount, processingFeeAmount, config
            );
            BigDecimal netRecovery = FinancePolicy.netRecovery(
                    indemnityShare, tierAdjustmentAmount, quotaCreditAmount, processingFeeAmount, premiumHoldbackAmount
            );

            processed.add(new ProcessedCoinsurancePolicy(
                    towerLayer.getId(),
                    towerLayer.getCedent(),
                    towerLayer.getLossAmount(),
                    towerLayer.getDeductibleAmount(),
                    towerLayer.getCoinsuranceRate(),
                    towerLayer.getTreatyTier(),
                    indemnityShare,
                    processingFeeAmount,
                    adjustmentRate,
                    tierAdjustmentAmount,
                    quotaCreditAmount,
                    premiumHoldbackAmount,
                    netRecovery
            ));
        }

        processed.sort(
                Comparator.comparing(ProcessedCoinsurancePolicy::getNetRecovery)
                        .reversed()
                        .thenComparing(ProcessedCoinsurancePolicy::getId)
        );
        return processed;
    }
}
EOF

cat > coinsurance-report/src/main/java/com/coinsurancerecovery/report/ReportGenerator.java << 'EOF'
package com.coinsurancerecovery.report;

import com.google.gson.Gson;
import com.google.gson.GsonBuilder;

import java.io.IOException;
import java.math.BigDecimal;
import java.math.RoundingMode;
import java.nio.file.Files;
import java.nio.file.Path;
import java.time.Instant;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

public class ReportGenerator {
    private static final Gson GSON = new GsonBuilder().setPrettyPrinting().create();

    public void writeReport(List<ProcessedCoinsurancePolicy> policies, Path outputPath) throws IOException {
        BigDecimal totalIndemnityShare = BigDecimal.ZERO;
        BigDecimal totalProcessingFee = BigDecimal.ZERO;
        BigDecimal totalTierAdjustment = BigDecimal.ZERO;
        BigDecimal totalQuotaCredit = BigDecimal.ZERO;
        BigDecimal totalPremiumHoldback = BigDecimal.ZERO;
        BigDecimal totalRecovery = BigDecimal.ZERO;

        List<Map<String, Object>> rows = policies.stream().map(layer -> {
            Map<String, Object> row = new LinkedHashMap<>();
            row.put("id", layer.getId());
            row.put("insurer", layer.getCedent());
            row.put("grossIncurred", scaleMoney(layer.getLossAmount()));
            row.put("deductibleAmount", scaleMoney(layer.getLayerAttachment()));
            row.put("coinsuranceRate", scaleMoney(layer.getLayerCap()));
            row.put("policyTier", layer.getTreatyTier());
            row.put("indemnityShare", scaleMoney(layer.getBaseRecovery()));
            row.put("processingFeeAmount", scaleMoney(layer.getProcessingFeeAmount()));
            row.put("adjustmentRate", scaleRate(layer.getAdjustmentRate()));
            row.put("tierAdjustmentAmount", scaleMoney(layer.getTierAdjustmentAmount()));
            row.put("quotaCreditAmount", scaleMoney(layer.getCatastropheCreditAmount()));
            row.put("premiumHoldbackAmount", scaleMoney(layer.getRetentionHoldbackAmount()));
            row.put("netRecovery", scaleMoney(layer.getNetRecovery()));
            return row;
        }).toList();

        for (ProcessedCoinsurancePolicy layer : policies) {
            totalIndemnityShare = totalIndemnityShare.add(layer.getBaseRecovery());
            totalProcessingFee = totalProcessingFee.add(layer.getProcessingFeeAmount());
            totalTierAdjustment = totalTierAdjustment.add(layer.getTierAdjustmentAmount());
            totalQuotaCredit = totalQuotaCredit.add(layer.getCatastropheCreditAmount());
            totalPremiumHoldback = totalPremiumHoldback.add(layer.getRetentionHoldbackAmount());
            totalRecovery = totalRecovery.add(layer.getNetRecovery());
        }

        Map<String, Object> summary = new LinkedHashMap<>();
        summary.put("policyCount", policies.size());
        summary.put("totalIndemnityShare", scaleMoney(totalIndemnityShare));
        summary.put("totalProcessingFee", scaleMoney(totalProcessingFee));
        summary.put("totalTierAdjustment", scaleMoney(totalTierAdjustment));
        summary.put("totalQuotaCredit", scaleMoney(totalQuotaCredit));
        summary.put("totalPremiumHoldback", scaleMoney(totalPremiumHoldback));
        summary.put("totalRecovery", scaleMoney(totalRecovery));

        Map<String, Object> report = new LinkedHashMap<>();
        report.put("generatedAt", Instant.now().toString());
        report.put("policies", rows);
        report.put("summary", summary);

        Files.createDirectories(outputPath.getParent());
        Files.writeString(outputPath, GSON.toJson(report));
    }

    private BigDecimal scaleMoney(BigDecimal value) {
        return value.setScale(2, RoundingMode.HALF_UP);
    }

    private BigDecimal scaleRate(BigDecimal value) {
        return value.setScale(2, RoundingMode.HALF_UP);
    }
}
EOF

mvn -q -B -o test
