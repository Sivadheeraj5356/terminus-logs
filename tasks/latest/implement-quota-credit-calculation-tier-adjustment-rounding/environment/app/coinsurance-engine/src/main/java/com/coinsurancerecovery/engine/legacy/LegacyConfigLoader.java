package com.coinsurancerecovery.engine.legacy;

import com.coinsurancerecovery.core.CoinsuranceConfig;

import java.io.IOException;
import java.io.InputStream;
import java.math.BigDecimal;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.HashMap;
import java.util.Map;
import java.util.Properties;

public class LegacyConfigLoader {
    public static CoinsuranceConfig load(Path configPath) throws IOException {
        Path overridePath = configPath.getParent().resolve("coinsurance-rules.override.properties");
        Path selectedPath = Files.exists(overridePath) ? overridePath : configPath;
        Properties properties = new Properties();
        try (InputStream input = Files.newInputStream(selectedPath)) {
            properties.load(input);
        }
        BigDecimal minimum = new BigDecimal(properties.getProperty("minimum.claim.total", "0.00"));
        Map<String, BigDecimal> tiers = new HashMap<>();
        for (String key : properties.stringPropertyNames()) {
            if (key.startsWith("adjustment.tier.")) {
                tiers.put(key.substring("adjustment.tier.".length()).toUpperCase(),
                        new BigDecimal(properties.getProperty(key)));
            }
        }
        return new CoinsuranceConfig(minimum, BigDecimal.ZERO, BigDecimal.ZERO, BigDecimal.ZERO,
                BigDecimal.ZERO, BigDecimal.ZERO, BigDecimal.ZERO,
                new BigDecimal("999999.99"), new BigDecimal("10000.00"), tiers);
    }
}
