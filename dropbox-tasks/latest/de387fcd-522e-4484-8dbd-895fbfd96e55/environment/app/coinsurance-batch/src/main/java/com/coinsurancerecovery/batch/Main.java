package com.coinsurancerecovery.batch;

import com.coinsurancerecovery.core.CoinsuranceConfigLoader;
import com.coinsurancerecovery.core.CoinsurancePolicyParser;
import com.coinsurancerecovery.engine.CoinsuranceProcessor;
import com.coinsurancerecovery.report.ReportGenerator;

import java.nio.file.Path;

public class Main {
    public static void main(String[] args) throws Exception {
        Path configPath = Path.of("/app/config/coinsurance-rules.properties");
        Path inputPath = Path.of("/app/data/coinsurance-policies.json");
        Path outputPath = Path.of("/app/output/coinsurance-report.json");

        var config = CoinsuranceConfigLoader.load(configPath);
        var parser = new CoinsurancePolicyParser();
        var processor = new CoinsuranceProcessor(config);
        var reportGenerator = new ReportGenerator();

        var policies = parser.parse(inputPath);
        var processed = processor.process(policies);
        reportGenerator.writeReport(processed, outputPath);
    }
}
