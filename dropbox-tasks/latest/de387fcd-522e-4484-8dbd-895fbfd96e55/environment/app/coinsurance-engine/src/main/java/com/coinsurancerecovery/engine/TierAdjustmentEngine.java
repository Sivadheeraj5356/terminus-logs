package com.coinsurancerecovery.engine;

import com.coinsurancerecovery.core.CoinsurancePolicy;
import com.coinsurancerecovery.core.CoinsuranceConfig;

import java.math.BigDecimal;
import java.math.RoundingMode;

public class TierAdjustmentEngine {
    public BigDecimal adjustmentRate(CoinsurancePolicy adjustment, CoinsuranceConfig config) {
        return config.getAdjustmentRate(adjustment.getTreatyTier());
    }

    public BigDecimal tierAdjustmentAmount(CoinsurancePolicy adjustment, BigDecimal indemnityShare, CoinsuranceConfig config) {
        BigDecimal rate = adjustmentRate(adjustment, config);
        BigDecimal basis = indemnityShare;
        if (adjustment.getLossAmount().compareTo(config.getCatastropheThreshold()) > 0) {
            if ("plus".equalsIgnoreCase(adjustment.getTreatyTier())) {
                basis = adjustment.getLossAmount();
            }
        }
        return basis.multiply(rate).setScale(2, RoundingMode.HALF_UP);
    }
}
