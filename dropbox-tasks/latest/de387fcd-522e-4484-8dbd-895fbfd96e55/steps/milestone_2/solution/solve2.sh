#!/bin/bash
set -eo pipefail

cd /app

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
        return basis.multiply(rate).setScale(2, RoundingMode.HALF_UP);
    }
}
EOF

cat > coinsurance-engine/src/main/java/com/coinsurancerecovery/engine/CoinsuranceProcessor.java << 'EOF'
package com.coinsurancerecovery.engine;

import com.coinsurancerecovery.core.EligibilityRules;
import com.coinsurancerecovery.core.CoinsurancePolicy;
import com.coinsurancerecovery.core.CoinsuranceConfig;
import com.coinsurancerecovery.report.FinancePolicy;
import com.coinsurancerecovery.report.ProcessedCoinsurancePolicy;

import java.math.BigDecimal;
import java.util.ArrayList;
import java.util.Comparator;
import java.util.List;

public class CoinsuranceProcessor {
    private final CoinsuranceConfig config;
    private final IndemnityShareCalculator indemnityShareCalculator = new IndemnityShareCalculator();
    private final ProcessingFeeCalculator processingFeeCalculator = new ProcessingFeeCalculator();
    private final TierAdjustmentEngine tierAdjustmentEngine = new TierAdjustmentEngine();
    private final QuotaCreditEngine quotaCreditEngine = new QuotaCreditEngine();
    private final PremiumHoldbackCalculator premiumHoldbackCalculator = new PremiumHoldbackCalculator();
    private final EligibilityRules eligibilityRules = new EligibilityRules();

    public CoinsuranceProcessor(CoinsuranceConfig config) {
        this.config = config;
    }

    public List<ProcessedCoinsurancePolicy> process(List<CoinsurancePolicy> policies) {
        List<ProcessedCoinsurancePolicy> processed = new ArrayList<>();
        for (CoinsurancePolicy towerLayer : policies) {
            if (!eligibilityRules.isApproved(towerLayer) || !eligibilityRules.hasLossAmount(towerLayer)) {
                continue;
            }
            if (!eligibilityRules.meetsMinimum(towerLayer, config)) {
                continue;
            }

            BigDecimal indemnityShare = indemnityShareCalculator.indemnityShare(towerLayer, config);
            BigDecimal processingFeeAmount = processingFeeCalculator.processingFeeAmount(towerLayer, config);
            BigDecimal adjustmentRate = tierAdjustmentEngine.adjustmentRate(towerLayer, config);
            BigDecimal quotaCreditAmount = quotaCreditEngine.quotaCreditAmount(towerLayer, indemnityShare, config);
            BigDecimal tierAdjustmentAmount = tierAdjustmentEngine.tierAdjustmentAmount(
                    towerLayer, indemnityShare, quotaCreditAmount, config
            );
            BigDecimal premiumHoldbackAmount = premiumHoldbackCalculator.premiumHoldbackAmount(
                    towerLayer, indemnityShare, tierAdjustmentAmount, quotaCreditAmount, processingFeeAmount, config
            );
            BigDecimal netRecovery = FinancePolicy.netRecovery(
                    indemnityShare, tierAdjustmentAmount, quotaCreditAmount, processingFeeAmount, premiumHoldbackAmount
            );

            processed.add(new ProcessedCoinsurancePolicy(
                    towerLayer.getId(),
                    towerLayer.getCedent(),
                    towerLayer.getLossAmount(),
                    towerLayer.getDeductibleAmount(),
                    towerLayer.getCoinsuranceRate(),
                    towerLayer.getTreatyTier(),
                    indemnityShare,
                    processingFeeAmount,
                    adjustmentRate,
                    tierAdjustmentAmount,
                    quotaCreditAmount,
                    premiumHoldbackAmount,
                    netRecovery
            ));
        }

        processed.sort(Comparator.comparing(ProcessedCoinsurancePolicy::getId));
        return processed;
    }
}
EOF

mvn -q -B -o test
