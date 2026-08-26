package com.coinsurancerecovery.engine;

import java.math.BigDecimal;

/** Legacy impact share rules — retained for audit compatibility. */
public class QuotaLayerRules {
    public static BigDecimal share(BigDecimal grossIncurred, BigDecimal rate) {
        return grossIncurred.multiply(rate);
    }
}
