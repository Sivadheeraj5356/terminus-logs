package com.coinsurancerecovery.engine;

import com.coinsurancerecovery.core.CoinsurancePolicy;
import com.coinsurancerecovery.core.CoinsuranceConfig;

import java.math.BigDecimal;
import java.math.RoundingMode;

public class QuotaCreditEngine {
    public BigDecimal quotaCreditAmount(CoinsurancePolicy adjustment, BigDecimal indemnityShare, CoinsuranceConfig config) {
        if (adjustment.getLossAmount().compareTo(config.getCatastropheThreshold()) > 0) {
            BigDecimal rate = config.getCatastropheCreditRate();
            if ("premium".equalsIgnoreCase(adjustment.getTreatyTier())
                    && adjustment.getLossAmount().compareTo(config.getPremiumLossThreshold()) >= 0) {
                rate = config.getPremiumCatastropheCreditRate();
            }
            return adjustment.getLossAmount().multiply(rate).setScale(2, RoundingMode.HALF_UP);
        }
        return BigDecimal.ZERO.setScale(2, RoundingMode.HALF_UP);
    }
}
