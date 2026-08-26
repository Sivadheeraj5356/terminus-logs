package com.coinsurancerecovery.engine;

import com.coinsurancerecovery.core.CoinsurancePolicy;
import com.coinsurancerecovery.core.CoinsuranceConfig;

import java.math.BigDecimal;

public final class QuotaBasisRules {
    private QuotaBasisRules() {
    }

    public static BigDecimal tierPremiumBasis(
            CoinsurancePolicy adjustment,
            BigDecimal indemnityShare,
            BigDecimal quotaCreditAmount,
            CoinsuranceConfig config
    ) {
        if (adjustment.getLossAmount().compareTo(config.getCatastropheThreshold()) > 0) {
            return indemnityShare.subtract(quotaCreditAmount);
        }
        return indemnityShare;
    }
}
