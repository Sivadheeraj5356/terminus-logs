package com.coinsurancerecovery.report;

import com.google.gson.Gson;
import com.google.gson.GsonBuilder;

import java.io.IOException;
import java.math.BigDecimal;
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
        BigDecimal totalTierAdjustment = BigDecimal.ZERO;
        BigDecimal totalQuotaCredit = BigDecimal.ZERO;
        BigDecimal totalPremiumHoldback = BigDecimal.ZERO;
        BigDecimal totalProcessingFee = BigDecimal.ZERO;
        BigDecimal totalRecovery = BigDecimal.ZERO;

        List<Map<String, Object>> rows = policies.stream().map(layer -> {
            Map<String, Object> row = new LinkedHashMap<>();
            row.put("id", layer.getId());
            row.put("insurer", layer.getCedent());
            row.put("grossIncurred", layer.getLossAmount());
            row.put("deductibleAmount", layer.getLayerAttachment());
            row.put("coinsuranceRate", layer.getLayerCap());
            row.put("policyTier", layer.getTreatyTier());
            row.put("indemnityShare", layer.getBaseRecovery());
            row.put("processingFeeAmount", layer.getProcessingFeeAmount());
            row.put("adjustmentRate", layer.getAdjustmentRate());
            row.put("tierAdjustmentAmount", layer.getTierAdjustmentAmount());
            row.put("quotaCreditAmount", layer.getCatastropheCreditAmount());
            row.put("premiumHoldbackAmount", layer.getRetentionHoldbackAmount());
            row.put("netRecovery", layer.getNetRecovery());
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
        summary.put("totalIndemnityShare", totalIndemnityShare);
        summary.put("totalProcessingFee", totalProcessingFee);
        summary.put("totalTierAdjustment", totalTierAdjustment);
        summary.put("totalQuotaCredit", totalQuotaCredit);
        summary.put("totalPremiumHoldback", totalPremiumHoldback);
        summary.put("totalRecovery", totalRecovery);

        Map<String, Object> report = new LinkedHashMap<>();
        report.put("generatedAt", Instant.now().toString());
        report.put("policies", rows);
        report.put("summary", summary);

        Files.createDirectories(outputPath.getParent());
        Files.writeString(outputPath, GSON.toJson(report));
    }
}
