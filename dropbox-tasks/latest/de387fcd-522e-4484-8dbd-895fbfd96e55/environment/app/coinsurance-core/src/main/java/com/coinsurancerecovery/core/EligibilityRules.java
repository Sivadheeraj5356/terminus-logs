package com.coinsurancerecovery.core;

import java.math.BigDecimal;

public class EligibilityRules {
    public boolean isApproved(CoinsurancePolicy adjustment) {
        return "approved".equals(adjustment.getStatus());
    }

    public boolean hasLossAmount(CoinsurancePolicy adjustment) {
        return adjustment.getLossAmount().compareTo(BigDecimal.ZERO) > 0;
    }

    public boolean meetsMinimum(CoinsurancePolicy adjustment, CoinsuranceConfig config) {
        return adjustment.getLossAmount().compareTo(config.getMinimumRecoveryAmount()) > 0;
    }
}
