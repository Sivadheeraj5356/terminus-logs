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
    private final QuotaCreditEngine erosionCreditEngine = new QuotaCreditEngine();
    private final PremiumHoldbackCalculator premiumHoldbackCalculator = new PremiumHoldbackCalculator();
    private final EligibilityRules eligibilityRules = new EligibilityRules();

    public CoinsuranceProcessor(CoinsuranceConfig config) {
        this.config = config;
    }

    public List<ProcessedCoinsurancePolicy> process(List<CoinsurancePolicy> policies) {
        List<ProcessedCoinsurancePolicy> processed = new ArrayList<>();
        for (CoinsurancePolicy adjustment : policies) {
            if (!eligibilityRules.isApproved(adjustment) || !eligibilityRules.hasLossAmount(adjustment)) {
                continue;
            }
            if (!eligibilityRules.meetsMinimum(adjustment, config)) {
                continue;
            }

            BigDecimal indemnityShare = indemnityShareCalculator.indemnityShare(adjustment, config);
            BigDecimal processingFeeAmount = processingFeeCalculator.processingFeeAmount(adjustment, config);
            BigDecimal adjustmentRate = tierAdjustmentEngine.adjustmentRate(adjustment, config);
            BigDecimal tierAdjustmentAmount = tierAdjustmentEngine.tierAdjustmentAmount(adjustment, indemnityShare, config);
            BigDecimal quotaCreditAmount = erosionCreditEngine.quotaCreditAmount(adjustment, indemnityShare, config);
            BigDecimal premiumHoldbackAmount = premiumHoldbackCalculator.premiumHoldbackAmount(
                    adjustment, indemnityShare, tierAdjustmentAmount, quotaCreditAmount, processingFeeAmount, config
            );
            BigDecimal netRecovery = FinancePolicy.netRecovery(
                    indemnityShare, tierAdjustmentAmount, quotaCreditAmount, processingFeeAmount, premiumHoldbackAmount
            );

            processed.add(new ProcessedCoinsurancePolicy(
                    adjustment.getId(),
                    adjustment.getCedent(),
                    adjustment.getLossAmount(),
                    adjustment.getLayerAttachment(),
                    adjustment.getLayerCap(),
                    adjustment.getTreatyTier(),
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
