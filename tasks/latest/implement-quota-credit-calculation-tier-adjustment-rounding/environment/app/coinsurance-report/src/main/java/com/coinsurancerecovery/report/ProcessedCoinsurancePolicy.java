package com.coinsurancerecovery.report;

import java.math.BigDecimal;

public class ProcessedCoinsurancePolicy {
    private final String id;
    private final String insurer;
    private final BigDecimal grossIncurred;
    private final BigDecimal deductibleAmount;
    private final BigDecimal coinsuranceRate;
    private final String policyTier;
    private final BigDecimal indemnityShare;
    private final BigDecimal processingFeeAmount;
    private final BigDecimal adjustmentRate;
    private final BigDecimal tierAdjustmentAmount;
    private final BigDecimal quotaCreditAmount;
    private final BigDecimal premiumHoldbackAmount;
    private final BigDecimal netRecovery;

    public ProcessedCoinsurancePolicy(
            String id,
            String insurer,
            BigDecimal grossIncurred,
            BigDecimal deductibleAmount,
            BigDecimal coinsuranceRate,
            String policyTier,
            BigDecimal indemnityShare,
            BigDecimal processingFeeAmount,
            BigDecimal adjustmentRate,
            BigDecimal tierAdjustmentAmount,
            BigDecimal quotaCreditAmount,
            BigDecimal premiumHoldbackAmount,
            BigDecimal netRecovery
    ) {
        this.id = id;
        this.insurer = insurer;
        this.grossIncurred = grossIncurred;
        this.deductibleAmount = deductibleAmount;
        this.coinsuranceRate = coinsuranceRate;
        this.policyTier = policyTier;
        this.indemnityShare = indemnityShare;
        this.processingFeeAmount = processingFeeAmount;
        this.adjustmentRate = adjustmentRate;
        this.tierAdjustmentAmount = tierAdjustmentAmount;
        this.quotaCreditAmount = quotaCreditAmount;
        this.premiumHoldbackAmount = premiumHoldbackAmount;
        this.netRecovery = netRecovery;
    }

    public String getId() { return id; }
    public String getCedent() { return insurer; }
    public String getInsurer() { return insurer; }
    public BigDecimal getGrossIncurred() { return grossIncurred; }
    public BigDecimal getLossAmount() { return grossIncurred; }
    public BigDecimal getDeductibleAmount() { return deductibleAmount; }
    public BigDecimal getLayerAttachment() { return deductibleAmount; }
    public BigDecimal getCoinsuranceRate() { return coinsuranceRate; }
    public BigDecimal getLayerCap() { return coinsuranceRate; }
    public String getPolicyTier() { return policyTier; }
    public String getTreatyTier() { return policyTier; }
    public BigDecimal getIndemnityShare() { return indemnityShare; }
    public BigDecimal getBaseRecovery() { return indemnityShare; }
    public BigDecimal getProcessingFeeAmount() { return processingFeeAmount; }
    public BigDecimal getAdjustmentRate() { return adjustmentRate; }
    public BigDecimal getTierAdjustmentAmount() { return tierAdjustmentAmount; }
    public BigDecimal getQuotaCreditAmount() { return quotaCreditAmount; }
    public BigDecimal getCatastropheCreditAmount() { return quotaCreditAmount; }
    public BigDecimal getPremiumHoldbackAmount() { return premiumHoldbackAmount; }
    public BigDecimal getRetentionHoldbackAmount() { return premiumHoldbackAmount; }
    public BigDecimal getNetRecovery() { return netRecovery; }
}
