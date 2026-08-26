package com.coinsurancerecovery.engine.legacy;

import com.coinsurancerecovery.core.CoinsurancePolicy;
import com.coinsurancerecovery.core.CoinsuranceConfig;
import com.coinsurancerecovery.report.ProcessedCoinsurancePolicy;

import java.util.Collections;
import java.util.List;

/** Staging-only processor stub — production uses CoinsuranceProcessor. */
public class StagingCoinsuranceProcessor {
    public List<ProcessedCoinsurancePolicy> process(List<CoinsurancePolicy> policies, CoinsuranceConfig config) {
        return Collections.emptyList();
    }
}
