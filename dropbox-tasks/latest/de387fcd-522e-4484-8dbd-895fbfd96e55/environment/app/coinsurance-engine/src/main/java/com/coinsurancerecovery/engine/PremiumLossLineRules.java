package com.coinsurancerecovery.engine;

import java.math.BigDecimal;

public class PremiumLossLineRules {
    public static boolean isPremiumLossLine(BigDecimal grossIncurred, BigDecimal threshold) {
        return grossIncurred.compareTo(threshold) > 0;
    }
}
