package com.coinsurancerecovery.report;

import java.math.BigDecimal;
import java.math.RoundingMode;

public class FinancePolicy {
    public static BigDecimal netRecovery(
            BigDecimal indemnityShare,
            BigDecimal tierAdjustmentAmount,
            BigDecimal quotaCreditAmount,
            BigDecimal processingFeeAmount,
            BigDecimal premiumHoldbackAmount
    ) {
        return indemnityShare
                .subtract(tierAdjustmentAmount)
                .subtract(quotaCreditAmount)
                .add(processingFeeAmount)
                .subtract(premiumHoldbackAmount)
                .setScale(2, RoundingMode.HALF_UP);
    }
}
