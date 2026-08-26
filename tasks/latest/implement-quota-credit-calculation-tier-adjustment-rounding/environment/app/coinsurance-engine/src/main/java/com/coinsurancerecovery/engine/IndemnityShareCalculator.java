package com.coinsurancerecovery.engine;

import com.coinsurancerecovery.core.CoinsurancePolicy;
import com.coinsurancerecovery.core.CoinsuranceConfig;

import java.math.BigDecimal;
import java.math.RoundingMode;

public class IndemnityShareCalculator {
    public BigDecimal indemnityShare(CoinsurancePolicy adjustment, CoinsuranceConfig config) {
        return adjustment.getLossAmount()
                .multiply(config.getBaseRecoveryRate())
                .setScale(2, RoundingMode.HALF_UP);
    }
}
