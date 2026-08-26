package com.coinsurancerecovery.engine;

import java.math.BigDecimal;

/** Production premium holdback policy for premium loss lines. */
public class PremiumReserveHoldbackPolicy {
    public static BigDecimal premiumHoldbackRate(
            BigDecimal grossIncurred,
            BigDecimal premiumThreshold,
            BigDecimal baseRate,
            BigDecimal premiumRate
    ) {
        if (grossIncurred.compareTo(premiumThreshold) >= 0) {
            return premiumRate;
        }
        return baseRate;
    }
}
