package com.coinsurancerecovery.core;

import com.google.gson.Gson;
import com.google.gson.reflect.TypeToken;
import java.io.IOException;
import java.math.BigDecimal;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.List;

public class CoinsurancePolicyParser {
    private final Gson gson = new Gson();

    public List<CoinsurancePolicy> parse(Path inputPath) throws IOException {
        String json = Files.readString(inputPath);
        List<Row> rows = gson.fromJson(json, new TypeToken<List<Row>>(){}.getType());
        return rows.stream().map(r -> new CoinsurancePolicy(
                r.id, r.insurer, BigDecimal.valueOf(r.grossIncurred),
                BigDecimal.valueOf(r.deductibleAmount), BigDecimal.valueOf(r.coinsuranceRate),
                r.status, r.policyTier)).toList();
    }

    private static class Row {
        String id; String insurer; double grossIncurred; double deductibleAmount;
        double coinsuranceRate; String status; String policyTier;
    }
}
