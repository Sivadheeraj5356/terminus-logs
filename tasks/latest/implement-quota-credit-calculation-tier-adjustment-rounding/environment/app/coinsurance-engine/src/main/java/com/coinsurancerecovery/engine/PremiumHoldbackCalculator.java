package com.coinsurancerecovery.engine;

import com.coinsurancerecovery.core.CoinsurancePolicy;
import com.coinsurancerecovery.core.CoinsuranceConfig;

import java.math.BigDecimal;
import java.math.RoundingMode;

public class PremiumHoldbackCalculator {
    public BigDecimal premiumHoldbackAmount(
            CoinsurancePolicy adjustment,
            BigDecimal indemnityShare,
            BigDecimal tierAdjustmentAmount,
            BigDecimal quotaCreditAmount,
            BigDecimal processingFeeAmount,
            CoinsuranceConfig config
    ) {
        if ("basic".equalsIgnoreCase(adjustment.getTreatyTier())
                && adjustment.getLossAmount().compareTo(config.getMinimumRecoveryAmount()) == 0) {
            return BigDecimal.ZERO.setScale(2, RoundingMode.HALF_UP);
        }

        BigDecimal taxable = indemnityShare.subtract(tierAdjustmentAmount).subtract(quotaCreditAmount);
        BigDecimal rate = PremiumReserveHoldbackPolicy.premiumHoldbackRate(
                adjustment.getLossAmount(),
                config.getPremiumLossThreshold(),
                config.getRetentionHoldbackRate(),
                config.getPremiumRetentionHoldbackRate()
        );
        if ("premium".equalsIgnoreCase(adjustment.getTreatyTier())) {
            rate = config.getPremiumRetentionHoldbackRate();
        }
        return taxable.multiply(rate).setScale(2, RoundingMode.HALF_DOWN);
    }
}
