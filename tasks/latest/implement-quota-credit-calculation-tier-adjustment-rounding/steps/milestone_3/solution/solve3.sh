#!/bin/bash
set -eo pipefail

cd /app

cat > coinsurance-report/src/main/java/com/coinsurancerecovery/report/FinancePolicy.java << 'EOF'
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
EOF

cat > coinsurance-engine/src/main/java/com/coinsurancerecovery/engine/IndemnityShareCalculator.java << 'EOF'
package com.coinsurancerecovery.engine;

import com.coinsurancerecovery.core.CoinsurancePolicy;
import com.coinsurancerecovery.core.CoinsuranceConfig;

import java.math.BigDecimal;
import java.math.RoundingMode;

public class IndemnityShareCalculator {
    public BigDecimal indemnityShare(CoinsurancePolicy towerLayer, CoinsuranceConfig config) {
        return towerLayer.coinsuranceBase()
                .multiply(config.getBaseRecoveryRate())
                .setScale(2, RoundingMode.HALF_UP);
    }
}
EOF

cat > coinsurance-engine/src/main/java/com/coinsurancerecovery/engine/ProcessingFeeCalculator.java << 'EOF'
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
EOF

cat > coinsurance-engine/src/main/java/com/coinsurancerecovery/engine/TierAdjustmentEngine.java << 'EOF'
package com.coinsurancerecovery.engine;

import com.coinsurancerecovery.core.CoinsurancePolicy;
import com.coinsurancerecovery.core.CoinsuranceConfig;

import java.math.BigDecimal;
import java.math.RoundingMode;

public class TierAdjustmentEngine {
    public BigDecimal adjustmentRate(CoinsurancePolicy towerLayer, CoinsuranceConfig config) {
        return config.getAdjustmentRate(towerLayer.getTreatyTier());
    }

    public BigDecimal tierAdjustmentAmount(
            CoinsurancePolicy towerLayer,
            BigDecimal indemnityShare,
            BigDecimal quotaCreditAmount,
            CoinsuranceConfig config
    ) {
        BigDecimal rate = adjustmentRate(towerLayer, config);
        BigDecimal basis = indemnityShare;
        if (("premium".equalsIgnoreCase(towerLayer.getTreatyTier()) || "plus".equalsIgnoreCase(towerLayer.getTreatyTier()))
                && towerLayer.coinsuranceBase().compareTo(config.getCatastropheThreshold()) >= 0) {
            basis = indemnityShare.subtract(quotaCreditAmount);
        }
        BigDecimal rawBonus = basis.multiply(rate);
        if ("plus".equalsIgnoreCase(towerLayer.getTreatyTier())
                && towerLayer.coinsuranceBase().compareTo(config.getCatastropheThreshold()) >= 0) {
            return rawBonus.setScale(2, RoundingMode.HALF_DOWN);
        }
        if ("premium".equalsIgnoreCase(towerLayer.getTreatyTier())
                && towerLayer.coinsuranceBase().compareTo(config.getPremiumLossThreshold()) >= 0) {
            return rawBonus.setScale(2, RoundingMode.HALF_DOWN);
        }
        return rawBonus.setScale(2, RoundingMode.HALF_UP);
    }
}
EOF

cat > coinsurance-engine/src/main/java/com/coinsurancerecovery/engine/QuotaCreditEngine.java << 'EOF'
package com.coinsurancerecovery.engine;

import com.coinsurancerecovery.core.CoinsurancePolicy;
import com.coinsurancerecovery.core.CoinsuranceConfig;

import java.math.BigDecimal;
import java.math.RoundingMode;

public class QuotaCreditEngine {
    public BigDecimal quotaCreditAmount(CoinsurancePolicy towerLayer, BigDecimal indemnityShare, CoinsuranceConfig config) {
        if (towerLayer.coinsuranceBase().compareTo(config.getCatastropheThreshold()) >= 0) {
            BigDecimal rate = config.getCatastropheCreditRate();
            if (towerLayer.coinsuranceBase().compareTo(config.getPremiumLossThreshold()) >= 0) {
                rate = config.getPremiumCatastropheCreditRate();
            }
            BigDecimal rawMega = indemnityShare.multiply(rate);
            if ("premium".equalsIgnoreCase(towerLayer.getTreatyTier())) {
                return rawMega.setScale(2, RoundingMode.HALF_DOWN);
            }
            return rawMega.setScale(2, RoundingMode.HALF_UP);
        }
        return BigDecimal.ZERO.setScale(2, RoundingMode.HALF_UP);
    }
}
EOF

cat > coinsurance-engine/src/main/java/com/coinsurancerecovery/engine/PremiumHoldbackCalculator.java << 'EOF'
package com.coinsurancerecovery.engine;

import com.coinsurancerecovery.core.CoinsurancePolicy;
import com.coinsurancerecovery.core.CoinsuranceConfig;

import java.math.BigDecimal;
import java.math.RoundingMode;

public class PremiumHoldbackCalculator {
    public BigDecimal premiumHoldbackAmount(
            CoinsurancePolicy towerLayer,
            BigDecimal indemnityShare,
            BigDecimal tierAdjustmentAmount,
            BigDecimal quotaCreditAmount,
            BigDecimal processingFeeAmount,
            CoinsuranceConfig config
    ) {
        if ("basic".equalsIgnoreCase(towerLayer.getTreatyTier())
                && towerLayer.getLossAmount().compareTo(config.getMinimumRecoveryAmount()) == 0) {
            return BigDecimal.ZERO.setScale(2, RoundingMode.HALF_UP);
        }

        BigDecimal taxable = indemnityShare
                .subtract(tierAdjustmentAmount)
                .subtract(quotaCreditAmount)
                .add(processingFeeAmount);
        BigDecimal rate = config.getRetentionHoldbackRate();
        if (towerLayer.coinsuranceBase().compareTo(config.getPremiumLossThreshold()) >= 0) {
            rate = config.getPremiumRetentionHoldbackRate();
        }
        BigDecimal rawHoldback = taxable.multiply(rate);
        if (towerLayer.coinsuranceBase().compareTo(config.getCatastropheThreshold()) >= 0) {
            return rawHoldback.setScale(2, RoundingMode.HALF_DOWN);
        }
        return rawHoldback.setScale(2, RoundingMode.HALF_UP);
    }
}
EOF

mvn -q -B -o test
