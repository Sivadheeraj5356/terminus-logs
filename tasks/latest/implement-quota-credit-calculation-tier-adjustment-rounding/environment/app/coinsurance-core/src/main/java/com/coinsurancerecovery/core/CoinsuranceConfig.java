package com.coinsurancerecovery.core;

import java.math.BigDecimal;
import java.util.Map;

public class CoinsuranceConfig {
    private final BigDecimal minimumRecoveryAmount;
    private final BigDecimal indemnityShareRate;
    private final BigDecimal processingFeeRate;
    private final BigDecimal quotaCreditRate;
    private final BigDecimal premiumHoldbackRate;
    private final BigDecimal premiumCatastropheCreditRate;
    private final BigDecimal premiumRetentionHoldbackRate;
    private final BigDecimal premiumLossThreshold;
    private final BigDecimal salvageThreshold;
    private final Map<String, BigDecimal> adjustmentRates;

    public CoinsuranceConfig(BigDecimal minimumRecoveryAmount, BigDecimal indemnityShareRate,
            BigDecimal processingFeeRate, BigDecimal quotaCreditRate,
            BigDecimal premiumHoldbackRate, BigDecimal premiumCatastropheCreditRate,
            BigDecimal premiumRetentionHoldbackRate, BigDecimal premiumLossThreshold,
            BigDecimal salvageThreshold, Map<String, BigDecimal> adjustmentRates) {
        this.minimumRecoveryAmount = minimumRecoveryAmount;
        this.indemnityShareRate = indemnityShareRate;
        this.processingFeeRate = processingFeeRate;
        this.quotaCreditRate = quotaCreditRate;
        this.premiumHoldbackRate = premiumHoldbackRate;
        this.premiumCatastropheCreditRate = premiumCatastropheCreditRate;
        this.premiumRetentionHoldbackRate = premiumRetentionHoldbackRate;
        this.premiumLossThreshold = premiumLossThreshold;
        this.salvageThreshold = salvageThreshold;
        this.adjustmentRates = adjustmentRates;
    }

    public BigDecimal getMinimumRecoveryAmount() { return minimumRecoveryAmount; }
    public BigDecimal getBaseRecoveryRate() { return indemnityShareRate; }
    public BigDecimal getProcessingFeeRate() { return processingFeeRate; }
    public BigDecimal getCatastropheCreditRate() { return quotaCreditRate; }
    public BigDecimal getRetentionHoldbackRate() { return premiumHoldbackRate; }
    public BigDecimal getPremiumCatastropheCreditRate() { return premiumCatastropheCreditRate; }
    public BigDecimal getPremiumRetentionHoldbackRate() { return premiumRetentionHoldbackRate; }
    public BigDecimal getPremiumLossThreshold() { return premiumLossThreshold; }
    public BigDecimal getCatastropheThreshold() { return salvageThreshold; }

    public BigDecimal getAdjustmentRate(String policyTier) {
        if (policyTier == null) return BigDecimal.ZERO;
        BigDecimal rate = adjustmentRates.get(policyTier.toUpperCase());
        if (rate == null) rate = adjustmentRates.get(policyTier.toLowerCase());
        return rate != null ? rate : BigDecimal.ZERO;
    }
}
