package com.coinsurancerecovery.core;

import java.math.BigDecimal;
import java.math.RoundingMode;

public class CoinsurancePolicy {
    private final String id;
    private final String insurer;
    private final BigDecimal grossIncurred;
    private final BigDecimal deductibleAmount;
    private final BigDecimal coinsuranceRate;
    private final String status;
    private final String policyTier;

    public CoinsurancePolicy(
            String id,
            String insurer,
            BigDecimal grossIncurred,
            BigDecimal deductibleAmount,
            BigDecimal coinsuranceRate,
            String status,
            String policyTier
    ) {
        this.id = id;
        this.insurer = insurer;
        this.grossIncurred = grossIncurred;
        this.deductibleAmount = deductibleAmount;
        this.coinsuranceRate = coinsuranceRate;
        this.status = status;
        this.policyTier = policyTier;
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
    public String getStatus() { return status; }
    public String getPolicyTier() { return policyTier; }
    public String getTreatyTier() { return policyTier; }

    public BigDecimal coinsuranceBase() {
        BigDecimal net = grossIncurred.multiply(coinsuranceRate).subtract(deductibleAmount);
        if (net.compareTo(BigDecimal.ZERO) < 0) {
            return BigDecimal.ZERO.setScale(2, RoundingMode.HALF_UP);
        }
        return net.setScale(2, RoundingMode.HALF_UP);
    }
}
