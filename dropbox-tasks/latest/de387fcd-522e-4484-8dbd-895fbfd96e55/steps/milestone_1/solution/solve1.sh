#!/bin/bash
set -eo pipefail

cd /app

cat > coinsurance-core/src/main/java/com/coinsurancerecovery/core/CoinsuranceConfigLoader.java << 'EOF'
package com.coinsurancerecovery.core;

import java.io.IOException;
import java.io.InputStream;
import java.math.BigDecimal;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.HashMap;
import java.util.Map;
import java.util.Properties;

public class CoinsuranceConfigLoader {
    public static CoinsuranceConfig load(Path configPath) throws IOException {
        Properties properties = new Properties();
        try (InputStream input = Files.newInputStream(configPath)) {
            properties.load(input);
        }

        BigDecimal minimumRecoveryAmount = new BigDecimal(properties.getProperty("minimum.policy.amount", "0.00"));
        BigDecimal indemnityShareRate = new BigDecimal(properties.getProperty("indemnity.share.rate", "0.00"));
        BigDecimal processingFeeRate = new BigDecimal(properties.getProperty("processing.fee.rate", "0.00"));
        BigDecimal quotaCreditRate = new BigDecimal(properties.getProperty("quota.credit.rate", "0.00"));
        BigDecimal premiumHoldbackRate = new BigDecimal(properties.getProperty("premium.holdback.rate", "0.00"));
        BigDecimal premiumCatastropheCreditRate = new BigDecimal(
                properties.getProperty("coinsurance.rate.quota.premium", quotaCreditRate.toPlainString())
        );
        BigDecimal premiumRetentionHoldbackRate = new BigDecimal(
                properties.getProperty("coinsurance.rate.holdback.premium", premiumHoldbackRate.toPlainString())
        );
        BigDecimal premiumLossThreshold = new BigDecimal(
                properties.getProperty("coinsurance.threshold.large.loss", "999999.99")
        );
        BigDecimal catastropheThreshold = new BigDecimal(
                properties.getProperty("coinsurance.threshold.quota", "999999.99")
        );

        Map<String, BigDecimal> adjustmentRates = new HashMap<>();
        for (String key : properties.stringPropertyNames()) {
            if (key.startsWith("adjustment.tier.")) {
                String tier = key.substring("adjustment.tier.".length()).toLowerCase();
                adjustmentRates.put(tier, new BigDecimal(properties.getProperty(key)));
            }
        }

        return new CoinsuranceConfig(
                minimumRecoveryAmount,
                indemnityShareRate,
                processingFeeRate,
                quotaCreditRate,
                premiumHoldbackRate,
                premiumCatastropheCreditRate,
                premiumRetentionHoldbackRate,
                premiumLossThreshold,
                catastropheThreshold,
                adjustmentRates
        );
    }
}
EOF

cat > coinsurance-core/src/main/java/com/coinsurancerecovery/core/EligibilityRules.java << 'EOF'
package com.coinsurancerecovery.core;

import java.math.BigDecimal;

public class EligibilityRules {
    public boolean isApproved(CoinsurancePolicy towerLayer) {
        return "approved".equalsIgnoreCase(towerLayer.getStatus());
    }

    public boolean hasLossAmount(CoinsurancePolicy towerLayer) {
        return towerLayer.getLossAmount().compareTo(BigDecimal.ZERO) > 0;
    }

    public boolean meetsMinimum(CoinsurancePolicy towerLayer, CoinsuranceConfig config) {
        return towerLayer.getLossAmount().compareTo(config.getMinimumRecoveryAmount()) >= 0;
    }
}
EOF

mvn -q -B -o test
