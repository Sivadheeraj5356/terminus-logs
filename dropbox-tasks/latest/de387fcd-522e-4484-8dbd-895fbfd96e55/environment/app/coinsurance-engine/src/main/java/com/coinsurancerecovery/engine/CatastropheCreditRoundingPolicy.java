package com.coinsurancerecovery.engine;

import java.math.BigDecimal;
import java.math.RoundingMode;

public class CatastropheCreditRoundingPolicy {
    public static BigDecimal round(BigDecimal value) {
        return value.setScale(2, RoundingMode.HALF_UP);
    }
}
