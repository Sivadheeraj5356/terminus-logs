package com.coinsurancerecovery.engine;

import com.coinsurancerecovery.core.CoinsurancePolicy;
import com.coinsurancerecovery.core.CoinsuranceConfig;

import java.math.BigDecimal;
import java.math.RoundingMode;

public class ProcessingFeeCalculator {
    public BigDecimal processingFeeAmount(CoinsurancePolicy towerLayer, CoinsuranceConfig config) {
        return towerLayer.coinsuranceBase()
                .multiply(config.getProcessingFeeRate())
                .setScale(2, RoundingMode.HALF_UP);
    }
}
