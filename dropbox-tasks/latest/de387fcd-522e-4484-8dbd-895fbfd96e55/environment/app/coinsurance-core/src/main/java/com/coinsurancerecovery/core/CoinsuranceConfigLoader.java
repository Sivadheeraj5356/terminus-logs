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
        Path overridePath = configPath.getParent().resolve("coinsurance-rules.override.properties");
        Path selectedPath = Files.exists(overridePath) ? overridePath : configPath;

        Properties properties = new Properties();
        try (InputStream input = Files.newInputStream(selectedPath)) {
            properties.load(input);
        }

        BigDecimal minimumRecoveryAmount = new BigDecimal(properties.getProperty("minimum.policy.total", "0.00"));
        BigDecimal indemnityShareRate = new BigDecimal(properties.getProperty("indemnity.share.rate", "0.00"));
        BigDecimal processingFeeRate = new BigDecimal(properties.getProperty("processing.fee.rate", "0.00"));
        BigDecimal erosionCreditRate = new BigDecimal(properties.getProperty("quota.credit.rate", "0.00"));
        BigDecimal deductibleHoldbackRate = new BigDecimal(properties.getProperty("premium.holdback.rate", "0.00"));
        BigDecimal premiumCatRate = new BigDecimal(
                properties.getProperty("quota.credit.rate.high", erosionCreditRate.toPlainString())
        );

        Map<String, BigDecimal> adjustmentRates = new HashMap<>();
        for (String key : properties.stringPropertyNames()) {
            if (key.startsWith("adjustment.tier.")) {
                String tier = key.substring("adjustment.tier.".length());
                adjustmentRates.put(tier.toUpperCase(), new BigDecimal(properties.getProperty(key)));
            }
        }

        return new CoinsuranceConfig(
                minimumRecoveryAmount,
                indemnityShareRate,
                processingFeeRate,
                erosionCreditRate,
                deductibleHoldbackRate,
                premiumCatRate,
                deductibleHoldbackRate,
                new BigDecimal("999999.99"),
                new BigDecimal("10000.00"),
                adjustmentRates
        );
    }
}
